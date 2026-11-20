# Task 15 - Trial balance, profit and loss, balance sheet

## Definitions used
- **Trial balance** (`/reports/trial-balance?from=&to=`): for every account with activity: opening balance, debits and credits in the period, closing balance.
  Closing balances are shown on their natural side, so total debit = total credit.
- **Profit and loss** (`/reports/profit-and-loss?from=&to=`): income (credits minus debits) minus expenses (debits minus credits) for the period.
- **Balance sheet** (`/reports/balance-sheet?as_of=`): assets, liabilities and equity at a date. Profit and loss accounts are not closed to equity yet,
  so the sheet shows **current profit** (income minus expenses from the beginning to that date) and checks
  `Assets = Liabilities + Equity + current profit`.
- All three are **Admin only**, because they are the board's reports.

## Not counting group accounts twice
Heading accounts (1000 Assets, 4000 Income, 5000 Expenses ...) can never be posted to (the ledger refuses). Every total is added up from
**detail accounts only**. Headings appear only as subtotals of their children, so nothing is added twice. A contra asset such as 1590
Accumulated Depreciation (credit balance) comes out as a negative asset automatically. Tested.

## Results on the official books
| | Result |
|---|---|
| Trial balance | debits 1,518,309,423.07 = credits 1,518,309,423.07, difference 0.00 |
| Revenue | 1,260,930,052.00 (equal to a hand calculation from the CSV files) |
| Expenses | 1,036,246,464.42 (equal) |
| Profit | 224,683,587.58 (equal) |
| Balance sheet 30 Sep 2026 | assets 463,762,958.65 = liabilities 77,499,607.07 + equity 161,579,764.00 + profit 224,683,587.58, difference 0.00 |
| Every month end, Apr 2025 to Sep 2026 | balance sheet balances (18 of 18) |

## Think for yourself: profit of one department, without code
Cost side: payroll and expense journal lines already carry a department (`cost_center_department_id`), so I would add up that
department's expense lines for the period. What is missing:
1. **Revenue has no department.** Invoice lines are not tagged. I would need a rule linking each client or service line (revenue account 4001 to 4004) to a department.
2. **Shared costs** such as rent, internet, cloud hosting and insurance have no department. I would need an allocation rule (for example by headcount or floor space) and an owner who approves it.
3. People who work for several departments (assignments over time) and cost of unassigned staff.
4. Whether the board wants direct profit (revenue minus direct cost) or fully loaded profit after allocations.
