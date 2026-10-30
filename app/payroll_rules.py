"""One small function per payroll rule (pure functions: same input, same output).

FIRST DRAFT from the Conventions sheet. Always confirm each rule against real
rows of payroll_items (the answer key) before you trust it.
Rates are passed in as arguments: read them from the statutory_rates sheet,
do not hard-code them in your engine.
"""
from decimal import Decimal

from app.money import money, to_decimal

ZERO = Decimal("0.00")


def loss_of_pay(monthly_gross, calendar_days, lop_days) -> Decimal:
    """Pay cut for unpaid days: monthly fixed gross / calendar days x LOP days."""
    return money(to_decimal(monthly_gross) * to_decimal(lop_days) / to_decimal(calendar_days))


def overtime_pay(monthly_gross, overtime_hours, eligible, cap_hours=50,
                 hours_divisor=208, multiplier=2) -> Decimal:
    """Only for overtime-eligible roles: hours x (gross / 208) x 2, at most 50 hours."""
    if not eligible:
        return ZERO
    hours = min(to_decimal(overtime_hours), to_decimal(cap_hours))
    return money(
        to_decimal(monthly_gross) * hours * to_decimal(multiplier) / to_decimal(hours_divisor)
    )


def pf_employee(basic, rate="0.12", basic_cap="15000") -> Decimal:
    """Provident fund: 12% of basic, where basic is capped at 15,000."""
    return money(min(to_decimal(basic), to_decimal(basic_cap)) * to_decimal(rate))


def esi(monthly_gross, wage_limit="21000", employee_rate="0.0075", employer_rate="0.0325"):
    """ESI applies only when monthly fixed gross <= 21,000. Returns (employee, employer)."""
    gross = to_decimal(monthly_gross)
    if gross > to_decimal(wage_limit):
        return ZERO, ZERO
    return money(gross * to_decimal(employee_rate)), money(gross * to_decimal(employer_rate))


def professional_tax(monthly_gross, threshold="25000", amount="200") -> Decimal:
    """Flat 200 a month from 25,000 gross. CHECK in the answer key whether 25,000 itself pays."""
    return money(amount) if to_decimal(monthly_gross) >= to_decimal(threshold) else ZERO


def slab_tax(taxable_income, slabs) -> Decimal:
    """Progressive tax. slabs = [(lower, upper_or_None, rate), ...], rate like 0.05.

    Each rate applies only to the part of income inside its band.
    """
    income = to_decimal(taxable_income)
    tax = Decimal("0")
    for lower, upper, rate in slabs:
        lower = to_decimal(lower)
        if income <= lower:
            break
        top = income if upper is None else min(income, to_decimal(upper))
        tax += (top - lower) * to_decimal(rate)
    return money(tax)


def add_cess_after_rebate(tax, taxable_income, rebate_limit, cess_rate="0.04") -> Decimal:
    """No tax at or below the rebate limit, otherwise tax + cess. CHECK marginal relief in your data."""
    if to_decimal(taxable_income) <= to_decimal(rebate_limit):
        return ZERO
    return money(to_decimal(tax) * (1 + to_decimal(cess_rate)))
