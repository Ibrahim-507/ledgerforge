"""Run every payroll row through the engine and compare with the official answer key.
Usage:  python -m scripts.run_payroll [data_dir] [--official-inputs]
  default            LOP days, overtime hours and days employed are computed from attendance
  --official-inputs  copy those three from payroll_items (tests the formulas only)"""
import sys
import pandas as pd
from app.payroll_data import PayrollSource

args = [a for a in sys.argv[1:] if not a.startswith("--")]
data = args[0] if args else "data"
src = PayrollSource(data, own_inputs="--official-inputs" not in sys.argv)

rows = [{"run_id": r.run_id, "employee_id": r.employee_id, **p.as_dict()} for r, p in src.all_rows()]
mine = pd.DataFrame(rows)
mine[["run_id", "employee_id", "gross_pay", "total_deductions", "net_pay"]].to_csv(
    "payroll_results.csv", index=False)
print(f"wrote payroll_results.csv ({len(mine)} rows)\n")

key = pd.read_csv(f"{data}/payroll_items.csv")
cols = ["gross_pay", "pf_employee", "esi_employee", "professional_tax", "tds",
        "total_deductions", "net_pay", "employer_cost"]
bad = pd.Series(False, index=key.index)
for c in cols:
    diff = (mine[c] - key[c]).abs() > 0.005
    print(f"{c:18s} mismatches: {int(diff.sum())}")
    bad |= diff
print(f"\nRows matching on every column: {len(key) - int(bad.sum())} / {len(key)} "
      f"({100 * (1 - bad.mean()):.2f}%)")
if bad.any():
    out = key.loc[bad, ["run_id", "employee_id"] + cols].join(mine.loc[bad, cols], rsuffix="_mine", lsuffix="_key")
    out.to_csv("payroll_mismatches.csv", index=False)
    print("wrote payroll_mismatches.csv")
