from datetime import date, timedelta


def count_leave_days(
    start: date, end: date, holidays: set[date], skip_holidays: bool = True
) -> int:
    """Working days from start to end (both included).

    Weekends are never counted. Holidays are skipped unless skip_holidays=False
    (used for leave types whose policy counts holidays inside the leave).
    """
    days = 0
    day = start
    while day <= end:
        if day.weekday() < 5 and (not skip_holidays or day not in holidays):
            days += 1
        day += timedelta(days=1)
    return days
