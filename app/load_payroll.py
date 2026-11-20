"""Load payroll_runs.csv and payroll_items.csv into the database (safe to run twice).

    python -m scripts.load_payroll
"""
import time as timer
from decimal import Decimal

import pandas as pd
from sqlalchemy import insert

from app.database import SessionLocal
from app.models_payroll import PayrollItem, PayrollRun

RUN_MONEY = ["total_gross", "total_deductions", "total_net", "total_employer_contributions",
             "total_employer_cost"]
ITEM_NUMBERS = [
    "lop_days", "payable_days", "monthly_fixed_gross", "basic", "hra", "conveyance", "medical",
    "special_allowance", "earned_fixed_pay", "overtime_hours_paid", "overtime_pay", "variable_pay",
    "gross_pay", "pf_employee", "esi_employee", "professional_tax", "tds", "other_deductions",
    "total_deductions", "net_pay", "pf_employer", "esi_employer", "employer_cost",
]


def nothing_to_none(df):
    return df.astype(object).where(df.notna(), None)


def convert_runs(df):
    for c in ("period_start", "period_end", "pay_date"):
        df[c] = pd.to_datetime(df[c]).dt.date
    for c in ("created_at", "approved_at"):
        df[c] = pd.to_datetime(df[c]).dt.to_pydatetime()
    df["employees_paid"] = df["employees_paid"].astype(int)
    for c in RUN_MONEY:
        df[c] = df[c].map(lambda v: Decimal(str(v)))
    return nothing_to_none(df)


def convert_items(df):
    for c in ("period_start", "period_end"):
        df[c] = pd.to_datetime(df[c]).dt.date
    for c in ("calendar_days", "days_employed"):
        df[c] = df[c].astype(int)
    for c in ITEM_NUMBERS:
        df[c] = df[c].map(lambda v: Decimal(str(v)))
    return nothing_to_none(df)


def load(session, model, path, convert, chunksize=2000):
    total = 0
    for chunk in pd.read_csv(path, chunksize=chunksize, dtype={"department_id": str, "role_id": str}):
        rows = convert(chunk).to_dict("records")
        session.execute(insert(model).prefix_with("OR IGNORE"), rows)
        session.commit()
        total += len(rows)
    return total


if __name__ == "__main__":
    with SessionLocal() as s:
        start = timer.time()
        print("payroll_runs ", load(s, PayrollRun, "csv/payroll_runs.csv", convert_runs))
        print("payroll_items", load(s, PayrollItem, "csv/payroll_items.csv", convert_items))
        print("seconds:", round(timer.time() - start, 1))