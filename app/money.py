"""Money helpers. Never use float for money: always Decimal."""
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def to_decimal(value) -> Decimal:
    """Text, int or Decimal -> Decimal. A float goes through str() so 0.1 stays 0.1."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value) -> Decimal:
    """Round to 2 decimals (paise), halves go up."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def format_inr(value) -> str:
    """Indian digit grouping: 123456 -> '1,23,456.00'."""
    amount = money(value)
    sign = "-" if amount < 0 else ""
    whole, fraction = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{whole}.{fraction}"
