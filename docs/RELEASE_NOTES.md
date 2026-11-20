# LedgerForge v1.0.0 - Release notes

## Included
- Departments, employees, salary revisions, attendance, leave (FastAPI, SQLAlchemy, Alembic)
- Payroll engine: 7,340 / 7,340 official rows match
- Payslip PDF, double-entry ledger with reversals, invoices, vendor bills with approval
- Payroll runs (draft, processed, approved, paid), idempotent; tax rules as data; statutory reports
- Trial balance, P&L, balance sheet
- Security: scrypt hashes, JWT 30 min, roles ADMIN / HR / EMPLOYEE, deny-by-default permissions
- Background bulk payroll job, /api/v1, Docker Compose, CI tests
- JSON logs, /health with database check, backup and restore, CSV/Excel export

## NOT included / known limits (honest)
- Books store (ledger, payroll, invoices) is SQLite on a disk/volume, not PostgreSQL
- Demo users share one demo password
- No login-attempt limits yet
- Free hosting may sleep; first request can be slow
- (add anything else you found during the audit)

## Final checks
```
PASS  Every journal entry balances  -  debits-credits=0.0, unbalanced entries=0
PASS  Payroll equals ledger, every month  -  largest monthly difference=0.00
PASS  Receivables equal open invoices  -  ledger 1100=139,394,278.00, open (sent/overdue/part-paid) invoices=139,394,278.00
PASS  Payroll employees exist  -  payroll rows with unknown employee=0
PASS  Nobody is paid after leaving  -  payroll rows after exit_date=0

5/5 checks passed
```

## Performance (Task 18)
| Operation | Before | After | Notes |
|-----------|--------|-------|-------|
| 18-month payroll calculation | 27.5s | 26.7s | 7,340 rows, ~3.7ms/row |
| Payroll items + employee join | 4ms | 4ms | Uses index on run_id |
| Statutory summary | 1ms | 1ms | Uses indexes on run_id |
| Employee search (LIKE) | full scan | full scan | SQLite LIMIT: leading wildcard prevents index use |
| Trial balance (SQLite) | <1ms | <1ms | Uses index on account_code |
| Payroll journal entries | <1ms | <1ms | Uses index on source_type |

Indexes added:
- `employees`: full_name, work_email, composite (full_name, work_email)
- `journal_entries`: entry_date, source_type
- `journal_lines`: cost_center_department_id, entry_id
