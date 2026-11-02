from decimal import Decimal as D
from pathlib import Path
import pandas as pd
import pytest
from app.books_db import connect
from app.checks import check1_entries_balance, check4_payables_equal_unpaid_bills
from app.expenses import (BillError, DuplicateBillError, SeparationOfDutiesError, add_vendor, approve_bill,
                          compare_with_csv, find_likely_duplicates, load_historical_bills, pay_bill, reject_bill,
                          spend_report, submit_bill)
from app.ledger import account_balance, load_chart

DATA = Path(__file__).resolve().parent.parent / "data"


def books():
    c = connect()
    load_chart(c, DATA / "chart_of_accounts.csv")
    add_vendor(c, "V-001", "Skyline Realty", 5101, 30)
    add_vendor(c, "V-002", "Cloud Co", 5104, 15)
    return c


def bill(c, amount=100000, date="2025-04-01", vendor="V-001", ref=None, **kw):
    return submit_bill(c, vendor, date, 5101, amount, 18, "EMP-0001", "D09", "Rent", ref, **kw)


def n_entries(c):
    return c.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"]


def status(c, eid):
    return c.execute("SELECT status FROM expenses WHERE expense_id=?", (eid,)).fetchone()["status"]


def test_submit_calculates_gst_and_posts_nothing():
    c = books()
    b = c.execute("SELECT * FROM expenses WHERE expense_id=?", (bill(c),)).fetchone()
    assert (b["gst_amount"], b["total_amount"], b["status"], b["due_date"]) == ("18000.00", "118000.00", "SUBMITTED", "2025-05-01")
    assert n_entries(c) == 0


def test_approval_posts_expense_gst_and_payable():
    c = books()
    e = bill(c)
    je = approve_bill(c, e, "EMP-0002")
    lines = {(r["account_code"], r["cost_center_department_id"]): (r["debit"], r["credit"])
             for r in c.execute("SELECT * FROM journal_lines WHERE entry_id=?", (je,))}
    assert lines == {(5101, "D09"): ("100000.00", "0.00"), (1200, None): ("18000.00", "0.00"), (2001, None): ("0.00", "118000.00")}
    assert status(c, e) == "APPROVED" and account_balance(c, 2001) == D("118000.00")


def test_same_person_cannot_create_and_approve():
    c = books()
    e = bill(c)
    with pytest.raises(SeparationOfDutiesError, match="cannot also approve"):
        approve_bill(c, e, "EMP-0001")          # EMP-0001 submitted it
    assert status(c, e) == "SUBMITTED" and n_entries(c) == 0   # nothing changed, nothing posted


def test_bill_cannot_be_paid_before_approval():
    c = books()
    e = bill(c)
    with pytest.raises(BillError, match="must be approved"):
        pay_bill(c, e, "2025-04-10")
    assert n_entries(c) == 0 and status(c, e) == "SUBMITTED"


def test_payment_clears_payable_only_and_expense_not_counted_twice():
    c = books()
    e = bill(c)
    approve_bill(c, e, "EMP-0002")
    pay_bill(c, e, "2025-04-10")
    assert account_balance(c, 2001) == D("0.00")                 # debt cleared
    assert account_balance(c, 5101) == D("100000.00")            # expense still counted once
    assert account_balance(c, 1200) == D("18000.00")
    assert account_balance(c, 1001) == D("-118000.00")           # cash went out once
    assert n_entries(c) == 2 and status(c, e) == "PAID"
    with pytest.raises(BillError, match="already paid"):
        pay_bill(c, e, "2025-04-11")
    assert check1_entries_balance(c)["ok"] and check4_payables_equal_unpaid_bills(c)["ok"]


def test_one_way_flow_and_rejection():
    c = books()
    e = bill(c)
    approve_bill(c, e, "EMP-0002")
    with pytest.raises(BillError, match="Only a SUBMITTED"):
        approve_bill(c, e, "EMP-0003")                           # cannot approve twice
    r = bill(c, 5000, "2025-06-01")
    reject_bill(c, r, "EMP-0002", "not ours")
    with pytest.raises(BillError):
        approve_bill(c, r, "EMP-0002")
    with pytest.raises(BillError):
        pay_bill(c, r, "2025-06-10")
    assert n_entries(c) == 1                                     # rejected bill never posted


