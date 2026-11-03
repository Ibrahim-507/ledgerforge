from decimal import Decimal as D
from pathlib import Path
import pandas as pd
import pytest
from app.books_db import connect
from app.checks import check1_entries_balance, check2_payroll_matches_ledger
from app.ledger import LedgerError, account_balance, create_journal_entry, load_chart
from app.payroll_data import PayrollSource
from app.payroll_runs import (RunError, RunSeparationError, approve_run, create_run, pay_run, process_run,
                              reverse_run, run_all_months)

DATA = Path(__file__).resolve().parent.parent / "data"
src = PayrollSource(str(DATA))
official = pd.read_csv(DATA / "payroll_runs.csv").set_index("run_id")
RUN_BY, APPROVER = "U-0237", "U-0099"


def books():
    c = connect()
    load_chart(c, DATA / "chart_of_accounts.csv")
    return c


def processed(c, month="2025-04"):
    rid = create_run(c, f"{month}-01", RUN_BY)
    process_run(c, src, rid)
    return rid


def n_run_entries(c, run_id):
    return c.execute("SELECT COUNT(*) n FROM journal_entries WHERE source_type='PAYROLL_RUN' AND source_id=?", (run_id,)).fetchone()["n"]


def row(c, run_id):
    return c.execute("SELECT * FROM payroll_runs WHERE run_id=?", (run_id,)).fetchone()


def test_create_twice_gives_one_run_with_the_idempotency_key():
    c = books()
    a, b = create_run(c, "2025-04-01", RUN_BY), create_run(c, "2025-04-17", RUN_BY)   # double click
    assert a == b == "PR-2025-04"
    assert c.execute("SELECT COUNT(*) n FROM payroll_runs").fetchone()["n"] == 1
    assert row(c, a)["idempotency_key"] == "payroll:2025-04:ZNT" and row(c, a)["status"] == "DRAFT"


def test_process_uses_the_engine_for_every_employee_and_posts_nothing():
    c = books()
    rid = processed(c)
    r, o = row(c, rid), official.loc[rid]
    assert (r["status"], r["employees_paid"]) == ("PROCESSED", int(o.employees_paid)) == ("PROCESSED", 386)
    for col in ("total_gross", "total_deductions", "total_net", "total_employer_contributions", "total_employer_cost"):
        assert D(r[col]) == D(str(o[col]))
    assert c.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"] == 0
    assert process_run(c, src, rid)["already"] is True                       # processing twice rewrites nothing
    assert c.execute("SELECT COUNT(*) n FROM payroll_items WHERE run_id=?", (rid,)).fetchone()["n"] == 386


def test_approval_posts_one_entry_and_stores_its_id_on_the_run():
    c = books()
    rid = processed(c)
    je = approve_run(c, rid, APPROVER)
    r = row(c, rid)
    assert (r["status"], r["approved_by"], r["journal_entry_id"]) == ("APPROVED", APPROVER, je)
    e = c.execute("SELECT * FROM journal_entries WHERE entry_id=?", (je,)).fetchone()
    assert e["total_debit"] == e["total_credit"] == "53363392.08" and e["source_id"] == rid
    assert account_balance(c, 2100) == D("46035111.16")                      # net salaries payable = run total_net


def test_double_click_on_approve_posts_only_once():
    c = books()
    rid = processed(c)
    first, second = approve_run(c, rid, APPROVER), approve_run(c, rid, APPROVER)
    assert first == second and n_run_entries(c, rid) == 1
    with pytest.raises(LedgerError, match="already posted"):                 # even a direct second post is blocked by the database
        create_journal_entry(c, "2025-04-30", "again", [{"account_code": 1001, "debit": 1}, {"account_code": 3001, "credit": 1}],
                             source_type="PAYROLL_RUN", source_id=rid)


def test_approver_must_not_be_the_person_who_ran_payroll():
    c = books()
    rid = processed(c)
    with pytest.raises(RunSeparationError, match="cannot also approve"):
        approve_run(c, rid, RUN_BY)
    assert row(c, rid)["status"] == "PROCESSED" and n_run_entries(c, rid) == 0


