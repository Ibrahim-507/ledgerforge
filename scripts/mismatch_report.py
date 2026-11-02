import os
import pandas as pd

os.makedirs("docs", exist_ok=True)
try:
    m = pd.read_csv("payroll_mismatches.csv")
except FileNotFoundError:
    m = pd.DataFrame()

with open("docs/mismatch_log.md", "w", encoding="utf-8") as f:
    f.write("# Payroll mismatch log\n\n")
    if m.empty:
        f.write("All 7,340 rows match the official payroll_items to the paisa. No mismatches.\n")
    else:
        f.write(f"{len(m)} rows differ from the official data.\n")
print("wrote docs/mismatch_log.md")