def test_bad_bills_refused():
    c = books()
    with pytest.raises(BillError, match="more than zero"):
        bill(c, 0)
    with pytest.raises(BillError, match="not found"):
        bill(c, vendor="V-999")
    c.execute("UPDATE vendors SET is_active='N' WHERE vendor_id='V-002'")
    with pytest.raises(BillError, match="inactive"):
        bill(c, vendor="V-002")
    e = bill(c)
    approve_bill(c, e, "EMP-0002")
    with pytest.raises(BillError, match="before the bill date"):
        pay_bill(c, e, "2025-03-01")


# ---------------- duplicate detector ----------------
def test_duplicate_same_bill_number_is_flagged():
    c = books()
    bill(c, 100000, "2025-04-01", ref="BILL-77")
    with pytest.raises(DuplicateBillError, match="same bill number"):
        bill(c, 250000, "2025-09-01", ref=" bill-77 ")           # different amount and date, same number


def test_duplicate_same_amount_close_date_is_flagged():
    c = books()
    first = bill(c, 259330, "2025-07-01")
    with pytest.raises(DuplicateBillError) as e:
        bill(c, 257350, "2025-07-05")                            # 0.8% lower, 4 days later
    assert e.value.matches[0]["expense_id"] == first


def test_normal_recurring_bills_are_not_flagged():
    c = books()
    bill(c, 100000, "2025-04-01")
    bill(c, 100000, "2025-05-01")                                # monthly rent: 30 days apart
    bill(c, 100000, "2025-04-02", vendor="V-002")                # same amount, other vendor
    bill(c, 160000, "2025-04-03")                                # same vendor, very different amount
    assert c.execute("SELECT COUNT(*) n FROM expenses").fetchone()["n"] == 4


def test_duplicate_can_be_confirmed_and_rejected_bills_do_not_count():
    c = books()
    first = bill(c, 100000, "2025-04-01", ref="B1")
    bill(c, 100000, "2025-04-02", ref="B1", allow_duplicate=True)   # submitter confirmed it is real
    reject_bill(c, first, "EMP-0002")
    assert [m["expense_id"] for m in find_likely_duplicates(c, "V-001", "2025-04-01", 100000, "B1")] == ["EXP-00002"]


def test_spend_report_by_vendor_and_month():
    c = books()
    a = bill(c, 100000, "2025-04-01")
    b = bill(c, 50000, "2025-04-20", vendor="V-002")
    d = bill(c, 70000, "2025-05-02")
    bill(c, 1000, "2025-05-03", vendor="V-002")                  # still SUBMITTED: not in the report
    for x in (a, b, d):
        approve_bill(c, x, "EMP-0002")
    got = {(r["vendor_id"], r["month"]): r["total"] for r in spend_report(c)}
    assert got == {("V-001", "2025-04"): "118000.00", ("V-002", "2025-04"): "59000.00", ("V-001", "2025-05"): "82600.00"}


# ---------------- against the official data ----------------
def test_official_history_monthly_totals_match_csv_and_controls_find_14_self_approvals():
    c = connect()
    load_chart(c, DATA / "chart_of_accounts.csv")
    violations = load_historical_bills(c, DATA / "vendors.csv", DATA / "expenses.csv")
    table = compare_with_csv(c, DATA / "expenses.csv")
    assert len(table) == 18 and all(diff == 0 for _, _, _, diff in table)
    assert len(violations) == 14                                  # submitter == approver in the official data
    assert check1_entries_balance(c)["ok"] and check4_payables_equal_unpaid_bills(c)["ok"]
    assert n_entries(c) == 501 + 478                              # one entry per bill + one per payment
    df = pd.read_csv(DATA / "expenses.csv")
    pair = df[df.expense_id.isin(["EXP-00090", "EXP-00099"])]
    assert pair.vendor_id.nunique() == 1
    found = find_likely_duplicates(c, pair.vendor_id.iloc[0], pair.expense_date.iloc[1], pair.amount_excl_gst.iloc[1],
                                   pair.bill_reference.iloc[1], exclude_id="EXP-00099")
    assert [m["expense_id"] for m in found] == ["EXP-00090"]      # the one real near-duplicate in the data
