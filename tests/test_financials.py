from decimal import Decimal as D
from pathlib import Path
import pandas as pd
from app.books_db import connect
from app.financials import balance_sheet, profit_and_loss, trial_balance, trial_balance_csv
from app.ledger import create_journal_entry, load_chart
from app.seed_official import import_official

DATA = Path(__file__).resolve().parent.parent / "data"


def L(code, dr=0, cr=0):
    return {"account_code": code, "debit": dr, "credit": cr}


def small_books():
    c = connect()
    load_chart(c, DATA / "chart_of_accounts.csv")
    create_journal_entry(c, "2025-04-01", "capital", [L(1001, 1000000), L(3001, cr=1000000)])
    create_journal_entry(c, "2025-04-10", "invoice", [L(1100, 118000), L(4003, cr=100000), L(2200, cr=18000)])
    create_journal_entry(c, "2025-04-20", "rent bill", [L(5101, 30000), L(1200, 5400), L(2001, cr=35400)])
    create_journal_entry(c, "2025-05-05", "customer pays", [L(1001, 118000), L(1100, cr=118000)])
    create_journal_entry(c, "2025-05-15", "rent paid and booked", [L(5101, 30000), L(1200, 5400), L(1001, cr=35400)])
    return c


def test_trial_balance_balances_and_shows_opening_period_and_closing():
    c = small_books()
    tb = trial_balance(c, "2025-05-01", "2025-05-31")
    assert tb["balanced"] and tb["difference"] == "0.00"
    bank = next(r for r in tb["rows"] if r["account_code"] == 1001)
    assert (bank["opening_balance"], bank["period_debit"], bank["period_credit"], bank["balance"]) == ("1000000.00", "118000.00", "35400.00", "1082600.00")
    assert bank["closing_debit"] == "1082600.00" and bank["closing_credit"] == "0.00"
    rent = next(r for r in tb["rows"] if r["account_code"] == 5101)
    assert rent["opening_balance"] == "30000.00" and rent["balance"] == "60000.00"
    assert not any(r["account_code"] in (1000, 2000, 3000, 4000, 5000) for r in tb["rows"])   # headings never listed
    assert tb["total_debit"] == tb["total_credit"]


def test_profit_and_loss_by_period():
    c = small_books()
    april, may, both = profit_and_loss(c, "2025-04-01", "2025-04-30"), profit_and_loss(c, "2025-05-01", "2025-05-31"), profit_and_loss(c)
    assert (april["total_income"], april["total_expenses"], april["net_profit"]) == ("100000.00", "30000.00", "70000.00")
    assert (may["total_income"], may["total_expenses"], may["net_profit"]) == ("0.00", "30000.00", "-30000.00")
    assert both["net_profit"] == "40000.00" and both["income"]["rows"][0]["account_code"] == 4003
    assert both["expenses"]["headings"] == [{"account_code": 5000, "account_name": "Expenses", "subtotal": "60000.00"}]


def test_balance_sheet_balances_and_group_accounts_are_not_counted_twice():
    c = small_books()
    bs = balance_sheet(c, "2025-05-31")
    assert bs["total_assets"] == "1093400.00"                    # bank 1,082,600 + GST input 10,800
    assert bs["total_liabilities"] == "53400.00" and bs["total_equity"] == "1000000.00" and bs["current_profit"] == "40000.00"
    assert bs["total_liabilities_and_equity"] == "1093400.00" and bs["balanced"] and bs["difference"] == "0.00"
    assert sum(D(r["amount"]) for r in bs["assets"]["rows"]) == D(bs["total_assets"])          # rows add up; no heading in them
    assert [h["subtotal"] for h in bs["assets"]["headings"]] == ["1093400.00"]


def test_contra_asset_reduces_assets_and_the_sheet_still_balances():
    c = small_books()
    create_journal_entry(c, "2025-05-31", "depreciation", [L(5201, 10000), L(1590, cr=10000)])
    bs = balance_sheet(c, "2025-05-31")
    assert bs["total_assets"] == "1083400.00" and bs["balanced"]
    assert next(r for r in bs["assets"]["rows"] if r["account_code"] == 1590)["amount"] == "-10000.00"


def test_balance_sheet_as_of_an_earlier_date_ignores_later_entries():
    c = small_books()
    bs = balance_sheet(c, "2025-04-30")
    assert bs["total_assets"] == "1123400.00" and bs["balanced"]  # bank 1,000,000 + receivable 118,000 + GST 5,400


def test_trial_balance_file_for_the_official_checker(tmp_path):
    c = small_books()
    path = trial_balance_csv(trial_balance(c), tmp_path / "tb.csv")
    df = pd.read_csv(path)
    assert {"account_code", "debit", "credit", "balance"} <= set(df.columns)
    assert round(df.debit.sum(), 2) == round(df.credit.sum(), 2)


# ---------------- the official books ----------------
def official_books():
    c = connect()
    import_official(c, str(DATA))
    return c


def test_official_reports_match_an_independent_calculation():
    c = official_books()
    jl = pd.read_csv(DATA / "journal_lines.csv").merge(pd.read_csv(DATA / "chart_of_accounts.csv")[["account_code", "account_type"]], on="account_code")
    inc = jl[jl.account_type == "INCOME"]
    exp = jl[jl.account_type == "EXPENSE"]
    income = round(inc.credit.sum() - inc.debit.sum(), 2)
    expenses = round(exp.debit.sum() - exp.credit.sum(), 2)
    pl = profit_and_loss(c)
    assert float(pl["total_income"]) == income and float(pl["total_expenses"]) == expenses
    assert float(pl["net_profit"]) == round(income - expenses, 2) == 224683587.58


def test_official_trial_balance_has_zero_difference_and_the_balance_sheet_balances_at_every_month_end():
    c = official_books()
    tb = trial_balance(c)
    assert tb["balanced"] and tb["total_debit"] == tb["total_credit"] == "1518309423.07"
    for month_end in pd.date_range("2025-04-30", "2026-09-30", freq="ME"):
        bs = balance_sheet(c, month_end.date())
        assert bs["balanced"], (month_end, bs["difference"])
    final = balance_sheet(c, "2026-09-30")
    assert (final["total_assets"], final["total_liabilities"], final["total_equity"]) == ("463762958.65", "77499607.07", "161579764.00")
