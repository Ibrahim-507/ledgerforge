# Task 2 notes: company data model

## Tables
- departments: the 11 departments of Zenith Nova.
- roles: job titles, each belonging to one department.
- employees: the people, linked to a department, a role and a manager.
- employee_assignments: history of which department, role and manager a person had, and when.

## Columns that can be empty (nullable) and why
1. employees.manager_id is empty for the top person, who reports to nobody.
2. employees.exit_date, resignation_date, exit_type and exit_reason are empty for people who still work here.
3. employee_assignments.effective_to is empty for the current assignment, because it has not ended yet.

## Why manager_id points to employees
A manager is also an employee, so manager_id is a foreign key to employees.employee_id (the table points to itself).

## Think for yourself: who was in department D05 on 30 June 2025?
Look in employee_assignments for rows where department_id = 'D05',
effective_from <= 2025-06-30, and (effective_to is empty or effective_to >= 2025-06-30).
The employee_id values of those rows are the people in D05 on that date.

## Indexes
I added indexes on department_id, role_id and manager_id, because these are the columns the API will search and filter by.

## Evidence
- Migration files: alembic/versions/
- ER diagram: docs/er_diagram.png and docs/er_diagram.md