"""Task 11: vendors and expense bills with an approval step, posted to the ledger.

Status flow:   SUBMITTED -> APPROVED -> PAID          (SUBMITTED -> REJECTED is a dead end)
Ledger rules (same pattern as invoices):
  approve:  DR expense account (net) + DR 1200 GST input credit (gst)   CR 2001 Accounts Payable (total)
  pay:      DR 2001 Accounts Payable   CR 1001 Bank          <- clears the payable ONLY; expense is not counted again
  SUBMITTED / REJECTED bills never post.
Controls (decided BEFORE coding - see docs/expense_rules.md):
  1. Separation of duties: the approver must be a different person from the submitter.
  2. A bill cannot be paid before it is approved; nothing moves backwards.
  3. Likely duplicate bills are refused unless the submitter explicitly confirms."""
from datetime import timedelta
from decimal import Decimal as D, ROUND_HALF_UP
from app.books_db import dec, fmt, next_id
from app.ledger import create_journal_entry, _to_date

PAYABLE, BANK, GST_INPUT = 2001, 1001, 1200


class BillError(Exception):
    """A bill rule was broken (wrong status, bad amount, inactive vendor ...)."""


class SeparationOfDutiesError(BillError):
    """Creator and approver are the same person."""


class DuplicateBillError(BillError):
    def __init__(self, matches):
        self.matches = matches
        super().__init__("Likely duplicate of " + "; ".join(f"{m['expense_id']} ({m['reason']})" for m in matches))


def _money(x) -> D:
    return D(str(x)).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def _bill(conn, expense_id):
    b = conn.execute("SELECT * FROM expenses WHERE expense_id=?", (expense_id,)).fetchone()
    if b is None:
        raise BillError(f"Bill {expense_id} not found")
    return b


# ---------------- vendors ------------------------------------------------------------------
def add_vendor(conn, vendor_id, vendor_name, primary_expense_account=None, payment_terms_days=30, city=None, gst_registration=None):
    conn.execute("INSERT INTO vendors VALUES (?,?,?,?,?,?,'Y')",
                 (vendor_id, vendor_name, primary_expense_account, payment_terms_days, city, gst_registration))
    conn.commit()


# ---------------- duplicate detector (the challenge) ---------------------------------------------
def find_likely_duplicates(conn, vendor_id, bill_date, amount_excl_gst, bill_reference=None, window_days=7,
                           tolerance=D("0.01"), exclude_id=None):
    """A new bill is a likely duplicate of an existing live bill (not REJECTED) when, for the SAME vendor:
       (a) the vendor bill number is the same (ignoring case/spaces), or
       (b) the amount is equal, or within `tolerance` (1%), and the dates are within `window_days` days.
    Monthly bills such as rent are NOT flagged, because their dates are about 30 days apart."""
    d = _to_date(bill_date)
    amt = _money(amount_excl_gst)
    ref = (bill_reference or "").strip().lower()
    matches = []
    for b in conn.execute("SELECT * FROM expenses WHERE vendor_id=? AND status!='REJECTED'", (vendor_id,)):
        if b["expense_id"] == exclude_id:
            continue
        reasons = []
        if ref and (b["bill_reference"] or "").strip().lower() == ref:
            reasons.append("same bill number")
        other = dec(b["amount_excl_gst"])
        gap = abs((_to_date(b["expense_date"]) - d).days)
        if gap <= window_days and abs(other - amt) <= tolerance * max(other, amt):
            reasons.append("same amount within 1%" if other != amt else "same amount")
            reasons[-1] += f", {gap} day(s) apart"
        if reasons:
            matches.append({"expense_id": b["expense_id"], "reason": " and ".join(reasons)})
    return matches


