"""Task 12 evidence:  python -m scripts.task12_run
Runs payroll for all 18 months through draft -> processed -> approved (posted) -> paid, proves a second run posts nothing,
prints check 2 per month and a run with its journal entry, demonstrates a reversal, and exports tables to my_export/."""
import shutil
from pathlib import Path
from app.books_db import connect
from app.checks import check1_entries_balance, check2_payroll_matches_ledger
from app.exporter import export_tables
from app.ledger import entry_as_table, load_chart
from app.payroll_data import PayrollSource
from app.payroll_runs import approve_run, create_run, process_run, reverse_run, run_all_months

DATA = "data"
src = PayrollSource(DATA)
c = connect()
load_chart(c, f"{DATA}/chart_of_accounts.csv")

ids = run_all_months(c, src)
n1 = c.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"]
run_all_months(c, src)                                   # the "double click": run every month again
n2 = c.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"]
print(f"Journal entries after first run: {n1}   after running all 18 months AGAIN: {n2}   (must be equal)\n")

print("=== Check 2: ledger vs payroll run, every month ===")
print(f"{'Run':<12}{'Run total (employer cost)':>28}{'Ledger entry total':>22}{'Difference':>12}")
k = check2_payroll_matches_ledger(c)
for d in k["detail"]:
    print(f"{d['run_id']:<12}{float(d['run_total']):>28,.2f}{float(d['ledger']):>22,.2f}{d['difference']:>12}")
print("Check 2:", "PASS" if k["ok"] else "FAIL", f"({k['runs']} runs)   Check 1:", "PASS" if check1_entries_balance(c)["ok"] else "FAIL")

print("\n=== A run and its journal entry ===")
r = c.execute("SELECT * FROM payroll_runs WHERE run_id='PR-2025-04'").fetchone()
print({x: r[x] for x in ("run_id", "status", "employees_paid", "total_net", "total_employer_cost", "run_by", "approved_by",
                         "idempotency_key", "journal_entry_id", "payment_entry_id")})
print(entry_as_table(c, r["journal_entry_id"]))

print("=== Reversal demo (separate scratch ledger, one month) ===")
d = connect()
load_chart(d, f"{DATA}/chart_of_accounts.csv")
rid = create_run(d, "2025-04-01", "U-0237"); process_run(d, src, rid); approve_run(d, rid, "U-0099")
reverse_run(d, rid, "2025-05-02", "wrong variable pay", "U-0099")
print("status:", d.execute("SELECT status FROM payroll_runs").fetchone()["status"],
      "| entries:", d.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"],
      "| 5001 balance after reversal:", d.execute("SELECT dsum(debit) a, dsum(credit) b FROM journal_lines WHERE account_code=5001").fetchone()[:])

out = Path("my_export")
export_tables(c, out)
for f in ("employees.csv", "invoices.csv"):             # the official checker reads these too
    shutil.copy(Path(DATA) / f, out / f)
print("\nExported to my_export/. Run the official checker:  python verify_ledgerforge.py checks --data my_export/")
print("(my_export holds payroll postings only, so a receivable check on it will differ: look at checks 1 and 2.)")
