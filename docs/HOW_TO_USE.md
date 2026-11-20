# How to add Tasks 7-10 to your project (about 20 minutes)

**0. Back up first.** Copy your project folder. These files are NEW and may overwrite yours of the same name:
`app/payroll_rules.py`, `app/payroll_engine.py`, `app/attendance_rules.py`, `app/payroll_data.py`, `app/money_format.py`,
`app/payslip_service.py`, `app/api_payslips.py`, `app/books_db.py`, `app/ledger.py`, `app/checks.py`, `app/invoicing.py`,
`app/payroll_posting.py`, `app/exporter.py`, `app/seed_official.py`. Do not overwrite your own `monthly_summary` or leave code.

**1. Install what is missing:** `pip install reportlab pandas` (fastapi and pytest you already have).

**2. Data:** the code reads CSVs from a `data/` folder in the project root, named like the sheets
(`payroll_items.csv`, `salary_structures.csv`, `employees.csv`, `roles.csv`, `departments.csv`, `attendance.csv`,
`statutory_rates.csv`, `tax_parameters.csv`, `tax_slabs.csv`, `users.csv`, `chart_of_accounts.csv`, `journal_entries.csv`,
`journal_lines.csv`, `payroll_runs.csv`, `clients.csv`, `invoices.csv`, `invoice_items.csv`, `invoice_payments.csv`).
If you only have the Excel file: `python -m scripts.export_csvs LedgerForge_Dataset.xlsx`.

**3. Run, in this order, and keep the output as evidence:**
```powershell
python -m pytest -q                                   # all tests
python -m scripts.run_payroll                          # Task 7: 7,340 / 7,340 rows match; writes payroll_results.csv
python verify_ledgerforge.py payroll payroll_results.csv
python -m scripts.check_books                          # Tasks 9-10: checks 1 and 3, receivables, payroll posting; writes my_export/
python verify_ledgerforge.py checks --data my_export/
```

**4. Task 8 API:** in your FastAPI `main.py`
```python
from app.payroll_data import PayrollSource
from app.api_payslips import build_router
app.include_router(build_router(PayrollSource("data")))
```
Call it with header `X-User-Id: U-0002` (owner), another employee's id (stranger -> 403) or an HR user id.
This header login is a stand-in until JWT in Task 13.

**5. Be honest in the report:** the Task 9-10 code uses its own small SQLite store (`books_db.py`) with the dataset's
column names, not your SQLAlchemy models. If your mentor wants ORM models, the three ledger tables map 1:1.
