#!/usr/bin/env python3
"""Measure performance of key operations."""
import time
import os
import sqlite3
from sqlalchemy import create_engine, text
from decimal import Decimal

from app.database import engine as pg_engine
from app.payroll_data import PayrollSource
from app.books_db import connect as connect_books
from app.config import settings

def timeit(label, fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - t0
    print(f"{label}: {elapsed:.3f}s")
    return result, elapsed

def main():
    print("=" * 60)
    print("PERFORMANCE MEASUREMENTS")
    print("=" * 60)
    print(f"Database: {settings.database_url}")

    # 1. 18-month payroll run (background job style)
    print("\n1. 18-MONTH PAYROLL CALCULATION")
    print("-" * 40)

    source = PayrollSource("data")
    months = [
        "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09",
        "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
        "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"
    ]

    t0 = time.perf_counter()
    for m in months:
        rows = source.items[source.items.period_start == m]
        for r in rows.itertuples():
            source.calculate_row(r)
    elapsed = time.perf_counter() - t0
    print(f"  Calculate all 18 months ({len(source.items)} rows): {elapsed:.3f}s")
    print(f"  Per row: {elapsed/len(source.items)*1000:.2f}ms")

    # 2. Main database queries (PostgreSQL or SQLite)
    print("\n2. MAIN DATABASE QUERIES")
    print("-" * 40)

    is_postgres = settings.database_url.startswith("postgresql")
    engine = pg_engine

    with engine.connect() as conn:
        # Query 1: Payroll items with employee join
        if is_postgres:
            q1 = """
                EXPLAIN ANALYZE
                SELECT pi.*, e.full_name, e.department_id
                FROM payroll_items pi
                JOIN employees e ON pi.employee_id = e.employee_id
                WHERE pi.run_id = 'PR-2025-04'
            """
        else:
            q1 = """
                EXPLAIN QUERY PLAN
                SELECT pi.*, e.full_name, e.department_id
                FROM payroll_items pi
                JOIN employees e ON pi.employee_id = e.employee_id
                WHERE pi.run_id = 'PR-2025-04'
            """
        result, t = timeit("  Payroll items + employee join", lambda: conn.execute(text(q1)).fetchall())
        for row in result:
            print(f"    {row}")

        # Query 2: Statutory summary (multiple joins)
        if is_postgres:
            q2 = """
                EXPLAIN ANALYZE
                SELECT pr.run_id, pr.period_start, pr.total_employer_cost,
                       SUM(pi.pf_employee + pi.pf_employer) as pf_total,
                       SUM(pi.esi_employee + pi.esi_employer) as esi_total,
                       SUM(pi.tds) as tds_total,
                       SUM(pi.professional_tax) as pt_total
                FROM payroll_runs pr
                JOIN payroll_items pi ON pr.run_id = pi.run_id
                GROUP BY pr.run_id, pr.period_start, pr.total_employer_cost
            """
        else:
            q2 = """
                EXPLAIN QUERY PLAN
                SELECT pr.run_id, pr.period_start, pr.total_employer_cost,
                       SUM(pi.pf_employee + pi.pf_employer) as pf_total,
                       SUM(pi.esi_employee + pi.esi_employer) as esi_total,
                       SUM(pi.tds) as tds_total,
                       SUM(pi.professional_tax) as pt_total
                FROM payroll_runs pr
                JOIN payroll_items pi ON pr.run_id = pi.run_id
                GROUP BY pr.run_id, pr.period_start, pr.total_employer_cost
            """
        result, t = timeit("  Statutory summary", lambda: conn.execute(text(q2)).fetchall())
        for row in result:
            print(f"    {row}")

        # Query 3: Employee search
        if is_postgres:
            q3 = """
                EXPLAIN ANALYZE
                SELECT * FROM employees
                WHERE full_name ILIKE '%jatin%' OR work_email ILIKE '%jatin%'
            """
        else:
            q3 = """
                EXPLAIN QUERY PLAN
                SELECT * FROM employees
                WHERE full_name LIKE '%jatin%' OR work_email LIKE '%jatin%'
            """
        result, t = timeit("  Employee search", lambda: conn.execute(text(q3)).fetchall())
        for row in result:
            print(f"    {row}")

    # 3. SQLite books queries
    print("\n3. SQLITE BOOKS QUERIES")
    print("-" * 40)

    conn = connect_books("ledgerforge.sqlite")

    # Query 1: Payroll posting lookup
    q1 = "EXPLAIN QUERY PLAN SELECT * FROM journal_entries WHERE source_type = 'PAYROLL_RUN'"
    result, t = timeit("  Payroll journal entries", lambda: conn.execute(q1).fetchall())
    for row in result:
        print(f"    {row}")

    # Query 2: Receivables
    q2 = "EXPLAIN QUERY PLAN SELECT * FROM journal_lines WHERE account_code = 1100"
    result, t = timeit("  Receivables (account 1100)", lambda: conn.execute(q2).fetchall())
    for row in result:
        print(f"    {row}")

    # Query 3: Journal entries for a period
    q3 = "EXPLAIN QUERY PLAN SELECT * FROM journal_entries WHERE entry_date BETWEEN '2025-04-01' AND '2025-04-30'"
    result, t = timeit("  Journal entries for April 2025", lambda: conn.execute(q3).fetchall())
    for row in result:
        print(f"    {row}")

    conn.close()

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)

if __name__ == "__main__":
    main()