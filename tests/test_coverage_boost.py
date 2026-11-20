"""Tests for the least-covered code: user seeding, the role table, the tax explanation, ledger printing and the error branches of
invoices, bills and payroll runs."""
from pathlib import Path
import pytest
from app.auth_store import authenticate, seed_users
from app.books_db import connect
from app.expenses import BillError, add_vendor, approve_bill, pay_bill, reject_bill, submit_bill
from app.invoicing import InvoiceError, cancel_invoice, create_invoice, record_payment, send_invoice
from app.ledger import LedgerError, account_balance, create_journal_entry, entry_as_table, load_chart, reverse_entry
from app.payroll_runs import RunError, approve_run, create_run, pay_run, reverse_run
from app.permissions import role_table_markdown
from app.tax_config import load_rules, seed_rules
from app.tax_explain import explain_text, explain_tds

DATA = Path(__file__).resolve().parent.parent / "data"


def books():
    c = connect()
    load_chart(c, DATA / "chart_of_accounts.csv")
    c.execute("INSERT INTO clients(client_id, client_name, payment_terms_days) VALUES ('CL-001','Alpha Ltd',30)")
    add_vendor(c, "V-001", "Skyline Realty", 5101, 30)
    c.commit()
    return c


def L(code, dr=0, cr=0):
    return {"account_code": code, "debit": dr, "credit": cr}


# ---------------- users ----------------
def test_seed_users_loads_demo_users_once_and_only_active_when_asked():
    c = connect()
    assert seed_users(c, DATA / "users.csv", "Demo@12345", limit=4, active_only=True) == 4
    assert seed_users(c, DATA / "users.csv", "Demo@12345", limit=4, active_only=True) == 0        # nothing is added twice
    rows = c.execute("SELECT username, password_hash, is_active FROM users").fetchall()
    assert all(r["is_active"] == "Y" and r["password_hash"].startswith("scrypt$") and "Demo@12345" not in r["password_hash"] for r in rows)
    assert authenticate(c, rows[0]["username"], "Demo@12345")["username"] == rows[0]["username"]


# ---------------- permissions table ----------------
def test_role_table_marks_public_routes_and_routes_without_a_rule():
    table = role_table_markdown([("POST", "/api/v1/auth/login"), ("GET", "/brand-new"), ("GET", "/payslips/{employee_id}/{run_id}")])
    assert "| POST | /auth/login | public |" in table
    assert "| GET | /brand-new | **NO RULE** |" in table
    assert "own only" in table                                                                    # an employee sees only their own payslip


# ---------------- tax explanation ----------------
def test_tax_explanation_text_shows_every_step():
    c = connect()
    seed_rules(c, str(DATA))
    rates, params, slabs = load_rules(c)
    text = explain_text(explain_tds(144460, "34670.40", 30, 30, slabs["FY2025-26"], params))
    for part in ("taxable income", "standard deduction", "slab", "cess", "MONTHLY TDS", "18,625.79"):
        assert part in text, part


# ---------------- ledger ----------------
def test_printing_an_entry_and_ledger_error_branches():
    c = books()
    je = create_journal_entry(c, "2025-04-01", "capital", [L(1001, 100), L(3001, cr=100)])
    assert "TOTAL" in entry_as_table(c, je) and "Software" not in entry_as_table(c, je)
    big = create_journal_entry(c, "2025-04-02", "many lines", [L(1001, 1) for _ in range(34)] + [L(3001, cr=34)])
    assert "more lines" in entry_as_table(c, big)                                                # long entries are shortened
    with pytest.raises(LedgerError, match="does not exist"):
        account_balance(c, 9999)
    with pytest.raises(LedgerError, match="not found"):
        reverse_entry(c, "JE-999999", "2025-04-05")
    with pytest.raises(LedgerError, match="at least two"):
        create_journal_entry(c, "2025-04-03", "one line", [L(1001, 5)])


# ---------------- invoices ----------------
def test_invoice_error_branches():
    c = books()
    item = {"description": "x", "quantity": 1, "unit_price": 1000, "revenue_account": 4003}
    with pytest.raises(InvoiceError, match="Client CL-999 not found"):
        create_invoice(c, "CL-999", "2025-06-01", [item])
    with pytest.raises(InvoiceError, match="at least one item"):
        create_invoice(c, "CL-001", "2025-06-01", [])
    with pytest.raises(InvoiceError, match="quantity must be above 0"):
        create_invoice(c, "CL-001", "2025-06-01", [{**item, "quantity": 0}])
    with pytest.raises(InvoiceError, match="not found"):
        send_invoice(c, "INV-99999")
    inv = create_invoice(c, "CL-001", "2025-06-01", [item])
    send_invoice(c, inv)
    with pytest.raises(InvoiceError, match="more than zero"):
        record_payment(c, inv, "2025-06-02", 0)
    record_payment(c, inv, "2025-06-02", 1180)
    with pytest.raises(InvoiceError, match="has payments"):
        cancel_invoice(c, inv, "2025-06-03")
    with pytest.raises(InvoiceError, match="Cannot take a payment"):
        record_payment(c, inv, "2025-06-04", 10)


# ---------------- vendor bills ----------------
def test_bill_error_branches():
    c = books()
    with pytest.raises(BillError, match="not found"):
        approve_bill(c, "EXP-99999", "EMP-2")
    with pytest.raises(BillError, match="who submitted"):
        submit_bill(c, "V-001", "2025-04-01", 5101, 1000, 18, "")
    e = submit_bill(c, "V-001", "2025-04-01", 5101, 1000, 18, "EMP-1")
    with pytest.raises(BillError, match="who approved"):
        approve_bill(c, e, "")
    reject_bill(c, e, "EMP-2", "not ours")
    with pytest.raises(BillError, match="Only a SUBMITTED"):
        reject_bill(c, e, "EMP-2", "again")
    with pytest.raises(BillError, match="must be approved"):
        pay_bill(c, e, "2025-04-10")


# ---------------- payroll runs ----------------
def test_payroll_run_error_branches():
    c = books()
    with pytest.raises(RunError, match="not found"):
        approve_run(c, "PR-1999-01", "U-0099")
    with pytest.raises(RunError, match="not found"):
        pay_run(c, "PR-1999-01")
    rid = create_run(c, "2025-04-01", "U-0237")
    with pytest.raises(RunError, match="Only a PROCESSED"):
        approve_run(c, rid, "")                                   # the status is checked first
    with pytest.raises(RunError, match="Only an APPROVED"):
        reverse_run(c, rid, "2025-05-01", "")
    c.execute("UPDATE payroll_runs SET status='APPROVED' WHERE run_id=?", (rid,))
    with pytest.raises(RunError, match="needs a reason"):
        reverse_run(c, rid, "2025-05-01", "")
