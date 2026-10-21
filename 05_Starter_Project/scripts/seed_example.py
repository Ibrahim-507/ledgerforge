"""PATTERN TO COPY: load a CSV into the database safely (re-runnable).
Run from 04_Starter_Project:   python -m scripts.seed_example
Your job (LF-03): turn this into ONE command that loads every table, then runs the integrity checks."""
import pandas as pd
from pathlib import Path
from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import Department
def main():
    Base.metadata.create_all(engine)
    df = pd.read_csv(Path(settings.data_dir) / "departments.csv")
    df["description"] = df["description"].where(df["description"].notna(), None)
    with SessionLocal() as db:
        for r in df.to_dict("records"):
            db.merge(Department(**r))
        db.commit()
    print(f"Seeded {len(df)} departments")
if __name__ == "__main__": main()
