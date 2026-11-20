# Task 5 notes: salary structures and revisions

## A raise is effective on 1 January: what is the pay on 31 December and on 1 January?
Pay on 31 December is the OLD amount, because the old row is valid up to and including 31 December.
Pay on 1 January is the NEW amount, because the new row is valid from 1 January.
The old row ends the day before the new row starts, so there is no overlap and no gap.

## How it works
- get_structure(employee_id, date) returns the pay rows where effective_from <= date and (effective_to is empty or effective_to >= date).
- revise_salary() closes the current rows the day before the raise and opens new rows on the effective date. Old rows are never deleted or overwritten.
- Money uses Decimal, never float.
- revise_salary scales earning components in proportion and puts the rounding difference on the largest component.