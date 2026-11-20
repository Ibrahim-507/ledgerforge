import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", None)

items = pd.read_csv("csv/payroll_items.csv")
zero = items[(items.pf_employee == 0) & (items.basic > 0)]
print("rows with PF = 0 although basic > 0:", len(zero))
print(zero.calculation_note.value_counts().head(10).to_string())
print(zero[["employee_id", "run_id", "monthly_fixed_gross", "basic", "esi_employee",
            "professional_tax", "tds", "variable_pay_type"]].head(8).to_string())

print("--- the whole official row for EMP-0089, April 2025")
print(items[(items.employee_id == "EMP-0089") & (items.run_id == "PR-2025-04")].T.to_string())

emp = pd.read_csv("csv/employees.csv")
print("--- employees.csv columns:", list(emp.columns))
print(emp[emp.employee_id == "EMP-0089"].T.to_string())