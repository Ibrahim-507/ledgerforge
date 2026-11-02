"""Integrity checks on the books (the same ideas as verify_ledgerforge.py checks 1 and 3)."""
from decimal import Decimal as D
from app.books_db import dec, fmt
from app.ledger import account_balance


def check1_entries_balance(conn):
    """Check 1: every journal entry balances (sum of its lines' debits == credits) and header totals agree."""
    bad = [r["entry_id"] for r in conn.execute(
        "SELECT e.entry_id, e.total_debit td, e.total_credit tc, dsum(l.debit) d, dsum(l.credit) c "
        "FROM journal_entries e JOIN journal_lines l ON l.entry_id=e.entry_id GROUP BY e.entry_id")
        if not (dec(r["d"]) == dec(r["c"]) == dec(r["td"]) == dec(r["tc"]))]
    n = conn.execute("SELECT COUNT(*) c FROM journal_entries").fetchone()["c"]
    t = conn.execute("SELECT dsum(debit) d, dsum(credit) c FROM journal_lines").fetchone()
    return {"ok": not bad and dec(t["d"]) == dec(t["c"]), "entries": n, "unbalanced": bad[:10],
            "total_debit": t["d"], "total_credit": t["c"]}


OPEN = ("SENT", "OVERDUE", "PARTIALLY_PAID")


def check3_receivable_equals_open_invoices(conn, as_of=None):
    """Check 3: ledger account 1100 == sum of balance_due of open (posted, unpaid) invoices."""
    ledger = account_balance(conn, 1100, as_of)
    q = ",".join("?" * len(OPEN))
    r = conn.execute(f"SELECT dsum(balance_due) b FROM invoices WHERE status IN ({q})", OPEN).fetchone()
    inv = dec(r["b"])
    return {"ok": ledger == inv, "ledger_1100": fmt(ledger), "open_invoices": fmt(inv), "difference": fmt(ledger - inv)}


def check4_payables_equal_unpaid_bills(conn, as_of=None):
    """Check 4: ledger 2001 Accounts Payable == sum of total_amount of APPROVED (approved, not yet paid) bills."""
    from app.ledger import account_balance
    ledger = account_balance(conn, 2001, as_of)
    r = conn.execute("SELECT dsum(total_amount) b FROM expenses WHERE status='APPROVED'").fetchone()
    bills = dec(r["b"])
    return {"ok": ledger == bills, "ledger_2001": fmt(ledger), "unpaid_bills": fmt(bills), "difference": fmt(ledger - bills)}
