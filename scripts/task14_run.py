"""Task 14 evidence:  python -m scripts.task14_run
1) tax calculation step by step  2) change a slab -> tax changes -> change it back  3) past months untouched
4) monthly PF / ESI / TDS / PT reports checked against payroll and the ledger  5) the rule change log"""
from pathlib import Path
from app.books_db import connect
from app.ledger import load_chart
from app.payroll_data import PayrollSource
from app.payroll_runs import approve_run, create_run, process_run, run_all_months
from app.statutory_reports import export_csv, monthly_summary, statutory_report
from app.tax_config import list_changes, load_rules, seed_rules, update_slab
from app.tax_explain import explain_text, explain_tds

DATA, ADMIN = "data", "U-0099"
conn = connect()
load_chart(conn, f"{DATA}/chart_of_accounts.csv")
seed_rules(conn, DATA)
src = PayrollSource(DATA)
FY = "FY2025-26"


def one_tax(label):
    """Re-calculate EMP-0002, April 2025 with the rules currently in the database (what a re-run would do)."""
    src.rates, src.params, src.slabs = load_rules(conn)
    r = src.items[(src.items.employee_id == "EMP-0002") & (src.items.run_id == "PR-2025-04")].iloc[0]
    row = type("Row", (), {**r.to_dict(), "employee_id": "EMP-0002"})()
    p = src.calculate_row(row)
    print(f"{label:<34} TDS {p.tds:>12,.2f}   net pay {p.net_pay:>14,.2f}")
    return p.tds


print("=== 1. Tax step by step: EMP-0002, April 2025 ===")
rates, params, slabs = load_rules(conn)
print(explain_text(explain_tds(144460, "34670.40", 30, 30, slabs[FY], params)))

print("\n=== 2. Change a slab, re-run, change it back ===")
before = one_tax("Original rules (20% slab)")
update_slab(conn, "TS-005", ADMIN, "demo: raise the 20% slab to 25%", rate_percent=25)
after = one_tax("After TS-005 20% -> 25%")
update_slab(conn, "TS-005", ADMIN, "demo: change it back", rate_percent=20)
back = one_tax("After changing it back")
print(f"Tax went up by {after - before:,.2f}, then back to the original: {back == before}")

print("\n=== 3. Past months are not altered ===")
rid = create_run(conn, "2025-04-01", "U-0237"); process_run(conn, src, rid); approve_run(conn, rid, ADMIN)
snap = lambda: conn.execute("SELECT dsum(tds) FROM payroll_items WHERE run_id='PR-2025-04'").fetchone()[0]
frozen = snap()
update_slab(conn, "TS-005", ADMIN, "demo: 20% -> 30%", rate_percent=30)
rid2 = create_run(conn, "2025-05-01", "U-0237"); process_run(conn, src, rid2)
print("April TDS total before / after the change:", frozen, snap(), "(unchanged)" if frozen == snap() else "(CHANGED!)")
for r in conn.execute("SELECT run_id, status, calculation_version FROM payroll_runs"):
    print(f"  {r['run_id']}  {r['status']:<9} {r['calculation_version']}")
update_slab(conn, "TS-005", ADMIN, "demo: back to 20%", rate_percent=20)

print("\n=== 4. Statutory reports, 18 months (fresh books) ===")
books = connect()
load_chart(books, f"{DATA}/chart_of_accounts.csv"); seed_rules(books, DATA)
src2 = PayrollSource(DATA)
run_all_months(books, src2)
print(f"{'Month':<9}{'PF to remit':>15}{'ESI':>12}{'TDS':>16}{'PT':>12}   vs ledger")
for s in monthly_summary(books):
    print(f"{s['month']:<9}{float(s['pf']):>15,.2f}{float(s['esi']):>12,.2f}{float(s['tds']):>16,.2f}{float(s['pt']):>12,.2f}   {'difference 0.00 on all four' if s['ok'] else 'MISMATCH'}")
rep = statutory_report(books, "PR-2025-04", "pf")
print("\nPF report, April 2025 (first 3 of", rep["employees"], "employees):")
for r in rep["rows"][:3]:
    print("  ", r["employee_id"], r["basic"], r["pf_employee"], r["pf_employer"])
print("   TOTAL", rep["totals"])
Path("reports").mkdir(exist_ok=True)
for kind in ("pf", "esi", "tds", "pt"):
    export_csv(statutory_report(books, "PR-2025-04", kind), f"reports/{kind}_PR-2025-04.csv")
print("Saved reports/pf_PR-2025-04.csv, esi_..., tds_..., pt_...")

print("\n=== 5. Rule change log ===")
for c in list_changes(conn):
    print(f"  #{c['change_id']} {c['changed_by']}  {c['rule_key']}.{c['field']}: {c['old_value']} -> {c['new_value']}   ({c['reason']})")
