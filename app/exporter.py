"""Export the books to CSV (dataset column names) so the official checker can read them:
    python verify_ledgerforge.py checks --data your_export/"""
import csv
import os
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

from app.books_db import connect as connect_books
from app.database import engine as pg_engine
from sqlalchemy import text

CENT = Decimal("0.01")

BOOKS_TABLES = [
    "chart_of_accounts", "journal_entries", "journal_lines", "clients", "invoices",
    "invoice_items", "invoice_payments", "vendors", "expenses",
    "users", "tax_slabs", "tax_parameters", "statutory_rates", "rule_changes", "jobs"
]

PG_TABLES = [
    "employees", "departments", "roles", "salary_structures", "salary_revisions",
    "salary_components", "attendance", "leave_types", "leave_requests", "leave_balances",
    "holidays", "employee_assignments"
]

# Payroll tables from PostgreSQL with exact seed CSV column order
PAYROLL_RUN_COLS = [
    "run_id", "period_start", "period_end", "pay_date", "employees_paid",
    "total_gross", "total_deductions", "total_net", "total_employer_contributions",
    "total_employer_cost", "status", "run_by", "approved_by", "created_at",
    "approved_at", "idempotency_key", "journal_entry_id", "calculation_version"
]

PAYROLL_ITEM_COLS = [
    "payroll_item_id", "run_id", "employee_id", "period_start", "period_end",
    "department_id", "role_id", "calendar_days", "days_employed", "lop_days",
    "payable_days", "monthly_fixed_gross", "basic", "hra", "conveyance", "medical",
    "special_allowance", "earned_fixed_pay", "overtime_hours_paid", "overtime_pay",
    "variable_pay", "variable_pay_type", "gross_pay", "pf_employee", "esi_employee",
    "professional_tax", "tds", "other_deductions", "total_deductions", "net_pay",
    "pf_employer", "esi_employer", "employer_cost", "calculation_note"
]


def export_books(out_dir):
    """Export SQLite books database to CSV."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    conn = connect_books(os.environ.get("LEDGERFORGE_BOOKS_PATH", "ledgerforge.sqlite"))
    for t in BOOKS_TABLES:
        cur = conn.execute(f"SELECT * FROM {t}")
        with open(Path(out_dir) / f"{t}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([c[0] for c in cur.description])
            w.writerows(cur.fetchall())
    conn.close()


def export_pg(out_dir):
    """Export PostgreSQL main database to CSV."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with pg_engine.connect() as conn:
        for t in PG_TABLES:
            result = conn.execute(text(f"SELECT * FROM {t}"))
            rows = result.fetchall()
            if rows:
                with open(Path(out_dir) / f"{t}.csv", "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(result.keys())
                    w.writerows(rows)


def export_payroll(out_dir):
    """Export payroll tables from PostgreSQL with exact seed CSV column format."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with pg_engine.connect() as conn:
        # payroll_runs
        result = conn.execute(text(f"SELECT {', '.join(PAYROLL_RUN_COLS)} FROM payroll_runs"))
        rows = result.fetchall()
        with open(Path(out_dir) / "payroll_runs.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(PAYROLL_RUN_COLS)
            w.writerows(rows)

        # payroll_items
        result = conn.execute(text(f"SELECT {', '.join(PAYROLL_ITEM_COLS)} FROM payroll_items"))
        rows = result.fetchall()
        with open(Path(out_dir) / "payroll_items.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(PAYROLL_ITEM_COLS)
            w.writerows(rows)


def export_tables(books_conn, out_dir):
    """Legacy function for backward compatibility - exports only books tables."""
    export_books(out_dir)
    return out_dir


def export_all(out_dir):
    """Export both SQLite books and PostgreSQL main databases."""
    export_books(out_dir)
    export_pg(out_dir)
    export_payroll(out_dir)
    return out_dir