def test_flow_order_is_enforced():
    c = books()
    rid = create_run(c, "2025-04-01", RUN_BY)
    with pytest.raises(RunError, match="Only a PROCESSED"):
        approve_run(c, rid, APPROVER)                                         # draft cannot be approved
    process_run(c, src, rid)
    with pytest.raises(RunError, match="must be approved"):
        pay_run(c, rid)                                                       # cannot pay before approval
    approve_run(c, rid, APPROVER)
    pay_run(c, rid, APPROVER)
    assert pay_run(c, rid) == row(c, rid)["payment_entry_id"]                 # paying twice returns the same entry
    assert c.execute("SELECT COUNT(*) n FROM journal_entries WHERE source_type='SALARY_PAYMENT'").fetchone()["n"] == 1
    assert account_balance(c, 2100) == D("0.00")                              # net pay owed is now cleared
    with pytest.raises(RunError, match="already paid"):
        reverse_run(c, rid, "2025-05-02", "oops")


def test_failed_ledger_post_rolls_back_completely_and_can_be_retried():
    c = books()
    rid = processed(c)
    c.execute("UPDATE chart_of_accounts SET is_active='N' WHERE account_code=5003")   # make the post fail
    c.commit()
    with pytest.raises(LedgerError, match="inactive"):
        approve_run(c, rid, APPROVER)
    r = row(c, rid)
    assert r["status"] == "PROCESSED" and r["journal_entry_id"] is None and "inactive" in r["error_message"]
    assert c.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"] == 0
    assert c.execute("SELECT COUNT(*) n FROM journal_lines").fetchone()["n"] == 0     # no half-written entry
    c.execute("UPDATE chart_of_accounts SET is_active='Y' WHERE account_code=5003")
    c.commit()
    approve_run(c, rid, APPROVER)                                                     # retry works
    assert row(c, rid)["status"] == "APPROVED" and row(c, rid)["error_message"] is None and n_run_entries(c, rid) == 1


def test_reversal_cancels_the_posted_run_and_the_month_can_be_rerun():
    c = books()
    rid = processed(c)
    je = approve_run(c, rid, APPROVER)
    reverse_run(c, rid, "2025-05-02", "wrong variable pay", "U-0099")
    assert row(c, rid)["status"] == "REVERSED"
    for code in (5001, 5003, 5004, 2100, 2110, 2130):
        assert account_balance(c, code) == D("0.00")                          # everything cancelled out
    assert c.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"] == 2   # history kept
    with pytest.raises(RunError, match="already reversed"):
        reverse_run(c, rid, "2025-05-03", "again")
    again = create_run(c, "2025-04-01", RUN_BY)                               # corrected run for the same month
    assert again == "PR-2025-04-R1" and row(c, again)["idempotency_key"] == "payroll:2025-04:ZNT:R1"
    process_run(c, src, again)
    approve_run(c, again, APPROVER)
    assert account_balance(c, 2100) == D("46035111.16")                       # counted once, not twice
    assert check1_entries_balance(c)["ok"] and check2_payroll_matches_ledger(c)["ok"]


def test_draft_and_processed_runs_cannot_be_reversed():
    c = books()
    rid = create_run(c, "2025-04-01", RUN_BY)
    with pytest.raises(RunError, match="Only an APPROVED"):
        reverse_run(c, rid, "2025-05-01", "x")


def test_all_18_months_post_once_and_check2_is_zero_everywhere():
    c = books()
    ids = run_all_months(c, src)
    assert run_all_months(c, src) == ids                                       # running every month a second time
    assert len(ids) == 18 and c.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"] == 18 + 17
    k = check2_payroll_matches_ledger(c)
    assert k["ok"] and k["runs"] == 18 and all(d["difference"] == "0.00" for d in k["detail"])
    assert check1_entries_balance(c)["ok"]
    jl = pd.read_csv(DATA / "journal_lines.csv")
    for r in c.execute("SELECT * FROM payroll_runs ORDER BY period_start"):
        o = official.loc[r["run_id"]]
        assert r["journal_entry_id"] and r["idempotency_key"] == o.idempotency_key and r["employees_paid"] == o.employees_paid
        assert r["status"] == ("APPROVED" if str(o.status).startswith("POSTED") else "PAID")
        mine = {(x["account_code"], x["cost_center_department_id"]): D(x["debit"]) - D(x["credit"])
                for x in c.execute("SELECT * FROM journal_lines WHERE entry_id=?", (r["journal_entry_id"],))}
        off = {(x.account_code, None if pd.isna(x.cost_center_department_id) else x.cost_center_department_id):
               D(str(x.debit)) - D(str(x.credit)) for x in jl[jl.entry_id == o.journal_entry_id].itertuples()}
        assert mine == off                                                      # same lines as the official posting
