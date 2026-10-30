from decimal import Decimal

import pytest

from app.attendance_service import monthly_summary
from app.database import SessionLocal  # same import as in scripts/seed_time.py

# Hand counts from my Excel "handcounts" sheet.
# (employee, year, month, present, wfh, paid_leave, lop, late, overtime, missing_checkout)
# lop = UNPAID_LEAVE + ABSENT_LOP + 0.5 * HALF_DAY_UNPAID  (Excel columns J + K + 0.5 * L)
HAND_COUNTS = [
    ("EMP-0004", 2025, 9, 10, 11, 1, 0, 0, 0, 1),
    ("EMP-0026", 2025, 10, 8, 12, 0, 0, 1, 0, 1),
    ("EMP-0012", 2026, 2, 19, 0, 1, 0, 2, 0, 1),
]


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s


@pytest.mark.parametrize(
    "emp, year, month, present, wfh, paid, lop, late, overtime, missing", HAND_COUNTS
)
def test_summary_matches_hand_count(
    session, emp, year, month, present, wfh, paid, lop, late, overtime, missing
):
    r = monthly_summary(session, emp, year, month)
    assert r["present_days"] == present
    assert r["wfh_days"] == wfh
    assert r["paid_leave_days"] == paid
    assert r["lop_days"] == Decimal(str(lop))
    assert r["late_days"] == late
    assert r["overtime_hours"] == Decimal(str(overtime))
    assert r["missing_checkout_days"] == missing


def test_missing_checkout_day_counts_as_present_with_no_overtime(session):
    # 2025-09-30: EMP-0004 checked in but has no check-out (MISSING_CHECKOUT)
    r = monthly_summary(session, "EMP-0004", 2025, 9)
    assert r["missing_checkout_days"] == 1
    assert r["present_days"] >= 1


def test_days_never_exceed_calendar_days(session):
    r = monthly_summary(session, "EMP-0004", 2025, 9)
    counted = (
        r["present_days"] + r["wfh_days"] + r["paid_leave_days"]
        + r["unpaid_leave_days"] + r["absent_days"] + r["half_day_unpaid"]
    )
    assert counted <= r["calendar_days"]
    assert r["lop_days"] >= 0


def test_unknown_employee_gives_zeros(session):
    r = monthly_summary(session, "EMP-9999", 2025, 9)
    assert r["present_days"] == 0
    assert r["lop_days"] == 0