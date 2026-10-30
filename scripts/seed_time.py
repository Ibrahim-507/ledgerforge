import time as timer
import pandas as pd
from sqlalchemy import insert
from app.database import SessionLocal   # CHANGE: copy from seed_example.py
from app.models import LeaveType, Holiday, Attendance, LeaveRequest, LeaveBalance

def clean(df):
    return df.astype(object).where(df.notna(), None)

def conv_leave_types(df):
    for c in ("prorated_for_joiners", "carry_forward_allowed"):
        df[c] = df[c].eq("Y")
    return clean(df)

def conv_holidays(df):
    df = df[["holiday_date", "holiday_name", "holiday_type", "falls_on_weekend"]].copy()
    df["holiday_date"] = pd.to_datetime(df["holiday_date"]).dt.date
    df["falls_on_weekend"] = df["falls_on_weekend"].eq("Y")
    return clean(df)

def conv_attendance(df):
    cols = ["attendance_id", "employee_id", "attendance_date", "status", "leave_type_code",
            "check_in", "check_out", "hours_worked", "overtime_hours", "late_flag",
            "data_quality_flag"]
    df = df[cols].copy()
    df["attendance_date"] = pd.to_datetime(df["attendance_date"]).dt.date
    for c in ("check_in", "check_out"):
        df[c] = pd.to_datetime(df[c], format="%H:%M", errors="coerce").dt.time
    df["late_flag"] = df["late_flag"].eq("Y")
    return clean(df)

def conv_requests(df):
    for c in ("start_date", "end_date", "applied_on", "decided_on"):
        df[c] = pd.to_datetime(df[c]).dt.date
    return clean(df)

def conv_balances(df):
    df["as_of_date"] = pd.to_datetime(df["as_of_date"]).dt.date
    return clean(df)

def load(session, model, path, convert, chunksize=10000):
    total = 0
    for chunk in pd.read_csv(path, chunksize=chunksize):
        rows = convert(chunk).to_dict("records")
        session.execute(insert(model).prefix_with("OR IGNORE"), rows)  # SQLite: skip duplicates
        session.commit()
        total += len(rows)
    return total

if __name__ == "__main__":
    with SessionLocal() as s:
        start = timer.time()
        for model, name, conv in [
            (LeaveType, "leave_types", conv_leave_types),
            (Holiday, "holidays", conv_holidays),
            (Attendance, "attendance", conv_attendance),
            (LeaveRequest, "leave_requests", conv_requests),
            (LeaveBalance, "leave_balances", conv_balances),
        ]:
            print(name, load(s, model, f"csv/{name}.csv", conv))
        print("seconds:", round(timer.time() - start, 1))