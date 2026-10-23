Nullable columns:
1. manager_id (employees) is empty for the top person, who reports to nobody.
2. exit_date, resignation_date, exit_type and exit_reason are empty for people who still work here.
3. effective_to (employee_assignments) is empty for the current assignment, which has not ended.
manager_id points to employees because a manager is also an employee.
Who was in department D05 on 30 June 2025?
Look in employee_assignments for rows where department_id = 'D05',
effective_from <= 2025-06-30, and (effective_to is empty or effective_to >= 2025-06-30).
The employee_id values of those rows are the answer.