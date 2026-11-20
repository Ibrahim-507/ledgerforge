# Task 14 - Taxes and statutory reports: rules live in data

## Where the Task 7 engine finds tax today
| Item | Where it lives now | Hard-coded in code? |
|---|---|---|
| Tax slabs (limits and rates), per financial year | table `tax_slabs` | no |
| Standard deduction 75,000, cess 4%, rebate limit 12,00,000 | table `tax_parameters` | no |
| PF 12% and 15,000 ceiling, ESI 0.75% / 3.25% and 21,000 limit, professional tax 200 and 25,000, overtime x2, 208 hours, 50-hour cap | table `statutory_rates` | no |
| Months in a year (12), the financial year starting in April, new regime only, rounding to the paisa | code | **yes, on purpose: these are not rules that change with a budget** |

The CSV files are only the first load (`seed_rules`). After that the database is the source of truth, and `process_run` reads it every time.

## The calculation (annual taxable income to a monthly figure)
1. Annual fixed income = monthly fixed gross x 12, minus the standard deduction = taxable income.
2. Slab tax: each slice of income taxed at its slab rate.
3. Rebate: nothing is payable up to the rebate limit, with marginal relief just above it (tax never exceeds the income above the limit).
4. Cess: multiply by 1.04. Divide by 12, then pay only for the days worked.
5. The bonus is taxed as the extra annual tax it causes, with cess.
`app/tax_explain.py` prints these steps. They add up to exactly the engine's answer (tested on 800 sample rows and the first row, 18,625.79).

## Changing a rule safely
- `PUT /tax/slabs/{slab_id}`, `/tax/parameters/{name}` and `/tax/statutory-rates/{name}` are **Admin only** (HR and employees get 403).
- A change needs a reason and records who, when, the old value and the new value in `rule_changes`. A refused change leaves no trace.
- Rates must be between 0 and 100. Moving a slab's upper limit moves the next slab's start with it, so slabs never leave gaps.
- Demo (`python -m scripts.task14_run`): EMP-0002, April 2025, 20% slab to 25%: tax goes up; changed back: tax is exactly the original again.

## Past months are not altered
- A processed or approved run keeps its stored payroll rows and its ledger entry; processing it again does nothing.
- Every run records the rules version it used (`ledgerforge-engine-1.0/rules-v2`), so any payslip can be traced to the rules in force.
- Slabs belong to a financial year, so editing FY2025-26 never changes FY2026-27 (tested).
- In production I would not overwrite a slab. I would insert a new row with an `effective_from` date and keep the old one. Here the audit log plus the stored runs give the same protection for this training scope.

## Statutory reports (`app/statutory_reports.py`)
Monthly PF, ESI, TDS and professional-tax reports (a line per employee plus totals), built from the stored payroll rows.
For all 18 months: report totals equal the payroll sums, and each equals the amount the ledger holds as payable for that run
(2110 PF, 2120 ESI, 2130 TDS, 2140 professional tax), difference 0.00.

## Think for yourself: old and new tax regime together. Questions to settle before building
1. Does each employee choose a regime every year, and can they change it mid-year? Who records the choice, and from when?
2. Which deductions does the old regime allow (80C, HRA, home loan interest ...)? Where do we get the proofs, and how often are they checked?
3. Do we compute tax under both regimes and use the lower, or only the employee's choice? What do we do when a declaration changes in February?
4. Two slab sets per year (a `regime` value on `tax_slabs` already exists) and two sets of parameters: standard deduction and rebate differ by regime.
5. How do we spread a year's tax when the choice or declarations change part-way (catch-up in the remaining months)?
6. What must the payslip and the TDS report show per employee (regime, taxable income, deductions claimed)?
7. How do we keep last year's results unchanged when the rules change, and how do we test both regimes against known answers?
