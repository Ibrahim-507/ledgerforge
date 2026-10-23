"""Load the company CSVs into the database. Safe to run again and again."""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine
from app.models import Department, Employee, EmployeeAssignment, Role

# Loading order: parents first. Employees need departments and roles to exist.
# (csv name, model, date columns, yes/no columns)
TABLES = [
    ("departments", Department, [], []),
    ("roles", Role, [], ["overtime_eligible"]),
    ("employees", Employee,
     ["date_of_birth", "hire_date", "exit_date", "resignation_date", "created_at"],
     ["pf_applicable", "esi_applicable"]),
    ("employee_assignments", EmployeeAssignment, ["effective_from", "effective_to"], []),
]

YES_NO = {"true": True, "yes": True, "y": True, "1": True,
          "false": False, "no": False, "n": False, "0": False}


def read_clean(name, date_cols, bool_cols):
    df = pd.read_csv(Path(settings.data_dir) / f"{name}.csv")
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    for c in bool_cols:
        df[c] = df[c].astype(str).str.strip().str.lower().map(YES_NO)
    df = df.astype(object)
    return df.where(df.notna(), None)  # empty cells become None


def main():
    data = {name: read_clean(name, d, b) for name, _, d, b in TABLES}

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