# Task 13 - Logins, roles and permissions

## How it works
1. `POST /auth/login` with a username and password returns a token valid for **30 minutes**.
2. Every other request sends `Authorization: Bearer <token>`. In `/docs`, click **Authorize** and paste the token.
3. One dependency, `authorize`, runs before EVERY route. It checks the token, loads the user from the database, and asks the
   permission table (`app/permissions.py`) whether this role may use this route. The server decides; hiding a button is never enough.

| Situation | Answer |
|---|---|
| No token, bad token, expired token | **401** |
| Valid token but the role may not use the route | **403** |
| Employee asks for someone else's data by changing the id in the address | **403** |
| Route that has no rule in the table | **403** (deny by default), so a forgotten route is never left open |

## Passwords and keys
- Passwords are hashed with **scrypt** and a random salt per user (a memory-hard hash). The database holds only the hash. `users.csv` has no passwords, so
  every demo user gets one demo password, which is also stored only as a hash.
- The token signing key is read from the environment variable `LEDGERFORGE_SECRET_KEY` (at least 32 characters). The server refuses to start
  logins without it. It is never written in code or committed to git.
- Login failures always say "Invalid username or password", so an attacker cannot learn which usernames exist.

## Think for yourself: a user is deactivated while holding a valid token
**Decision: refused on the very next request.** The token only identifies the user. On every request the server reloads the user
from the database and checks `is_active` and the current role. So a deactivation, a demotion or a promotion takes effect immediately,
without waiting up to 30 minutes for the token to expire. Cost: one small database read per request. Tested both without and with a web server.

## Who may use which route
| Method | Route | Admin | HR | Employee | Note |
|---|---|---|---|---|---|
| POST | /auth/login | public | public | public | login |
| GET | /auth/me | yes | yes | yes | your own profile |
| GET | /bills | yes | yes | no |  |
| POST | /bills | yes | yes | no | submit a bill |
| POST | /bills/{expense_id}/approve | yes | no | no | not the person who submitted it |
| POST | /bills/{expense_id}/pay | yes | no | no |  |
| POST | /bills/{expense_id}/reject | yes | no | no |  |
| GET | /departments | yes | yes | yes |  |
| GET | /departments/{department_id} | yes | yes | yes |  |
| GET | /employees | yes | yes | no | whole company list |
| POST | /employees | yes | yes | no |  |
| DELETE | /employees/{employee_id} | yes | no | no | only Admin removes people |
| GET | /employees/{employee_id} | yes | yes | own only | an employee sees only their own record |
| PATCH | /employees/{employee_id} | yes | yes | no |  |
| GET | /employees/{employee_id}/salary | yes | yes | own only |  |
| GET | /employees/{employee_id}/salary/revisions | yes | yes | own only |  |
| POST | /employees/{employee_id}/salary/revisions | yes | yes | no | only HR and Admin change pay |
| GET | /employees/{employee_id}/team | yes | yes | own only |  |
| GET | /payroll-runs | yes | yes | no |  |
| POST | /payroll-runs | yes | yes | no | create a month |
| GET | /payroll-runs/{run_id} | yes | yes | no |  |
| POST | /payroll-runs/{run_id}/approve | yes | no | no | moves real money: separate permission, and not the person who ran it |
| POST | /payroll-runs/{run_id}/pay | yes | no | no |  |
| POST | /payroll-runs/{run_id}/process | yes | yes | no | calculate |
| POST | /payroll-runs/{run_id}/reverse | yes | no | no |  |
| GET | /payslips/{employee_id}/{run_id} | yes | yes | own only | an employee reads only their own payslip |
| GET | /payslips/{employee_id}/{run_id}/pdf | yes | yes | own only |  |
| GET | /reports/balance-sheet | yes | no | no |  |
| GET | /reports/profit-and-loss | yes | no | no |  |
| GET | /reports/spend | yes | yes | no |  |
| GET | /reports/statutory-summary | yes | yes | no |  |
| GET | /reports/statutory/{kind}/{run_id} | yes | yes | no |  |
| GET | /reports/trial-balance | yes | no | no |  |
| GET | /tax/explain | yes | yes | no |  |
| GET | /tax/parameters | yes | yes | no |  |
| PUT | /tax/parameters/{name} | yes | no | no |  |
| GET | /tax/rule-changes | yes | no | no | audit log of rule changes |
| GET | /tax/slabs | yes | yes | no |  |
| PUT | /tax/slabs/{slab_id} | yes | no | no | changes tax for the next payroll run |
| GET | /tax/statutory-rates | yes | yes | no |  |
| PUT | /tax/statutory-rates/{name} | yes | no | no |  |

Money-moving actions (approve payroll, approve or pay a bill, reverse a run) are **Admin only**, and the person who ran payroll
or submitted a bill still cannot approve their own, because the acting user comes from the token, not from the request body.

## Not done (next improvements)
Login attempt limits (lock after repeated failures), refresh tokens, password reset and change flows, and MFA (the `mfa_enabled` flag is loaded but not enforced).
