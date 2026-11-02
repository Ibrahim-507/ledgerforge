import pandas as pd

a = pd.read_csv("csv/attendance.csv")
print("rows:", len(a))
print("dates:", a.attendance_date.min(), "to", a.attendance_date.max())
print(a.status.value_counts(dropna=False), "\n")
print(a.data_quality_flag.value_counts(dropna=False), "\n")
print("duplicate employee+date rows:", a.duplicated(["employee_id", "attendance_date"]).sum())
print("unknown employees:", (~a.employee_id.isin(pd.read_csv("csv/employees.csv").employee_id)).sum(), "\n")
print(a[a.data_quality_flag == "MISSING_CHECKOUT"].head(3).to_string(), "\n")

r = pd.read_csv("csv/leave_requests.csv")
print(r.status.value_counts(), "\n")
print(r.leave_type_code.value_counts(), "\n")
print(pd.read_csv("csv/leave_types.csv")[["leave_type_code", "pay_type"]].to_string())
print("half-days in requests:", (r.days % 1 != 0).sum())