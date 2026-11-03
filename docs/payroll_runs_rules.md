# Task 12 - Payroll runs that post to the books once and only once

## Flow
`DRAFT -> PROCESSED -> APPROVED (posted) -> PAID`, and `APPROVED -> REVERSED`. Nothing else is allowed.

| Step | What happens | Who |
|---|---|---|
| create | One run per month. Key `payroll:2025-04:ZNT` is UNIQUE in the database. Creating the month again returns the same run. | payroll officer |
| process | Runs the Task 7 engine for every employee employed in the month (hire date on or before month end, exit on or after month start) and stores one row per employee. All or nothing. | payroll officer |
| approve | Posts ONE journal entry built from the stored rows and stores its id on the run. | a DIFFERENT person (separation of duties) |
| pay | Posts the salary payment: debit 2100 Salaries Payable, credit 1001 Bank. | approver / finance |
| reverse | Posts the mirror entry and marks the run REVERSED. | approver |

## Idempotency (a double click must not double post) - three layers
1. The run's `idempotency_key` is UNIQUE, so the same month cannot create two runs.
2. `approve_run` on an already approved run returns the existing journal entry and posts nothing.
3. The database refuses a second journal entry with the same source (`PAYROLL_RUN` + run id), even if code is called directly.

## Think for yourself: what if the ledger post fails halfway?
**Rule: all or nothing.** The journal entry, its lines, the journal id on the run and the status change happen in ONE
transaction. If any part fails, everything is rolled back:
- the run stays PROCESSED, `journal_entry_id` stays empty, and no half-written entry exists;
- the reason is written to the run's `error_message` so finance can see it;
- approving again is safe (retry), because nothing was posted. After the fix it posts once and clears the error.
Tested by making account 5003 inactive, approving (fails), then reactivating and approving again.

## Reversal (challenge)
`reverse_run` is allowed only on an APPROVED run. It posts the mirror entry (debits and credits swapped), so every account returns to
its earlier balance, and keeps both entries (history is never deleted). A PAID run is refused: salaries already left the bank, which
needs a separate recovery process. A reversed month can be run again as `PR-2025-04-R1` (key `payroll:2025-04:ZNT:R1`), and the ledger then
counts the month once.

## Posting uses the stored rows, not a fresh calculation
Rules are frozen per month: after a run is processed, a later change to a rate can never alter its posting.

## Results
- All 18 months processed, approved and posted; 17 paid and the last left approved, like the official data.
- Check 2: ledger entry total = run total (employer cost) for every month, difference 0.00.
- Running all 18 months a second time posts nothing new (35 entries before and after).
- Each run's totals, employee count, key, pay date and journal lines equal the official `payroll_runs` and journal entries.
