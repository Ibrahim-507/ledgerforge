from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.models import Attendance


def monthly_summary(session, employee_id: str, year: int, month: int) -> dict:
    start = date(year, month, 1)
    calendar_days = monthrange(year, month)[1]
    end = date(year, month, calendar_days)
    where = [
        Attendance.employee_id == employee_id,
        Attendance.attendance_date.between(start, end),
    ]

    rows = session.execute(
        select(Attendance.status, func.count()).where(*where).group_by(Attendance.status)
    ).all()
    counts = {status: n for status, n in rows}

    late_days = session.scalar(
        select(func.count()).where(*where, Attendance.late_flag.is_(True))
    )
    missing = session.scalar(
        select(func.count()).where(*where, Attendance.data_quality_flag == "MISSING_CHECKOUT")
    )
    overtime = session.scalar(
        select(func.coalesce(func.sum(Attendance.overtime_hours), 0)).where(*where)
    )

    absent = counts.get("ABSENT_LOP", 0)
    unpaid = counts.get("UNPAID_LEAVE", 0)
    half_unpaid = counts.get("HALF_DAY_UNPAID", 0)

    return {
        "employee_id": employee_id,
        "month": f"{year}-{month:02d}",
        "calendar_days": calendar_days,
        "present_days": counts.get("PRESENT", 0),
        "wfh_days": counts.get("WFH", 0),
        "paid_leave_days": counts.get("PAID_LEAVE", 0),
        "unpaid_leave_days": unpaid,
        "absent_days": absent,
        "half_day_unpaid": half_unpaid,
        "lop_days": Decimal(absent + unpaid) + Decimal("0.5") * half_unpaid,
        "late_days": late_days,
        "overtime_hours": Decimal(str(overtime)),
        "missing_checkout_days": missing,
    }
