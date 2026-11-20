"""Import the CSV payroll register into the API/books SQLite database, without duplicates.
Run: python -m scripts.load_books_payroll
Only inserts rows not already present. Payroll journal/payment entry IDs are linked
from the journal entries already in the books database when matching entries exist.
"""
import csv
import os
from pathlib import Path
from app.books_db import connect
from app.deps import db_path


DATA = Path(os.environ.get("LEDGERFORGE_DATA", "data"))


def read_rows(name):
    with (DATA / f"{name}.csv").open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def blank_to_none(value):
    return None if value is None or value == "" else value


def main():
    conn = connect(db_path())
    try:
        run_rows = read_rows("payroll_runs")
        item_rows = read_rows("payroll_items")
        payments = {r["source_id"]: r["entry_id"] for r in conn.execute(
            "SELECT source_id, entry_id FROM journal_entries WHERE source_type='SALARY_PAYMENT' AND source_id IS NOT NULL"
        )}
        payroll_entries = {r["source_id"]: r["entry_id"] for r in conn.execute(
            "SELECT source_id, entry_id FROM journal_entries WHERE source_type='PAYROLL_RUN' AND source_id IS NOT NULL"
        )}
        run_cols = [r["name"] for r in conn.execute("PRAGMA table_info(payroll_runs)")]
        item_cols = [r["name"] for r in conn.execute("PRAGMA table_info(payroll_items)")]
        inserted_runs = inserted_items = 0
        conn.execute("BEGIN")
        for row in run_rows:
            row = dict(row)
            row["journal_entry_id"] = row.get("journal_entry_id") or payroll_entries.get(row["run_id"])
            row["payment_entry_id"] = payments.get(row["run_id"])
            # CSV uses a descriptive legacy status for the posted month not yet paid.
            if row.get("status", "").upper().startswith("POSTED"):
                row["status"] = "APPROVED"
            row["error_message"] = None
            row = {k: blank_to_none(row.get(k)) for k in run_cols}
            if row.get("run_id"):
                cur = conn.execute(
                    f"INSERT OR IGNORE INTO payroll_runs ({','.join(run_cols)}) VALUES ({','.join('?' for _ in run_cols)})",
                    [row[k] for k in run_cols],
                )
                inserted_runs += max(cur.rowcount, 0)
        for row in item_rows:
            row = {k: blank_to_none(row.get(k)) for k in item_cols}
            if row.get("run_id"):
                cur = conn.execute(
                    f"INSERT OR IGNORE INTO payroll_items ({','.join(item_cols)}) VALUES ({','.join('?' for _ in item_cols)})",
                    [row[k] for k in item_cols],
                )
                inserted_items += max(cur.rowcount, 0)
        conn.commit()
        print(f"Payroll register linked: {inserted_runs} run(s), {inserted_items} item(s); database {db_path()}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
