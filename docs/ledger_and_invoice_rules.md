# Tasks 9-10 - Ledger and invoice rules (put these in the README)

## Debit and credit in plain words
Every money event has two sides. Debit = where value went / what the company now has or spent
(assets and expenses go up with a debit). Credit = where it came from / what the company now owes or earned
(liabilities, income and equity go up with a credit). Because every event is written twice, total debits
must always equal total credits: **Assets = Liabilities + Equity**.

## Rules the ledger enforces
1. **Balanced only.** An entry whose debits and credits differ is refused with a message such as
   `Entry is not balanced: total debits 100.00 != total credits 90.00 (difference 10.00)` and nothing is saved.
2. **Each line has one side**: a debit or a credit above zero, at most 2 decimals, never negative.
3. **Detail accounts only**: headings (1000, 2000 ...) and inactive or unknown accounts are refused.
4. **Posted entries are read-only.** `update_entry()` always refuses, and the database also blocks any
   UPDATE or DELETE on entries and lines (triggers). **Instead we offer `reverse_entry()`**: it posts a new entry with
   debits and credits swapped, linked to the original. The correct entry is then posted separately. History is never lost.
5. A reversal can be made once per entry, and a reversal cannot be reversed.
6. A payroll run, invoice or payment can be posted only once (unique source id).

## Payroll posting (one entry per run, by department)
Debit 5001 earned fixed pay, 5002 overtime, 5003 variable pay, 5004 employer PF, 5005 employer ESI.
Credit 2100 net pay, 2110 PF (employee + employer), 2120 ESI (employee + employer), 2130 TDS,
2140 professional tax, 1300 loan recovery. Verified: all 18 runs equal the official entries line by line.

## Invoices
Status flow: DRAFT -> SENT -> PARTIALLY_PAID -> PAID; SENT -> OVERDUE after the due date; DRAFT or SENT -> CANCELLED.
* Send: DR 1100 receivable (total) / CR revenue (subtotal) / CR 2200 GST (if any).
* Payment: DR 1001 bank / CR 1100 receivable. Overpayment refused.
* **Draft and cancelled-draft invoices never post.**
* **Think-for-yourself: cancelling a sent invoice.** The original entry stays. We post its reversal (receivable, income and GST
  all go back to 0), then mark the invoice CANCELLED with balance 0. If a payment already exists, cancelling is refused:
  refund the payment or issue a credit note first.
* Check 3: ledger account 1100 = sum of balance due on SENT, OVERDUE and PARTIALLY_PAID invoices.
