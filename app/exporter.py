"""Export the books to CSV (dataset column names) so the official checker can read them:
    python verify_ledgerforge.py checks --data your_export/"""
import csv
from pathlib import Path

TABLES = ["chart_of_accounts", "journal_entries", "journal_lines", "clients", "invoices",
          "invoice_items", "invoice_payments", "vendors", "expenses", "payroll_runs", "payroll_items"]


def export_tables(conn, out_dir):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for t in TABLES:
        cur = conn.execute(f"SELECT * FROM {t}")
        with open(Path(out_dir) / f"{t}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([c[0] for c in cur.description])
            w.writerows(cur.fetchall())
    return out_dir
