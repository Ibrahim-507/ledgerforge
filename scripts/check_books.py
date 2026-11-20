"""Prove Tasks 9-10 against the official data. Run:  python -m scripts.check_books"""
import sys
from decimal import Decimal as D
import pandas as pd
from app.books_db import connect, dec, fmt
from app.checks import check1_entries_balance, check3_receivable_equals_open_invoices
from app.exporter import export_tables
from app.invoicing import receivables_list
from app.ledger import account_balance, entry_as_table, load_chart
from app.payroll_data import PayrollSource
from app.payroll_posting import post_payroll_run
from app.seed_official import import_official

data = sys.argv[1] if len(sys.argv) > 1 else "data"

print("=== A. Official books loaded into my schema ===")
conn = connect()
import_official(conn, data)
print("Check 1 (every entry balances):", check1_entries_balance(conn))
print("Check 3 (receivable = open invoices):", check3_receivable_equals_open_invoices(conn))
print("Bank balance 30 Sep 2026:", fmt(account_balance(conn, 1001, "2026-09-30")))

print("\n=== B. Receivables list, top 3 clients ===")
for c in receivables_list(conn)[:3]:
    print(f"{c['client_id']} {c['client_name']:<32} owes {fmt(c['total_due']):>16}  ({len(c['invoices'])} invoices)")
inv = pd.read_csv(f"{data}/invoices.csv")
op = inv[inv.status.isin(["SENT", "OVERDUE", "PARTIALLY_PAID"])].groupby("client_id").balance_due.sum()
print("Hand check straight from invoices.csv:", {k: int(v) for k, v in op.sort_values(ascending=False).head(3).items()})

print("\n=== C. My payroll posting vs official journal entries (all 18 runs) ===")
src = PayrollSource(data)
mine = connect()
load_chart(mine, f"{data}/chart_of_accounts.csv")
runs = pd.read_csv(f"{data}/payroll_runs.csv")
lines = pd.read_csv(f"{data}/journal_lines.csv")
ok = 0
for run in runs.itertuples():
    je = post_payroll_run(mine, src, run.run_id)
    got = {(r["account_code"], r["cost_center_department_id"]): dec(r["debit"]) - dec(r["credit"])
           for r in mine.execute("SELECT * FROM journal_lines WHERE entry_id=?", (je,))}
    off = lines[lines.entry_id == run.journal_entry_id]
    exp = {(r.account_code, None if pd.isna(r.cost_center_department_id) else r.cost_center_department_id):
           D(str(r.debit)) - D(str(r.credit)) for r in off.itertuples()}
    same = got == exp
    ok += same
    if not same:
        diff = {k: (got.get(k), exp.get(k)) for k in set(got) | set(exp) if got.get(k) != exp.get(k)}
        print(run.run_id, "DIFF", list(diff.items())[:3])
print(f"{ok}/{len(runs)} payroll runs post exactly like the official entries")
print("Check 1 on my own ledger:", check1_entries_balance(mine))

print("\n=== D. Sample journal entry (April 2025 payroll, first lines) ===")
print(entry_as_table(mine, "JE-000001"))
export_tables(mine, "my_export")
print("Exported my tables to my_export/ ->  python verify_ledgerforge.py checks --data my_export/")
