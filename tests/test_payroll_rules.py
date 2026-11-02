"""One small test per payroll rule, each from a REAL row of payroll_items (the answer key).
Run from the project root so data/ is found."""
from decimal import Decimal as D
from pathlib import Path
import pytest
from app import payroll_rules as R
from app.payroll_engine import load_rates

DATA = Path(__file__).resolve().parent.parent / "data"
rates, params, slabs = load_rates(str(DATA))
FY25 = slabs["FY2025-26"]


def test_float_problem_and_decimal_fix():
    assert 0.1 + 0.2 != 0.3                    # float: 0.30000000000000004
    assert D("0.1") + D("0.2") == D("0.3")     # Decimal: exact
    assert R.money("1234.565") == D("1234.57") # half-up to the paisa


def test_rule1_loss_of_pay_is_per_calendar_day():
    # EMP-0029, Apr 2025: 1 LOP day in a 30-day month -> basic 26,966 x 29/30 = 26,067.13
    assert R.prorate(26966, 29, 30) == D("26067.13")
    assert R.prorate(26966, 30, 30) == D("26966.00")            # no LOP: full pay
    assert R.prorate(26966, 29.5, 30) == D("26516.57")          # half-day unpaid = 0.5 day


def test_rule3_overtime_hours_x_hourly_x_2():
    # EMP-0201: 29 h, fixed gross 39,286 -> 29 x (39286/208) x 2 = 10,954.75
    assert R.overtime_pay(29, 39286, True, rates) == D("10954.75")


def test_rule3_overtime_cap_and_eligibility():
    assert R.overtime_pay(60, 39286, True, rates) == R.overtime_pay(50, 39286, True, rates)  # cap 50 h
    assert R.overtime_pay(29, 39286, False, rates) == D("0")                                  # not eligible


def test_rule6_pf_is_12_percent_of_basic_capped_at_15000():
    assert R.pf_employee("41575.00", True, rates) == D("1800.00")   # EMP-0004: capped
    assert R.pf_employee("7296.00", True, rates) == D("875.52")     # below cap: 12% of basic
    assert R.pf_employee("7296.00", False, rates) == D("0")         # EMP-0089 is not PF-applicable


def test_rule7_esi_only_when_fixed_gross_within_21000():
    # EMP-0131: gross 31,527.20, fixed gross 19,383 -> 0.75% = 236.45
    assert R.esi_employee("31527.20", 19383, True, rates) == D("236.45")
    assert R.esi_employee("21600.04", 21093, True, rates) == D("0")  # EMP-0415: fixed gross above 21,000
    assert R.esi_employee("31527.20", 19383, False, rates) == D("0") # not enrolled


def test_rule8_professional_tax_from_25000():
    assert R.professional_tax("25000.00", rates) == D("200")
    assert R.professional_tax("24999.99", rates) == D("0")


def test_rule9_tds_row1_matches_answer_key():
    # EMP-0002, Apr 2025: tax on 16,58,520 = 1,31,704 + 4% cess /12 = 11,414.35; bonus 34,670.40 x 20% x 1.04 = 7,211.44
    assert R.monthly_tds(144460, "34670.40", 30, 30, FY25, params) == D("18625.79")


def test_rule9_tds_marginal_relief():
    # EMP-0004: fixed part is under the 12 lakh rebate, the bonus pushes income just above it.
    assert R.monthly_tds(103938, "56126.52", 30, 30, FY25, params) == D("29517.82")


def test_rule9_tds_zero_when_income_under_rebate_limit():
    assert R.monthly_tds(53915, 0, 30, 30, FY25, params) == D("0")          # EMP-0012
    assert R.monthly_tds(67414, "52582.92", 29, 30, FY25, params) == D("0") # EMP-0029


def test_rule9_tds_fixed_part_is_prorated_for_lop():
    full = R.monthly_tds(110669, 0, 30, 30, FY25, params)
    lop = R.monthly_tds(110669, 0, 28, 30, FY25, params)     # EMP-0147: 28 of 30 days
    assert lop == D("4289.38") and lop < full
