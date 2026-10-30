from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.leave_service import (
    APPLIED, APPROVED, REJECTED, InsufficientBalance, LeaveError,
    apply_leave, approve_leave, reject_leave,
)
from app.models import Base, Holiday, LeaveBalance, LeaveRequest, LeaveType

EMP = "EMP-TEST"
HOLIDAY = date(2026, 3, 4)   # a Wednesday


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        s.add(Holiday(holiday_date=HOLIDAY, holiday_name="Test holiday",
                      holiday_type="National", falls_on_weekend=False))
        for code, name in [("CL", "Casual Leave"), ("ML", "Maternity Leave")]:
            s.add(LeaveType(leave_type_code=code, leave_type_name=name, pay_type="Paid",
                            annual_quota_days=12, prorated_for_joiners=False,
                            carry_forward_allowed=False, max_carry_forward_days=0))
        s.add(LeaveBalance(
            employee_id=EMP, as_of_date=date(2026, 3, 1), financial_year="FY2025-26",
            cl_entitlement=Decimal("12"), cl_used=Decimal("0"), cl_balance=Decimal("12"),
            sl_entitlement=Decimal("12"), sl_used=Decimal("0"), sl_balance=Decimal("12"),
            el_used_fy=Decimal("0"), el_balance=Decimal("30"), pending_days=Decimal("0"),
        ))
        s.commit()
        yield s


def bal(db):
    return db.get(LeaveBalance, EMP)


def test_weekends_and_holidays_are_not_counted(db):
    r = apply_leave(db, EMP, "CL", date(2026, 3, 2), date(2026, 3, 6))  # Mon-Fri, Wed is a holiday
    assert r.days == Decimal("4")
    assert r.status == APPLIED and r.leave_request_id.startswith("LR-")
    r2 = apply_leave(db, EMP, "CL", date(2026, 3, 6), date(2026, 3, 9))  # Fri to Mon
    assert r2.days == Decimal("2")


def test_applying_does_not_change_the_balance(db):
    apply_leave(db, EMP, "CL", date(2026, 3, 2), date(2026, 3, 6))
    assert bal(db).cl_balance == Decimal("12")


def test_approving_reduces_the_balance(db):
    r = apply_leave(db, EMP, "CL", date(2026, 3, 2), date(2026, 3, 6))
    approve_leave(db, r.leave_request_id, "EMP-BOSS", today=date(2026, 3, 10))
    assert r.status == APPROVED and r.decided_on == date(2026, 3, 10)
    assert bal(db).cl_balance == Decimal("8")
    assert bal(db).cl_used == Decimal("4")


def test_not_enough_balance_is_rejected(db):
    bal(db).cl_balance = Decimal("2")
    db.commit()
    with pytest.raises(InsufficientBalance):
        apply_leave(db, EMP, "CL", date(2026, 3, 2), date(2026, 3, 6))
    assert db.scalar(select(func.count()).select_from(LeaveRequest)) == 0


def test_two_requests_cannot_overspend_the_balance(db):
    bal(db).cl_balance = Decimal("5")
    db.commit()
    a = apply_leave(db, EMP, "CL", date(2026, 3, 2), date(2026, 3, 6))   # 4 days
    b = apply_leave(db, EMP, "CL", date(2026, 3, 9), date(2026, 3, 12))  # 4 days
    approve_leave(db, a.leave_request_id, "EMP-BOSS")
    assert bal(db).cl_balance == Decimal("1")
    with pytest.raises(InsufficientBalance):
        approve_leave(db, b.leave_request_id, "EMP-BOSS")
    assert b.status == APPLIED


def test_a_request_cannot_be_decided_twice(db):
    r = apply_leave(db, EMP, "CL", date(2026, 3, 2), date(2026, 3, 6))
    approve_leave(db, r.leave_request_id, "EMP-BOSS")
    with pytest.raises(LeaveError):
        approve_leave(db, r.leave_request_id, "EMP-BOSS")
    assert bal(db).cl_balance == Decimal("8")      # taken only once


def test_rejecting_keeps_the_balance(db):
    r = apply_leave(db, EMP, "CL", date(2026, 3, 2), date(2026, 3, 6))
    reject_leave(db, r.leave_request_id, "EMP-BOSS")
    assert r.status == REJECTED
    assert bal(db).cl_balance == Decimal("12")


def test_bad_input_is_refused(db):
    with pytest.raises(LeaveError):
        apply_leave(db, EMP, "XX", date(2026, 3, 2), date(2026, 3, 3))      # unknown type
    with pytest.raises(LeaveError):
        apply_leave(db, EMP, "CL", date(2026, 3, 6), date(2026, 3, 2))      # end before start
    with pytest.raises(LeaveError):
        apply_leave(db, EMP, "CL", date(2026, 3, 7), date(2026, 3, 8))      # weekend only


def test_long_leave_counts_holidays_and_has_no_balance_check(db):
    r = apply_leave(db, EMP, "ML", date(2026, 3, 2), date(2026, 3, 6))
    assert r.days == Decimal("5")                   # the Wednesday holiday is counted
    approve_leave(db, r.leave_request_id, "EMP-BOSS")
    assert bal(db).cl_balance == Decimal("12")


def test_half_day_leave(db):
    r = apply_leave(db, EMP, "CL", date(2026, 3, 2), date(2026, 3, 2), half_day=True)
    assert r.days == Decimal("0.5")
    approve_leave(db, r.leave_request_id, "EMP-BOSS")
    assert bal(db).cl_balance == Decimal("11.5")
    with pytest.raises(LeaveError):
        apply_leave(db, EMP, "CL", date(2026, 3, 2), date(2026, 3, 3), half_day=True)
