# Task 4 notes: employee and team APIs

## Why payroll needs history (soft delete)
When an employee leaves, the delete sets exit_date instead of removing the row. Payroll, tax and the ledger must still be able to show what was paid to that person in past months, so their record must never disappear.

## Should a manager's team include people who left?
By default the team shows only current employees (exit_date is empty), because a manager's team means the people reporting to them now. An optional include_left=true parameter shows everyone, because payroll and audits sometimes need the full history.