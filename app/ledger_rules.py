"""Double-entry rules, kept free of the database so they are easy to test."""
from decimal import Decimal

from app.money import money


class UnbalancedEntry(Exception):
    pass


def validate_balanced(lines) -> Decimal:
    """lines = [{'account': '5001', 'debit': 100, 'credit': 0}, ...]

    Refuses an entry unless total debits equal total credits.
    Returns the total amount when it is fine.
    """
    if len(lines) < 2:
        raise UnbalancedEntry("An entry needs at least two lines")
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for line in lines:
        debit = money(line.get("debit") or 0)
        credit = money(line.get("credit") or 0)
        if debit < 0 or credit < 0:
            raise UnbalancedEntry("Debit and credit cannot be negative")
        if debit > 0 and credit > 0:
            raise UnbalancedEntry("A line cannot have both a debit and a credit")
        total_debit += debit
        total_credit += credit
    if total_debit != total_credit:
        raise UnbalancedEntry(f"Debits {total_debit} do not equal credits {total_credit}")
    return total_debit


def reversing_lines(lines):
    """A correction is a new entry with debit and credit swapped (never an edit)."""
    return [
        {**line, "debit": line.get("credit") or 0, "credit": line.get("debit") or 0}
        for line in lines
    ]
