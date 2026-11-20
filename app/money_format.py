from decimal import Decimal as D, ROUND_HALF_UP


def inr(amount) -> str:
    """Indian digit grouping: 123456 -> '1,23,456.00', 12345678.9 -> '1,23,45,678.90'."""
    d = D(str(amount)).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if d < 0 else ""
    whole, frac = f"{abs(d):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{sign}{whole}.{frac}"
