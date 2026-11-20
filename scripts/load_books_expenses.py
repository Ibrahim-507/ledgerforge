"""Import the source expense/bill register into the books API database without duplicates.
Run: python -m scripts.load_books_expenses
CSV statuses PAID/UNPAID are mapped to API statuses PAID/APPROVED; ledger/payment
entry links are kept from the source CSV.
"""
import csv
import os
from pathlib import Path
from app.deps import db_path
from app.books_db import connect

DATA = Path(os.environ.get("LEDGERFORGE_DATA", "data"))


def main():
    with (DATA / "expenses.csv").open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    conn = connect(db_path())
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(expenses)")]
        payments = {r["source_id"]: r["entry_id"] for r in conn.execute(
            "SELECT source_id, entry_id FROM journal_entries WHERE source_type='EXPENSE_PAYMENT' AND source_id IS NOT NULL"
        )}
        inserted = 0
        conn.execute("BEGIN")
        for source in rows:
            row = dict(source)
            if row.get("status", "").upper() == "UNPAID":
                row["status"] = "APPROVED"  # posted to ledger; payment remains outstanding
            row["payment_ledger_entry_id"] = row.get("payment_ledger_entry_id") or payments.get(row.get("expense_id"))
            row["rejected_reason"] = None
            row = {k: (None if row.get(k) in (None, "") else row.get(k)) for k in cols}
            cur = conn.execute(
                f"INSERT OR IGNORE INTO expenses ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                [row[k] for k in cols],
            )
            inserted += max(cur.rowcount, 0)
        conn.commit()
        print(f"Expense register linked: {inserted} bill(s); database {db_path()}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
