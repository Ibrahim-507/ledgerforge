"""Task 10: clients, invoices and payments, posted to the same ledger.
Status flow:  DRAFT -> SENT -> PARTIALLY_PAID -> PAID
                       SENT -> OVERDUE (past due date)      DRAFT/SENT -> CANCELLED
Ledger rules: DRAFT and CANCELLED-while-draft never post.
  send:    DR 1100 Receivable (total)   CR revenue accounts (subtotal)   CR 2200 GST output (gst)
  payment: DR 1001 Bank                 CR 1100 Receivable
  cancel a SENT invoice (no payments): post the REVERSAL of its entry, status CANCELLED."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal as D, ROUND_HALF_UP
from app.books_db import dec, fmt, next_id
from app.ledger import LedgerError, create_journal_entry, reverse_entry, financial_year, _to_date

BANK, RECEIVABLE, GST_OUTPUT = 1001, 1100, 2200
OPEN = ("SENT", "OVERDUE", "PARTIALLY_PAID")


class InvoiceError(Exception):
    pass


def _money(x) -> D:
    return D(str(x)).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def _get(conn, invoice_id):
    inv = conn.execute("SELECT * FROM invoices WHERE invoice_id=?", (invoice_id,)).fetchone()
    if inv is None:
        raise InvoiceError(f"Invoice {invoice_id} not found")
    return inv


def create_invoice(conn, client_id, invoice_date, items, gst_rate_percent=18, created_by=None, po_number=None) -> str:
    """Create a DRAFT. items = [{description, quantity, unit_price, revenue_account}]. Nothing is posted."""
    client = conn.execute("SELECT * FROM clients WHERE client_id=?", (client_id,)).fetchone()
    if client is None:
        raise InvoiceError(f"Client {client_id} not found")
    if not items:
        raise InvoiceError("An invoice needs at least one item")
    d = _to_date(invoice_date)
    rows, subtotal = [], D("0")
    for i, it in enumerate(items, 1):
        qty, price = dec(it["quantity"]), dec(it["unit_price"])
        if qty <= 0 or price < 0:
            raise InvoiceError(f"Item {i}: quantity must be above 0 and price cannot be negative")
        amt = _money(qty * price)
        rows.append((i, it.get("description"), qty, price, amt, int(it["revenue_account"])))
        subtotal += amt
    gst = _money(subtotal * dec(gst_rate_percent) / 100)
    total = subtotal + gst
    iid = next_id(conn, "invoices", "invoice_id", "INV-", 5)
    fy = f"{d.year if d.month >= 4 else d.year - 1}-{str((d.year if d.month >= 4 else d.year - 1) + 1)[2:]}"
    seq = conn.execute("SELECT COUNT(*) c FROM invoices WHERE invoice_number LIKE ?", (f"INV/{fy}/%",)).fetchone()["c"] + 1
    conn.execute("INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (iid, f"INV/{fy}/{seq:04d}", client_id, d.isoformat(),
                  (d + timedelta(days=client["payment_terms_days"])).isoformat(), rows[0][5], "INR",
                  fmt(subtotal), str(gst_rate_percent), fmt(gst), fmt(total), "0.00", fmt(total), "DRAFT", None,
                  po_number, "N", created_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), None))
    for no, desc, qty, price, amt, acc in rows:
        conn.execute("INSERT INTO invoice_items VALUES (?,?,?,?,?,?,?,?)",
                     (next_id(conn, "invoice_items", "invoice_item_id", "II-", 6), iid, no, desc, str(qty), str(price), fmt(amt), acc))
    conn.commit()
    return iid


def send_invoice(conn, invoice_id, created_by=None) -> str:
    """DRAFT -> SENT and post to the ledger. Returns the journal entry id."""
    inv = _get(conn, invoice_id)
    if inv["status"] != "DRAFT":
        raise InvoiceError(f"Only a DRAFT can be sent; {invoice_id} is {inv['status']}")
    rev = defaultdict(D)
    for it in conn.execute("SELECT * FROM invoice_items WHERE invoice_id=?", (invoice_id,)):
        rev[it["revenue_account"]] += dec(it["amount"])
    lines = [{"account_code": RECEIVABLE, "debit": dec(inv["total_amount"]), "line_description": f"Receivable {inv['invoice_number']}"}]
    for acc, amt in sorted(rev.items()):
        lines.append({"account_code": acc, "credit": amt, "line_description": f"Revenue {inv['invoice_number']}"})
    if dec(inv["gst_amount"]) > 0:
        lines.append({"account_code": GST_OUTPUT, "credit": dec(inv["gst_amount"]), "line_description": f"GST output {inv['invoice_number']}"})
    try:
        je = create_journal_entry(conn, inv["invoice_date"], f"Invoice {inv['invoice_number']}", lines,
                                  source_type="INVOICE", source_id=invoice_id, created_by=created_by, commit=False)
        conn.execute("UPDATE invoices SET status='SENT', ledger_entry_id=? WHERE invoice_id=?", (je, invoice_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return je


def record_payment(conn, invoice_id, payment_date, amount, payment_mode="NEFT", reference_no=None, received_by=None) -> str:
    inv = _get(conn, invoice_id)
    if inv["status"] not in OPEN:
        raise InvoiceError(f"Cannot take a payment on a {inv['status']} invoice")
    amt = _money(amount)
    bal = dec(inv["balance_due"])
    if amt <= 0:
        raise InvoiceError("Payment must be more than zero")
    if amt > bal:
        raise InvoiceError(f"Payment {fmt(amt)} is more than the balance due {fmt(bal)}")
    pid = next_id(conn, "invoice_payments", "payment_id", "PAY-", 5)
    try:
        je = create_journal_entry(conn, payment_date, f"Payment {pid} for {inv['invoice_number']}",
                                  [{"account_code": BANK, "debit": amt, "line_description": f"Bank receipt {reference_no or pid}"},
                                   {"account_code": RECEIVABLE, "credit": amt, "line_description": "Receivable cleared"}],
                                  source_type="INVOICE_PAYMENT", source_id=pid, created_by=received_by, commit=False)
        new_bal = bal - amt
        conn.execute("INSERT INTO invoice_payments VALUES (?,?,?,?,?,?,?,?)",
                     (pid, invoice_id, _to_date(payment_date).isoformat(), fmt(amt), payment_mode, reference_no, received_by, je))
        conn.execute("UPDATE invoices SET amount_paid=?, balance_due=?, status=?, last_payment_date=? WHERE invoice_id=?",
                     (fmt(dec(inv["amount_paid"]) + amt), fmt(new_bal), "PAID" if new_bal == 0 else "PARTIALLY_PAID",
                      _to_date(payment_date).isoformat(), invoice_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return pid


def mark_overdue(conn, as_of) -> list:
    """SENT invoices past their due date become OVERDUE (status only - the ledger is unchanged)."""
    d = _to_date(as_of).isoformat()
    ids = [r["invoice_id"] for r in conn.execute(
        "SELECT invoice_id FROM invoices WHERE status='SENT' AND due_date < ?", (d,))]
    for i in ids:
        conn.execute("UPDATE invoices SET status='OVERDUE' WHERE invoice_id=?", (i,))
    conn.commit()
    return ids


def cancel_invoice(conn, invoice_id, cancel_date, reason="", created_by=None):
    """DRAFT: just cancel, nothing was posted. SENT/OVERDUE with no payment: post the reversal.
    Anything with a payment (or PAID): refused - refund / credit-note the payment first."""
    inv = _get(conn, invoice_id)
    st = inv["status"]
    if st == "CANCELLED":
        raise InvoiceError("Invoice is already cancelled")
    if st in ("PAID", "PARTIALLY_PAID") or dec(inv["amount_paid"]) > 0:
        raise InvoiceError("Cannot cancel an invoice that has payments; refund or issue a credit note first")
    try:
        if st in ("SENT", "OVERDUE"):
            reverse_entry(conn, inv["ledger_entry_id"], cancel_date, reason or f"cancelled {inv['invoice_number']}",
                          created_by, commit=False)
        conn.execute("UPDATE invoices SET status='CANCELLED', balance_due='0.00' WHERE invoice_id=?", (invoice_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def receivables_list(conn):
    """Who owes what: one row per client with open invoices, plus the invoice detail."""
    q = ",".join("?" * len(OPEN))
    rows = conn.execute(
        f"SELECT i.*, c.client_name FROM invoices i JOIN clients c ON c.client_id=i.client_id "
        f"WHERE i.status IN ({q}) AND CAST(i.balance_due AS REAL) > 0 ORDER BY c.client_name, i.invoice_date", OPEN).fetchall()
    out = {}
    for r in rows:
        c = out.setdefault(r["client_id"], {"client_id": r["client_id"], "client_name": r["client_name"],
                                            "total_due": D("0"), "invoices": []})
        c["total_due"] += dec(r["balance_due"])
        c["invoices"].append({"invoice_id": r["invoice_id"], "invoice_number": r["invoice_number"], "due_date": r["due_date"],
                              "status": r["status"], "balance_due": dec(r["balance_due"])})
    return sorted(out.values(), key=lambda c: -c["total_due"])
