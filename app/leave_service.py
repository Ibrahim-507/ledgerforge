from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.leave_days import count_leave_days
from app.models import Holiday, LeaveBalance, LeaveRequest, LeaveType

APPLIED, APPROVED, REJECTED = "Applied", "Approved", "Rejected"
LONG_LEAVE = "ML"  # holidays inside this leave are counted (checked on the data)

# leave type -> (balance column, used column) in leave_balances.
# Other types (ML, unpaid, ...) have no balance there, so they are not checked.
BALANCE_COLUMNS = {
    "CL": ("cl_balance", "cl_used"),
    "SL": ("sl_balance", "sl_used"),
    "EL": ("el_balance", "el_used_fy"),
}


class LeaveError(Exception):
    pass


class InsufficientBalance(LeaveError):
    pass


def _next_id(session) -> str:
    last = session.scalar(select(func.max(LeaveRequest.leave_request_id)))
    number = int(last.split("-")[1]) + 1 if last else 1
    return f"LR-{number:06d}"


def _check_balance(session, employee_id: str, code: str, days: Decimal) -> None:
    if code not in BALANCE_COLUMNS:
        return
    row = session.get(LeaveBalance, employee_id)
    if row is None:
        raise LeaveError(f"No leave balance found for {employee_id}")
    available = Decimal(str(getattr(row, BALANCE_COLUMNS[code][0])))
    if days > available:
        raise InsufficientBalance(
            f"Not enough {code} balance: requested {days}, available {available}"
        )


def apply_leave(session, employee_id, leave_type_code, start_date, end_date,
                reason=None, half_day=False, today=None) -> LeaveRequest:
    if end_date < start_date:
        raise LeaveError("End date is before start date")
    if session.get(LeaveType, leave_type_code) is None:
        raise LeaveError(f"Unknown leave type: {leave_type_code}")

    holidays = set(session.scalars(select(Holiday.holiday_date)))
    days = Decimal(count_leave_days(
        start_date, end_date, holidays, skip_holidays=(leave_type_code != LONG_LEAVE)
    ))
    if days == 0:
        raise LeaveError("No working days in this period")
    if half_day:
        if days != 1:
            raise LeaveError("A half day must be a single working day")
        days = Decimal("0.5")

    _check_balance(session, employee_id, leave_type_code, days)

    request = LeaveRequest(
        leave_request_id=_next_id(session),
        employee_id=employee_id,
        leave_type_code=leave_type_code,
        start_date=start_date,
        end_date=end_date,
        days=days,
        reason=reason,
        status=APPLIED,
        applied_on=today or date.today(),
    )
    session.add(request)
    session.commit()
    return request


def _get_open_request(session, request_id: str) -> LeaveRequest:
    request = session.get(LeaveRequest, request_id)
    if request is None:
        raise LeaveError(f"Leave request {request_id} not found")
    if request.status != APPLIED:
        raise LeaveError(f"Request {request_id} is already {request.status}")
    return request


def approve_leave(session, request_id, approver_id, today=None) -> LeaveRequest:
    request = _get_open_request(session, request_id)
    days = Decimal(str(request.days))
    code = request.leave_type_code
    _check_balance(session, request.employee_id, code, days)  # re-check at approval

    if code in BALANCE_COLUMNS:
        row = session.get(LeaveBalance, request.employee_id)
        bal_col, used_col = BALANCE_COLUMNS[code]
        setattr(row, bal_col, Decimal(str(getattr(row, bal_col))) - days)
        setattr(row, used_col, Decimal(str(getattr(row, used_col))) + days)

    request.status = APPROVED
    request.approver_id = approver_id
    request.decided_on = today or date.today()
    session.commit()
    return request


def reject_leave(session, request_id, approver_id, today=None) -> LeaveRequest:
    request = _get_open_request(session, request_id)
    request.status = REJECTED
    request.approver_id = approver_id
    request.decided_on = today or date.today()
    session.commit()
    return request
