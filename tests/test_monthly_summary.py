import pytest
from app.database import SessionLocal          # CHANGE if your session lives elsewhere
from app.attendance_service import monthly_summary

# (employee, year, month, present, wfh, paid_leave, lop, late, missing)
HAND_COUNTS = [
    ("EMP-0004", 2025, 9, 10, 11, 1, 0, 0, 1),
    # ("EMP-0026", 2025, 10, ...),   # fill from your Excel table
    # ("EMP-0012", 2026, 2, ...),    # fill from your Excel table
]

@pytest.mark.parametrize("emp, y, m, present, wfh, paid, lop, late, missing", HAND_COUNTS)
def test_summary_matches_hand_count(emp, y, m, present, wfh, paid, lop, late, missing):
    with SessionLocal() as s:
        r = monthly_summary(s, emp, y, m)
    assert r["present_days"] == present
    assert r["wfh_days"] == wfh
    assert r["paid_leave_days"] == paid
    assert r["lop_days"] == lop
    assert r["late_days"] == late
    assert r["missing_checkout_days"] == missing