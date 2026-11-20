"""Task 15 evidence:  python -m scripts.task15_run
Builds the trial balance, profit and loss and balance sheet from the official ledger and compares them with an independent
calculation straight from the CSV files. Saves my_trial_balance.csv for the official checker."""
import sys
import pandas as pd
from app.books_db import connect
from app.financials import balance_sheet, profit_and_loss, trial_balance, trial_balance_csv
from app.seed_official import import_official

DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
AS_OF = "2026-09-30"
conn = connect()
import_official(conn, DATA)
f = lambda x: f"{float(x):>18,.2f}"

print("=== Trial balance (all dates) ===")
tb = trial_balance(conn)
for r in tb["rows"]:
    print(f"{r['account_code']:<6}{r['account_name']:<34}{f(r['closing_debit'])}{f(r['closing_credit'])}")
print(f"{'TOTAL':<40}{f(tb['total_debit'])}{f(tb['total_credit'])}   difference {tb['difference']}   balanced: {tb['balanced']}")

print("\n=== Profit and loss (all dates) ===")
pl = profit_and_loss(conn)
for sec, name in (("income", "INCOME"), ("expenses", "EXPENSES")):
    print(name)
    for r in pl[sec]["rows"]:
        print(f"  {r['account_code']:<6}{r['account_name']:<34}{f(r['amount'])}")
    print(f"  {'Total ' + name.lower():<40}{f(pl[sec]['total'])}")
print(f"NET PROFIT {f(pl['net_profit'])}")

print(f"\n=== Balance sheet at {AS_OF} ===")
bs = balance_sheet(conn, AS_OF)
for sec in ("assets", "liabilities", "equity"):
    print(sec.upper())
    for r in bs[sec]["rows"]:
        print(f"  {r['account_code']:<6}{r['account_name']:<34}{f(r['amount'])}")
    print(f"  {'Total ' + sec:<40}{f(bs[sec]['total'])}")
    if sec == "equity":
        print(f"  {'Current profit (not yet closed)':<40}{f(bs['current_profit'])}")
print(f"Assets {f(bs['total_assets'])}   Liabilities + Equity + profit {f(bs['total_liabilities_and_equity'])}   difference {bs['difference']}   balanced: {bs['balanced']}")

print("\n=== Independent check straight from the CSV files ===")
jl = pd.read_csv(f"{DATA}/journal_lines.csv").merge(pd.read_csv(f"{DATA}/chart_of_accounts.csv")[["account_code", "account_type"]], on="account_code")
inc, exp = jl[jl.account_type == "INCOME"], jl[jl.account_type == "EXPENSE"]
ci, ce = round(inc.credit.sum() - inc.debit.sum(), 2), round(exp.debit.sum() - exp.credit.sum(), 2)
print(f"{'':<12}{'My report':>20}{'CSV by hand':>20}{'Same?':>8}")
for name, mine, theirs in (("Revenue", pl["total_income"], ci), ("Expenses", pl["total_expenses"], ce), ("Profit", pl["net_profit"], round(ci - ce, 2))):
    print(f"{name:<12}{float(mine):>20,.2f}{theirs:>20,.2f}{str(float(mine) == theirs):>8}")

trial_balance_csv(tb, "my_trial_balance.csv")
print("\nSaved my_trial_balance.csv. Now run the OFFICIAL checks and compare with the numbers above:")
print("  python verify_ledgerforge.py summary --data csv")
print("  python verify_ledgerforge.py trial-balance my_trial_balance.csv --data csv")
