# Phase 2 Report - LedgerForge (Python track)
**Name:** <your name>  **Track:** Python Developers  **Phase:** 2  **Repo:** <GitHub link>  **Tag:** phase-2

| Task | Done | Evidence |
|------|------|----------|
| 6 Attendance and leave | yes | hand-count table vs monthly_summary output; leave tests |
| 7 Payroll engine | yes | `verify_ledgerforge.py payroll` output: 7,340/7,340 rows match; mismatch log |
| 8 Payslip | yes | sample PDF (EMP-0002, Apr 2025, net 1,58,504.61); stranger-refused test |
| 9 Ledger | yes | check 1 output; printed sample journal entry (JE for PR-2025-04) |
| 10 Invoices | yes | check 3 output; receivables list for 3 clients |

**Proof it works:** 38 automated tests pass; all 7,340 payroll rows match to the paisa; all 18 payroll postings equal the official
journal entries; check 1 (every entry balances) and check 3 (receivable 1,39,39,42,78 = open invoices) pass.

**Mini challenge (5 lines):** Attendance rows give each month's LOP days and overtime hours. The payroll engine prorates each
salary component by payable days, adds overtime and variable pay for gross, and deducts PF, ESI, professional tax and TDS for net pay.
The payslip prints those same engine numbers. Posting the run debits salary, bonus and employer-contribution expenses by department
and credits net pay and the PF/ESI/TDS/PT liabilities. Example: EMP-0002, April 2025: gross 1,79,130.40, deductions 20,625.79, net 1,58,504.61.

**What I learned (3-5 lines):** <write in your own words: Decimal vs float (0.1 + 0.2), why LOP uses calendar days, debit/credit, why posted entries are reversed not edited.>

**Problems and fixes:** 1-paisa differences until each component was rounded separately; ESI flag reflected cut-off status, so I derived enrolment;
TDS needed rebate, marginal relief and proration (see docs/payroll_rules_and_mismatch_log.md).

**Next phase plan:** vendors and expenses (Task 11), auto-posting payroll (Task 12), JWT auth (Task 13).
