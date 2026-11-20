from decimal import Decimal as D
from pathlib import Path
import pytest
from app.checks import check1_entries_balance, check3_receivable_equals_open_invoices
from app.books_db import connect
from app.invoicing import (InvoiceError, cancel_invoice, create_invoice, mark_overdue, receivables_list,
                           record_payment, send_invoice)
from app.ledger import account_balance, load_chart

DATA = Path(__file__).resolve().parent.parent / "data"


def books():
    c = connect()
    load_chart(c, DATA / "chart_of_accounts.csv")
    for cid, name, terms in [("CL-001", "Alpha Ltd", 30), ("CL-002", "Beta Ltd", 45), ("CL-003", "Gamma Ltd", 30)]:
        c.execute("INSERT INTO clients(client_id, client_name, payment_terms_days) VALUES (?,?,?)", (cid, name, terms))
    c.commit()
    return c


def invoice(c, client="CL-001", date="2025-06-01", amount=100000, rate=18):
    return create_invoice(c, client, date, [{"description": "Consulting", "quantity": 1, "unit_price": amount,
                                             "revenue_account": 4003}], gst_rate_percent=rate)


def n_entries(c):
    return c.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"]


def test_gst_total_and_due_date():
    c = books()
    i = c.execute("SELECT * FROM invoices WHERE invoice_id=?", (invoice(c, amount=1583500),)).fetchone()
    assert (i["gst_amount"], i["total_amount"], i["balance_due"], i["status"]) == ("285030.00", "1868530.00", "1868530.00", "DRAFT")
    assert i["due_date"] == "2025-07-01"


def test_draft_never_posts():
    c = books()
    invoice(c)
    assert n_entries(c) == 0 and account_balance(c, 1100) == D("0")
    assert check3_receivable_equals_open_invoices(c)["ok"]


def test_send_posts_receivable_income_and_gst():
    c = books()
    i = invoice(c)
    je = send_invoice(c, i)
    lines = {r["account_code"]: (r["debit"], r["credit"]) for r in
             c.execute("SELECT * FROM journal_lines WHERE entry_id=?", (je,))}
    assert lines == {1100: ("118000.00", "0.00"), 4003: ("0.00", "100000.00"), 2200: ("0.00", "18000.00")}
    assert account_balance(c, 1100) == D("118000.00")
    assert check1_entries_balance(c)["ok"] and check3_receivable_equals_open_invoices(c)["ok"]
    with pytest.raises(InvoiceError):              # cannot send twice
        send_invoice(c, i)


def test_zero_gst_invoice_has_two_lines():
    c = books()
    je = send_invoice(c, invoice(c, rate=0))
    assert c.execute("SELECT COUNT(*) n FROM journal_lines WHERE entry_id=?", (je,)).fetchone()["n"] == 2


def test_payment_reduces_balance_and_status_flow():
    c = books()
    i = invoice(c)
    with pytest.raises(InvoiceError):              # draft cannot take a payment
        record_payment(c, i, "2025-06-10", 1000)
    send_invoice(c, i)
    record_payment(c, i, "2025-06-10", 50000)
    row = c.execute("SELECT * FROM invoices WHERE invoice_id=?", (i,)).fetchone()
    assert (row["status"], row["amount_paid"], row["balance_due"]) == ("PARTIALLY_PAID", "50000.00", "68000.00")
    assert account_balance(c, 1100) == D("68000.00") and account_balance(c, 1001) == D("50000.00")
    assert check3_receivable_equals_open_invoices(c)["ok"]
    with pytest.raises(InvoiceError, match="more than the balance"):
        record_payment(c, i, "2025-06-11", 70000)
    record_payment(c, i, "2025-06-12", 68000)
    row = c.execute("SELECT * FROM invoices WHERE invoice_id=?", (i,)).fetchone()
    assert (row["status"], row["balance_due"]) == ("PAID", "0.00")
    assert account_balance(c, 1100) == D("0.00") and check3_receivable_equals_open_invoices(c)["ok"]


def test_cancel_draft_posts_nothing():
    c = books()
    i = invoice(c)
    cancel_invoice(c, i, "2025-06-02")
    assert n_entries(c) == 0
    assert c.execute("SELECT status FROM invoices").fetchone()["status"] == "CANCELLED"
    with pytest.raises(InvoiceError):
        send_invoice(c, i)                          # a cancelled invoice never posts
    with pytest.raises(InvoiceError):
        cancel_invoice(c, i, "2025-06-03")


def test_cancel_sent_invoice_posts_a_reversal():
    c = books()
    i = invoice(c)
    send_invoice(c, i)
    cancel_invoice(c, i, "2025-06-05", "sent by mistake")
    assert n_entries(c) == 2                        # original + reversal: history kept
    assert account_balance(c, 1100) == D("0.00") and account_balance(c, 4003) == D("0.00") and account_balance(c, 2200) == D("0.00")
    assert check1_entries_balance(c)["ok"] and check3_receivable_equals_open_invoices(c)["ok"]


def test_cannot_cancel_invoice_with_payment():
    c = books()
    i = invoice(c)
    send_invoice(c, i)
    record_payment(c, i, "2025-06-10", 1000)
    with pytest.raises(InvoiceError, match="credit note"):
        cancel_invoice(c, i, "2025-06-11")


def test_overdue_and_receivables_list_for_three_clients():
    c = books()
    a1, a2 = invoice(c, "CL-001", "2025-06-01", 100000), invoice(c, "CL-001", "2025-06-15", 50000)
    b1 = invoice(c, "CL-002", "2025-06-01", 200000)
    g1 = invoice(c, "CL-003", "2025-08-01", 10000)           # still a draft: must not appear
    for i in (a1, a2, b1):
        send_invoice(c, i)
    record_payment(c, a2, "2025-06-20", 20000)
    assert mark_overdue(c, "2025-07-10") == [a1]               # due 2025-07-01; a2 is partly paid; b1 due 2025-07-16
    rec = {r["client_id"]: r for r in receivables_list(c)}
    assert set(rec) == {"CL-001", "CL-002"}
    assert rec["CL-001"]["total_due"] == D("118000.00") + D("39000.00")   # 100000*1.18 + (59000-20000)
    assert rec["CL-002"]["total_due"] == D("236000.00")
    assert check3_receivable_equals_open_invoices(c)["ok"]
