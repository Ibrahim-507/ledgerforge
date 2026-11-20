import sqlite3
from decimal import Decimal as D
from pathlib import Path
import pytest
from app.checks import check1_entries_balance
from app.books_db import connect
from app.ledger import (LedgerError, account_balance, create_journal_entry, load_chart, reverse_entry, update_entry)
from app.payroll_data import PayrollSource
from app.payroll_posting import post_payroll_run

DATA = Path(__file__).resolve().parent.parent / "data"


def fresh():
    c = connect()
    load_chart(c, DATA / "chart_of_accounts.csv")
    return c


def L(code, dr=0, cr=0):
    return {"account_code": code, "debit": dr, "credit": cr}


def count(c, t="journal_entries"):
    return c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"]


def test_unbalanced_entry_is_refused_with_clear_message():
    c = fresh()
    with pytest.raises(LedgerError, match="not balanced: total debits 100.00 != total credits 90.00"):
        create_journal_entry(c, "2025-04-05", "bad", [L(1001, 100), L(3001, cr=90)])
    assert count(c) == 0 and count(c, "journal_lines") == 0     # nothing written


def test_other_bad_entries_refused():
    c = fresh()
    for lines in ([L(1001, 100)],                                  # only one line
                  [L(1001, 100, 100), L(3001, cr=0)],              # both sides on one line
                  [L(1001, -5), L(3001, cr=-5)],                   # negative
                  [L(1001, 10), L(9999, cr=10)],                   # unknown account
                  [L(1000, 10), L(3001, cr=10)],                   # 1000 is a heading (group)
                  [L(1001, "10.001"), L(3001, cr="10.001")]):      # sub-paisa
        with pytest.raises(LedgerError):
            create_journal_entry(c, "2025-04-05", "bad", lines)
    assert count(c) == 0


def test_balanced_entry_posts_and_balances_by_date():
    c = fresh()
    create_journal_entry(c, "2025-04-05", "capital", [L(1001, 500000), L(3001, cr=500000)])
    create_journal_entry(c, "2025-05-10", "rent", [L(5101, 20000), L(1001, cr=20000)])
    assert account_balance(c, 1001, "2025-04-30") == D("500000.00")
    assert account_balance(c, 1001, "2025-05-31") == D("480000.00")
    assert account_balance(c, 3001) == D("500000.00")       # credit-normal account shows positive
    assert account_balance(c, 1000) == D("480000.00")       # heading adds up its children (1001 only here)
    assert check1_entries_balance(c)["ok"]


def test_posted_entry_cannot_be_edited_or_deleted():
    c = fresh()
    je = create_journal_entry(c, "2025-04-05", "capital", [L(1001, 100), L(3001, cr=100)])
    with pytest.raises(LedgerError, match="reversing entry"):
        update_entry(c, je, description="oops")
    for sql in ("UPDATE journal_entries SET description='x'", "DELETE FROM journal_entries",
                "UPDATE journal_lines SET debit='999.00'", "DELETE FROM journal_lines"):
        with pytest.raises(sqlite3.DatabaseError):               # the database itself refuses
            c.execute(sql)


def test_correction_by_reversal():
    c = fresh()
    je = create_journal_entry(c, "2025-04-05", "rent (wrong amount)", [L(5101, 25000), L(1001, cr=25000)])
    create_journal_entry(c, "2025-04-05", "capital", [L(1001, 100000), L(3001, cr=100000)])
    rev = reverse_entry(c, je, "2025-04-06", "wrong amount")
    assert account_balance(c, 5101) == D("0.00") and account_balance(c, 1001) == D("100000.00")
    assert count(c) == 3                                         # history kept: original + reversal
    with pytest.raises(LedgerError, match="already posted"):     # cannot reverse the same entry twice
        reverse_entry(c, je, "2025-04-07")
    with pytest.raises(LedgerError, match="reversal cannot itself"):
        reverse_entry(c, rev, "2025-04-07")


def test_payroll_posting_equals_run_total_and_is_idempotent():
    c = fresh()
    src = PayrollSource(str(DATA))
    je = post_payroll_run(c, src, "PR-2025-04")
    e = c.execute("SELECT * FROM journal_entries WHERE entry_id=?", (je,)).fetchone()
    assert e["total_debit"] == e["total_credit"] == "53363392.08"    # = payroll_runs.total_employer_cost
    assert account_balance(c, 2100) == D("46035111.16")               # net salaries payable = total_net
    with pytest.raises(LedgerError, match="already posted"):
        post_payroll_run(c, src, "PR-2025-04")
    assert check1_entries_balance(c)["ok"]