# ---------------- the flow ------------------------------------------------------------------------
def submit_bill(conn, vendor_id, bill_date, category_account, amount_excl_gst, gst_rate_percent, submitted_by,
                department_id=None, description=None, bill_reference=None, allow_duplicate=False) -> str:
    """Create a SUBMITTED bill. Posts nothing."""
    v = conn.execute("SELECT * FROM vendors WHERE vendor_id=?", (vendor_id,)).fetchone()
    if v is None:
        raise BillError(f"Vendor {vendor_id} not found")
    if v["is_active"] != "Y":
        raise BillError(f"Vendor {vendor_id} is inactive")
    if not submitted_by:
        raise BillError("A bill must record who submitted it")
    net = _money(amount_excl_gst)
    if net <= 0:
        raise BillError("Bill amount must be more than zero")
    if not allow_duplicate:
        dups = find_likely_duplicates(conn, vendor_id, bill_date, net, bill_reference)
        if dups:
            raise DuplicateBillError(dups)
    d = _to_date(bill_date)
    gst = _money(net * dec(gst_rate_percent) / 100)
    eid = next_id(conn, "expenses", "expense_id", "EXP-", 5)
    conn.execute("INSERT INTO expenses VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (eid, d.isoformat(), int(category_account), vendor_id, bill_reference, description, department_id,
                  fmt(net), str(gst_rate_percent), fmt(gst), fmt(net + gst),
                  (d + timedelta(days=v["payment_terms_days"])).isoformat(), None, "SUBMITTED", None,
                  submitted_by, None, None, None, None))
    conn.commit()
    return eid


