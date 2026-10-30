from decimal import Decimal

import pytest

from app.ledger_rules import UnbalancedEntry, reversing_lines, validate_balanced
from app.money import format_inr, money
from app.payroll_rules import (
    add_cess_after_rebate, esi, loss_of_pay, overtime_pay, pf_employee,
    professional_tax, slab_tax,
)

D = Decimal


def test_float_problem_and_decimal_fix():
    assert 0.1 + 0.2 != 0.3                       # floats are wrong for money
    assert D("0.1") + D("0.2") == D("0.3")        # Decimal is exact


def test_money_rounds_half_up_to_paise():
    assert money("10.005") == D("10.01")
    assert money(0.1) == D("0.10")


def test_indian_number_format():
    assert format_inr(123456) == "1,23,456.00"
    assert format_inr("1234567.5") == "12,34,567.50"
    assert format_inr(999) == "999.00"
    assert format_inr(1000) == "1,000.00"
    assert format_inr(-45000) == "-45,000.00"


# These use made-up numbers to test the formulas.
# ADD one test per rule that uses a REAL payroll_items row.
def test_loss_of_pay_is_per_calendar_day():
    assert loss_of_pay(30000, 30, 2) == D("2000.00")
    assert loss_of_pay(50000, 31, D("0.5")) == D("806.45")


def test_overtime_only_for_eligible_roles_and_capped():
    assert overtime_pay(20800, 10, eligible=False) == D("0.00")
    assert overtime_pay(20800, 10, eligible=True) == D("2000.00")        # 10 x 100 x 2
    assert overtime_pay(20800, 80, eligible=True) == D("10000.00")       # capped at 50 hours


def test_pf_is_12_percent_of_basic_with_cap():
    assert pf_employee(10000) == D("1200.00")
    assert pf_employee(40000) == D("1800.00")                            # basic capped at 15,000


def test_esi_only_up_to_21000():
    assert esi(20000) == (D("150.00"), D("650.00"))
    assert esi(21000) == (D("157.50"), D("682.50"))
    assert esi(21001) == (D("0.00"), D("0.00"))


def test_professional_tax():
    assert professional_tax(24999) == D("0.00")
    assert professional_tax(25000) == D("200.00")


def test_slab_tax_taxes_each_band_only():
    slabs = [(0, 300000, "0"), (300000, 700000, "0.05"), (700000, None, "0.10")]
    assert slab_tax(250000, slabs) == D("0.00")
    assert slab_tax(500000, slabs) == D("10000.00")
    assert slab_tax(900000, slabs) == D("40000.00")


def test_rebate_and_cess():
    assert add_cess_after_rebate(10000, 700000, 700000) == D("0.00")
    assert add_cess_after_rebate(40000, 900000, 700000) == D("41600.00")


# ---- ledger rules
def test_balanced_entry_is_accepted():
    lines = [{"account": "5001", "debit": 1000, "credit": 0},
             {"account": "2001", "debit": 0, "credit": 1000}]
    assert validate_balanced(lines) == D("1000.00")


@pytest.mark.parametrize("lines", [
    [{"debit": 1000, "credit": 0}, {"debit": 0, "credit": 900}],      # not equal
    [{"debit": 1000, "credit": 0}],                                   # one line only
    [{"debit": 100, "credit": 100}, {"debit": 0, "credit": 0}],       # both sides on a line
    [{"debit": -5, "credit": 0}, {"debit": 0, "credit": -5}],         # negative
])
def test_unbalanced_entries_are_refused(lines):
    with pytest.raises(UnbalancedEntry):
        validate_balanced(lines)


def test_reversal_swaps_debit_and_credit():
    lines = [{"account": "5001", "debit": 500, "credit": 0},
             {"account": "2001", "debit": 0, "credit": 500}]
    undo = reversing_lines(lines)
    assert undo[0]["credit"] == 500 and undo[1]["debit"] == 500
    validate_balanced(undo)
