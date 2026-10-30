# LedgerForge: starter project
This is a tiny, working skeleton. It already runs. You grow it into the full product over 4 weeks.

## First 10 minutes
```
python -m venv .venv
# Windows: .venv\Scripts\activate      Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
python -m scripts.seed_example
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs and try `GET /departments`. Run `pytest` to see the tests pass.

## What is already done for you (copy the pattern, do not just read it)
- `app/models.py` one table (Department)   - `app/routers/departments.py` one router
- `scripts/seed_example.py` one safe CSV loader   - `tests/` two working tests

## Rules
Never commit `.env`. One Git branch per task (`lf-02-employee-model`). Write a test for every new endpoint.

## Task 6: Attendance and leave

### Where the data comes from
Five CSV files in the `csv` folder are loaded into five tables: `attendance` (150,155 rows), `leave_types`, `leave_requests` (3,441 rows), `leave_balances` and `holidays`. Attendance is loaded in chunks of 10,000 rows. The full load takes [__] seconds.

### Status words in attendance
| Status | Counted as | Loss-of-pay days |
|---|---|---|
| PRESENT | present | 0 |
| WFH | work from home | 0 |
| PAID_LEAVE | paid leave | 0 |
| UNPAID_LEAVE | unpaid leave | 1 |
| ABSENT_LOP | absent | 1 |
| HALF_DAY_UNPAID | half day unpaid | 0.5 |

Loss-of-pay (LOP) days = absent days + unpaid leave days + 0.5 for each unpaid half day. This follows the payroll convention in the data sheet, and Task 7 uses it.

### Rule: missing check-out
A row with `data_quality_flag = MISSING_CHECKOUT` counts as a **present** day, because the person checked in. Its overtime is **0**, because the hours cannot be known. The day is also reported as `missing_checkout_days` in the monthly summary, so payroll can review it. Reason: cutting someone's pay for a recording fault would be unfair, and these rows are only about 0.15% of attendance.

### Rule: counting leave days
Leave days count Monday to Friday and skip public holidays from the `holidays` table. The exception is leave type **ML**: the data counts every weekday of its 26-week period, so holidays inside it are not subtracted. I checked my function against all 3,441 leave requests: **0 mismatches**.

### Monthly summary
`monthly_summary(employee, month)` returns: present days, work-from-home days, paid leave days, unpaid leave days, absent days, unpaid half days, LOP days, late days (from the `late_flag` column), overtime hours, and missing check-out days. Overtime hours are reported as recorded. The 50-hour cap and the eligible roles are applied in the payroll engine (Task 7).

### Leave flow
- A request starts as **applied**. HR can **approve** or **reject** it.
- A request is rejected when the balance is not enough.
- The balance is reduced only when a request is approved.
- Weekends and holidays are never counted as leave days.

### Half-day leave: how the design would change
Store the leave days as a decimal (0.5 is allowed). Add a field for first half or second half of the day. In the attendance summary, a half-day leave day counts 0.5 as leave and 0.5 as worked, and must not be counted twice.

### How I checked the results
I counted 3 employees by hand in Excel and compared with the program output.

| Employee | Month | Present | WFH | Paid leave | Late | Overtime | Missing check-out |
|---|---|---|---|---|---|---|---|
| EMP-0004 | 2025-09 | [__] | [__] | [__] | [__] | [__] | [__] |
| EMP-0026 | 2025-10 | [__] | [__] | [__] | [__] | [__] | [__] |
| EMP-0012 | 2026-02 | [__] | [__] | [__] | [__] | [__] | [__] |

The program output matches this table for all three employees. [Write this only after your test passes.]

Tests: `python -m pytest -q` gives [__] passed.