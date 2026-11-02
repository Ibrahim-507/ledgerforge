# Task 7 - Payroll rules and mismatch log

## Result
`python -m scripts.run_payroll` runs all **7,340** employee-months through the engine and compares each with
`payroll_items` (the answer key): **7,340 / 7,340 rows match on gross, PF, ESI, professional tax, TDS,
total deductions, net pay and employer cost, to the paisa (100.00%)**. LOP days, overtime hours and days
employed are computed from attendance and HR dates, not copied.

## The rules in plain English
| # | Rule | Formula |
|---|------|---------|
| 1 | Loss of pay | Each fixed component is paid for *payable days / calendar days* (calendar days, not working days). Half-day unpaid = 0.5 day. |
| 2 | Earned fixed pay | Sum of the five prorated components (Basic, HRA, Conveyance, Medical, Special), each rounded to the paisa first. |
| 3 | Overtime | Only for overtime-eligible roles: `min(hours, 50) x (monthly fixed gross / 208) x 2`. |
| 4 | Variable pay | Bonus / incentive amounts are decisions, not formulas: taken as input data. |
| 5 | Gross pay | Earned fixed pay + overtime + variable pay. |
| 6 | PF | 12% of the month's basic, basic capped at 15,000, only if the employee is PF-applicable. |
| 7 | ESI | 0.75% of gross pay, only if fixed gross <= 21,000 and the employee is enrolled in ESI. |
| 8 | Professional tax | 200 when gross pay >= 25,000, else 0. |
| 9 | TDS | See below. |
| 10 | Totals | Deductions = PF + ESI + PT + TDS + loan recovery. Net = gross - deductions. |

**TDS:** yearly taxable = fixed gross x 12 - 75,000. Tax by slab; nothing if taxable <= 12 lakh, with marginal
relief just above (tax never more than the amount above 12 lakh). `TDS = [tax(fixed) x 1.04 / 12 x payable/calendar days]
+ [(tax(fixed + variable) - tax(fixed)) x 1.04]`, each part rounded to the paisa, then added.

**Attendance rules (feed rules 1 and 3):** LOP days = ABSENT_LOP + UNPAID_LEAVE + 0.5 x HALF_DAY_UNPAID.
Overtime hours = sum of daily overtime hours. **MISSING_CHECKOUT rows count as present** (the check-in proves
attendance); they carry no overtime, and no LOP. Days employed = days from max(hire date, 1st) to min(exit date, month end).

## Mismatch log
There are **no unexplained mismatches**. These are the places where the README did not fully state the rule, so I
inferred it from the answer key and tested it against all 7,340 rows - each is a judgement a reviewer should know about:

| # | What the README left open | What I did | Rows affected | Evidence |
|---|---------------------------|------------|---------------|----------|
| 1 | Is PF/ESI decided by salary alone? | No. The `employees.pf_applicable` / `esi_applicable` flags decide. 456 rows have PF = 0 and every one belongs to a PF-not-applicable employee. | 456 | 0 mismatches after using the flag |
| 2 | ESI flag vs official data | The `esi_applicable` flag is the status at the 30 Sep 2026 cut-off. Four employees (EMP-0131, 0137, 0481, 0633) have flag N but paid ESI while their fixed gross was within 21,000, before a raise took them over. Rule used: *enrolled = flag Y, or (fixed gross within limit and the employee's latest fixed gross is above the limit)*. | 44 | Two other low-paid employees (EMP-0089, EMP-0494) have flag N and are correctly paid no ESI. This is an inference from data, not a stated rule. |
| 3 | Earned pay differs by 1 paisa if you prorate the total | Each component is prorated and rounded separately, then summed. | ~680 | 0 mismatches vs 681 with the total-pay shortcut |
| 4 | TDS wording ("projected annual tax / 12 + marginal tax on variable pay") | Implemented as above, including rebate, marginal relief, proration of the fixed part for LOP and the variable part taxed at the marginal slab rate. | all rows with TDS | 0 mismatches. A simpler version had 4,239; adding the rebate got to 702; adding LOP proration and marginal relief left 72 one-paisa differences; rounding the two parts separately reached 0. |
| 5 | Variable pay and loan recovery | Taken as input from payroll_items (decisions, not formulas). | 1,152 / 127 | Declared limitation. |
| 6 | Salary structure for mid-month joiners | Use the latest revision that overlaps the month. | 144 | 0 mismatches |
