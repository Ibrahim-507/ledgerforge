"""Turns raw attendance + HR dates into the 3 numbers payroll needs.
Rules (also written in the README):
  LOP days       = ABSENT_LOP + UNPAID_LEAVE + 0.5 x HALF_DAY_UNPAID
  Overtime hours = sum of daily overtime_hours, paid up to the 50-hour cap (cap applied in payroll)
  MISSING_CHECKOUT rows = counted as PRESENT (check-in proves attendance), overtime 0 for that day
  Days employed  = days from max(hire date, period start) to min(exit date, period end), inclusive
  Payable days   = days employed - LOP days"""
import numpy as np
import pandas as pd

LOP_WEIGHT = {"ABSENT_LOP": 1.0, "UNPAID_LEAVE": 1.0, "HALF_DAY_UNPAID": 0.5}


def monthly_inputs(items: pd.DataFrame, data_dir="data") -> pd.DataFrame:
    a = pd.read_csv(f"{data_dir}/attendance.csv", parse_dates=["attendance_date"])
    a["ym"] = a.attendance_date.dt.to_period("M")
    a["lop"] = a.status.map(LOP_WEIGHT).fillna(0.0)
    a["ot"] = a.overtime_hours.fillna(0.0)
    g = a.groupby(["employee_id", "ym"]).agg(lop=("lop", "sum"), ot=("ot", "sum")).reset_index()
    e = pd.read_csv(f"{data_dir}/employees.csv", parse_dates=["hire_date", "exit_date"])[
        ["employee_id", "hire_date", "exit_date"]]
    m = items.copy()
    m["ym"] = m.period_start.dt.to_period("M")
    m = m.merge(g, on=["employee_id", "ym"], how="left").merge(e, on="employee_id", how="left")
    m[["lop", "ot"]] = m[["lop", "ot"]].fillna(0.0)
    start = m[["hire_date", "period_start"]].max(axis=1)
    end = np.minimum(m.period_end, m.exit_date.fillna(m.period_end))
    m["days_employed"] = (end - start).dt.days + 1
    m["lop_days"] = m.lop
    m["payable_days"] = m.days_employed - m.lop
    m["overtime_hours_paid"] = m.ot   # payroll caps at 50 for eligible roles
    return m.drop(columns=["lop", "ot", "ym", "hire_date", "exit_date"])