def approve_bill(conn, expense_id, approved_by, *, enforce_separation=True) -> str:
    """SUBMITTED -> APPROVED and post the expense. `enforce_separation=False` exists ONLY for loading
    historical data (see load_historical_bills); normal code must never pass it."""
    b = _bill(conn, expense_id)
    if b["status"] != "SUBMITTED":
        raise BillError(f"Only a SUBMITTED bill can be approved; {expense_id} is {b['status']}")
    if not approved_by:
        raise BillError("An approval must record who approved it")
    if enforce_separation and approved_by == b["submitted_by"]:
        raise SeparationOfDutiesError(f"{approved_by} submitted {expense_id} and cannot also approve it")
    lines = [{"account_code": b["category_account"], "debit": dec(b["amount_excl_gst"]),
              "cost_center_department_id": b["department_id"], "line_description": b["description"]}]
    if dec(b["gst_amount"]) > 0:
        lines.append({"account_code": GST_INPUT, "debit": dec(b["gst_amount"]), "line_description": "GST input credit"})
    lines.append({"account_code": PAYABLE, "credit": dec(b["total_amount"]), "line_description": f"Payable {b['bill_reference'] or expense_id}"})
    try:
        je = create_journal_entry(conn, b["expense_date"], f"Expense bill {b['bill_reference'] or expense_id}", lines,
                                  source_type="EXPENSE", source_id=expense_id, created_by=approved_by, commit=False)
        conn.execute("UPDATE expenses SET status='APPROVED', approved_by=?, ledger_entry_id=? WHERE expense_id=?",
                     (approved_by, je, expense_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return je


def reject_bill(conn, expense_id, rejected_by, reason=""):
    b = _bill(conn, expense_id)
    if b["status"] != "SUBMITTED":
        raise BillError(f"Only a SUBMITTED bill can be rejected; {expense_id} is {b['status']}")
    conn.execute("UPDATE expenses SET status='REJECTED', rejected_reason=? WHERE expense_id=?",
                 (f"{rejected_by}: {reason}", expense_id))
    conn.commit()


def pay_bill(conn, expense_id, paid_date, payment_mode="NEFT", paid_by=None) -> str:
    """APPROVED -> PAID. Clears the payable only (DR 2001 / CR bank); the expense was counted at approval."""
    b = _bill(conn, expense_id)
    if b["status"] == "PAID":
        raise BillError(f"{expense_id} is already paid")
    if b["status"] != "APPROVED":
        raise BillError(f"{expense_id} must be approved before it can be paid (status: {b['status']})")
    pd_ = _to_date(paid_date)
    if pd_ < _to_date(b["expense_date"]):
        raise BillError("Payment date cannot be before the bill date")
    total = dec(b["total_amount"])
    try:
        je = create_journal_entry(conn, pd_, f"Vendor payment {b['bill_reference'] or expense_id}",
                                  [{"account_code": PAYABLE, "debit": total, "line_description": "Payable cleared"},
                                   {"account_code": BANK, "credit": total, "line_description": f"{payment_mode} to {b['vendor_id']}"}],
                                  source_type="EXPENSE_PAYMENT", source_id=expense_id, created_by=paid_by, commit=False)
        conn.execute("UPDATE expenses SET status='PAID', paid_date=?, payment_mode=?, payment_ledger_entry_id=? WHERE expense_id=?",
                     (pd_.isoformat(), payment_mode, je, expense_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return je


# ---------------- reports -------------------------------------------------------------------------------
def spend_report(conn):
    """Spend by vendor and month = bills that reached the books (APPROVED or PAID), by bill date."""
    rows = conn.execute(
        "SELECT e.vendor_id, v.vendor_name, substr(e.expense_date,1,7) month, COUNT(*) bills, "
        "dsum(e.amount_excl_gst) net, dsum(e.gst_amount) gst, dsum(e.total_amount) total "
        "FROM expenses e JOIN vendors v ON v.vendor_id=e.vendor_id WHERE e.status IN ('APPROVED','PAID') "
        "GROUP BY e.vendor_id, month ORDER BY month, e.vendor_id").fetchall()
    return [dict(r) for r in rows]


def monthly_totals(conn) -> dict:
    return {r["month"]: dec(r["total"]) for r in conn.execute(
        "SELECT substr(expense_date,1,7) month, dsum(total_amount) total FROM expenses "
        "WHERE status IN ('APPROVED','PAID') GROUP BY month")}


def compare_with_csv(conn, expenses_csv):
    """Monthly totals in my books vs the expenses CSV -> list of (month, mine, csv, difference)."""
    import pandas as pd
    df = pd.read_csv(expenses_csv)
    csv_tot = {m: D(str(round(g, 2))) for m, g in df.groupby(df.expense_date.str[:7]).total_amount.sum().items()}
    mine = monthly_totals(conn)
    return [(m, mine.get(m, D("0")), csv_tot.get(m, D("0")), mine.get(m, D("0")) - csv_tot.get(m, D("0")))
            for m in sorted(set(mine) | set(csv_tot))]


def load_historical_bills(conn, vendors_csv, expenses_csv):
    """Replay the official expenses CSV through MY flow (submit -> approve -> pay) into the books.
    Returns the bills my separation-of-duties rule would have blocked (submitter == approver):
    they are loaded anyway, because history is history, but they are reported as audit findings."""
    import pandas as pd
    for v in pd.read_csv(vendors_csv).itertuples():
        add_vendor(conn, v.vendor_id, v.vendor_name, v.primary_expense_account, int(v.payment_terms_days), v.city, v.gst_registration)
    violations = []
    df = pd.read_csv(expenses_csv).sort_values(["expense_date", "expense_id"])
    for r in df.itertuples():
        eid = submit_bill(conn, r.vendor_id, r.expense_date, r.category_account, r.amount_excl_gst, r.gst_rate_percent,
                          r.submitted_by, r.department_id, r.description, r.bill_reference, allow_duplicate=True)
        same = r.submitted_by == r.approved_by
        if same:
            violations.append((r.expense_id, r.submitted_by, r.total_amount))
        approve_bill(conn, eid, r.approved_by, enforce_separation=False)
        if r.status == "PAID":
            pay_bill(conn, eid, r.paid_date, r.payment_mode, paid_by=r.approved_by)
    return violations
