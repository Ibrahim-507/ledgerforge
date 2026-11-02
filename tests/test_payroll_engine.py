"""Whole-engine tests: full payslip for real rows, then ALL 7,340 rows against the answer key."""
from decimal import Decimal as D
from pathlib import Path
import pandas as pd
from app.payroll_data import PayrollSource

DATA = Path(__file__).resolve().parent.parent / "data"
src = PayrollSource(str(DATA))


def payslip(emp, run):
    return src.payslip(emp, run)[1]


def test_row1_full_payslip():
    p = payslip("EMP-0002", "PR-2025-04")
    assert (p.earned_fixed_pay, p.variable_pay, p.gross_pay) == (D("144460.00"), D("34670.40"), D("179130.40"))
    assert (p.pf_employee, p.esi_employee, p.professional_tax, p.tds) == (D("1800.00"), D("0"), D("200"), D("18625.79"))
    assert (p.total_deductions, p.net_pay) == (D("20625.79"), D("158504.61"))


def test_esi_and_overtime_row():
    p = payslip("EMP-0131", "PR-2025-04")           # fixed gross 19,383 + 9 h overtime + bonus
    assert p.overtime_pay == D("1677.38") and p.esi_employee == D("236.45") and p.net_pay == D("30160.39")


def test_mid_month_joiner_is_prorated():
    p = payslip("EMP-0319", "PR-2025-04")           # joined, 7 of 30 days
    assert p.earned_fixed_pay == D("8783.60") and p.net_pay == D("8361.98")


def test_lop_comes_from_attendance():
    r, p = src.payslip("EMP-0029", "PR-2025-04")    # one unpaid day in April 2025
    assert r.lop_days == 1.0 and r.payable_days == 29.0 and p.earned_fixed_pay == D("65166.87")


def test_every_official_row_matches():
    bad = 0
    key = src.items
    for r, p in src.all_rows():
        if abs(float(p.net_pay) - r.net_pay) > 0.005 or abs(float(p.total_deductions) - r.total_deductions) > 0.005 \
                or abs(float(p.gross_pay) - r.gross_pay) > 0.005:
            bad += 1
    assert len(key) == 7340
    assert bad / len(key) <= 0.01      # task target: 99%; we get 100%
