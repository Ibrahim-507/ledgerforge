# Task 11 - Vendor bills: rules decided BEFORE coding

## Flow
`SUBMITTED -> APPROVED -> PAID`.  `SUBMITTED -> REJECTED` is a dead end. Nothing moves backwards; a posted bill is corrected only by a reversing entry.

## Ledger postings (same pattern as invoices, checked against the official books)
| Moment | Debit | Credit |
|---|---|---|
| Bill approved | Expense account (net amount, with department) + 1200 GST Input Credit (GST) | 2001 Accounts Payable (total) |
| Bill paid | 2001 Accounts Payable (total) | 1001 Bank (total) |
| Submitted or rejected | nothing | nothing |

The expense is counted **once, at approval**. Payment only clears the payable, so spend is never double counted.

## Think for yourself: stopping one person creating and approving a bill
**Rule: separation of duties.** The approver must be a different person from the submitter. `approve_bill` refuses with
`SeparationOfDutiesError` ("EMP-0001 submitted EXP-00001 and cannot also approve it") and changes nothing. In the API this is a 403.
Why at approval and not at payment? Approval is the moment the company accepts the debt; payment is only cash movement.

**Finding in the official data:** 14 of the 501 bills (EXP-00004, 00005, 00013, 00023, 00071, 00130, 00141, 00195, 00278, 00322, 00368,
00395, 00400, 00485) were approved by the person who submitted them. My controls would have blocked all 14. They total 5,861,315.50 rupees
(including GST). The history loader loads them anyway (history is history) but reports them as audit findings.

## Other controls
- A bill cannot be paid before approval, cannot be approved twice, cannot be paid twice, and cannot be paid before its own bill date.
- Inactive vendors, zero or negative amounts and unknown vendors are refused.

## Duplicate detector (challenge)
A new bill is a likely duplicate of an existing live (not rejected) bill of the **same vendor** when
(a) it has the same vendor bill number (ignoring case and spaces), or
(b) its amount is equal, or within 1%, and the dates are within 7 days.
Monthly bills such as rent are not flagged because they are about 30 days apart. The submitter may confirm a genuine repeat with `allow_duplicate=True`.
On the official data it finds exactly **one** pair: EXP-00099 (V-017, 14 Jul 2025, 257,350) looks like EXP-00090 (259,330, 7 days earlier).

## Checks
- Monthly totals of approved/paid bills equal `expenses.csv` for all 18 months (difference 0.00).
- Check 4: ledger 2001 Accounts Payable (11,646,021.20) equals the total of approved-but-unpaid bills.
