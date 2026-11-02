"""Task 11 evidence:  python -m scripts.task11_report
Replays all 501 official bills through MY approval flow, then prints the monthly comparison table,
the self-approval findings, the duplicate-detector result, check 1/4 and a sample bill with its entries."""
from app.books_db import connect
from app.checks import check1_entries_balance, check4_payables_equal_unpaid_bills
from app.expenses import compare_with_csv, find_likely_duplicates, load_historical_bills, spend_report
from app.ledger import entry_as_table, load_chart
import pandas as pd

DATA = "data"
c = connect()
load_chart(c, f"{DATA}/chart_of_accounts.csv")
viol = load_historical_bills(c, f"{DATA}/vendors.csv", f"{DATA}/expenses.csv")

print("=== Monthly totals: my books vs expenses.csv ===")
print(f"{'Month':<9}{'My books':>18}{'CSV':>18}{'Difference':>12}")
for m, mine, csv, diff in compare_with_csv(c, f"{DATA}/expenses.csv"):
    print(f"{m:<9}{mine:>18,.2f}{csv:>18,.2f}{diff:>12,.2f}")

print("\n=== Checks ===")
print("Check 1 (entries balance):", check1_entries_balance(c))
print("Check 4 (payables = unpaid bills):", check4_payables_equal_unpaid_bills(c))

print(f"\n=== Separation-of-duties findings: {len(viol)} official bills approved by their own submitter ===")
for eid, who, amt in viol:
    print(f"  {eid}  {who}  {amt:,.2f}")

print("\n=== Duplicate detector on the official data ===")
df = pd.read_csv(f"{DATA}/expenses.csv")
for r in df.itertuples():
    m = find_likely_duplicates(c, r.vendor_id, r.expense_date, r.amount_excl_gst, r.bill_reference, exclude_id=r.expense_id)
    if m and r.expense_id > m[0]["expense_id"]:
        print(f"  {r.expense_id} ({r.vendor_id}, {r.expense_date}, {r.amount_excl_gst:,.0f}) looks like {m[0]['expense_id']}: {m[0]['reason']}")

print("\n=== Top 5 vendor-months by spend ===")
for r in sorted(spend_report(c), key=lambda r: -float(r["total"]))[:5]:
    print(f"  {r['month']}  {r['vendor_name']:<30}{r['bills']} bill(s)  {float(r['total']):>14,.2f}")

print("\n=== Sample approved bill (EXP-00001) ===")
print(entry_as_table(c, c.execute("SELECT ledger_entry_id e FROM expenses WHERE expense_id='EXP-00001'").fetchone()["e"]))
