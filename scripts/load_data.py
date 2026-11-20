"""Load the company CSVs into the database. Safe to run again and again."""
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine
from app.models import (
    Department,
    Employee,
    EmployeeAssignment,
    Role,
     SalaryComponent,
    SalaryRevision,
    SalaryStructure,
    LeaveType,
    Holiday,
    Attendance,
    LeaveRequest,
    LeaveBalance,
)

# Loading order: parents first. Employees need departments and roles to exist.
# (csv name, model, date columns, yes/no columns)
TABLES = [
    ("departments", Department, [], []),
    ("roles", Role, [], ["overtime_eligible"]),
    ("employees", Employee,
     ["date_of_birth", "hire_date", "exit_date", "resignation_date", "created_at"],
     ["pf_applicable", "esi_applicable"]),
    ("employee_assignments", EmployeeAssignment, ["effective_from", "effective_to"], []),
     ("salary_components", SalaryComponent, [], ["taxable", "is_fixed"]),
    ("salary_revisions", SalaryRevision, ["effective_from", "created_at"], []),
    ("salary_structures", SalaryStructure, ["effective_from", "effective_to"], []),
    ("leave_types", LeaveType, [], ["prorated_for_joiners", "carry_forward_allowed"]),
    ("holidays", Holiday, ["holiday_date"], ["falls_on_weekend"]),
    ("attendance", Attendance, ["attendance_date"], ["late_flag"]),
    ("leave_requests", LeaveRequest, ["start_date", "end_date", "applied_on", "decided_on"], []),
    ("leave_balances", LeaveBalance, ["as_of_date"], []),
]

# Numeric fields use Decimal when the target model stores exact numeric values.
DECIMAL_COLS = {
    "salary_revisions": ["previous_annual_fixed", "new_annual_fixed", "pct_change"],
    "salary_structures": ["monthly_amount"],
    "attendance": ["hours_worked", "overtime_hours"],
    "leave_requests": ["days"],
    "leave_balances": ["cl_entitlement", "cl_used", "cl_balance", "sl_entitlement", "sl_used", "sl_balance", "el_used_fy", "el_balance", "pending_days"],
}
TIME_COLS = {"attendance": ["check_in", "check_out"]}

YES_NO = {"true": True, "yes": True, "y": True, "1": True,
          "false": False, "no": False, "n": False, "0": False}


def read_clean(name, model, date_cols, bool_cols):
    df = pd.read_csv(Path(settings.data_dir) / f"{name}.csv")
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    for c in TIME_COLS.get(name, []):
        def parse_time(value):
            if pd.isna(value) or value == "":
                return None
            text = str(value).strip()
            for fmt in ("%H:%M:%S", "%H:%M", "%H:%M:%S.%f"):
                try:
                    from datetime import datetime
                    return datetime.strptime(text, fmt).time()
                except ValueError:
                    continue
            return None
        df[c] = df[c].map(parse_time)
    for c in bool_cols:
        df[c] = df[c].astype(str).str.strip().str.lower().map(YES_NO)
    for c in DECIMAL_COLS.get(name, []):
        df[c] = df[c].map(lambda v: None if pd.isna(v) else Decimal(str(v)))
    df = df.astype(object)
    df = df.where(df.notna(), None)  # empty cells become None
    model_columns = set(model.__table__.columns.keys())
    return df[[c for c in df.columns if c in model_columns]]


def main():
    data = {name: read_clean(name, model, d, b) for name, model, d, b in TABLES}

    with Session(engine) as session, session.begin():  # all or nothing
        for _, model, _, _ in reversed(TABLES):        # clear children first
            session.execute(delete(model))
        for name, model, _, _ in TABLES:               # load parents first
            print(f"Loading {name}...")
            session.bulk_insert_mappings(model, data[name].to_dict("records"))
            # raise RuntimeError("test failure")       # failure test: remove the # to test, then put it back

    # Count check: database vs CSV
    ok = True
    print(f"{'table':<24}{'csv':>8}{'db':>8}  status")
    with Session(engine) as session:
        for name, model, _, _ in TABLES:
            db_count = session.scalar(select(func.count()).select_from(model))
            match = db_count == len(data[name])
            ok &= match
            print(f"{name:<24}{len(data[name]):>8}{db_count:>8}  {'OK' if match else 'MISMATCH'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()