"""One small pure function per payroll rule. No database, no I/O.
All money is Decimal, rounded half-up to 2 places (README convention)."""
from decimal import Decimal as D, ROUND_HALF_UP

ZERO = D("0")
CENT = D("0.01")


def money(x) -> D:
    """Round to the paisa, half-up. Always build Decimals from strings."""
    return D(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


# ---- earnings -------------------------------------------------------------
def prorate(amount, payable_days, calendar_days) -> D:
    """Rule 1+2 (loss of pay): each fixed component is paid for payable days.
    amount x payable_days / calendar_days. LOP is charged per CALENDAR day."""
    return money(D(str(amount)) * D(str(payable_days)) / D(str(calendar_days)))


def overtime_pay(hours, monthly_fixed_gross, eligible: bool, rates) -> D:
    """Rule 3: only eligible roles; min(hours, 50) x (gross/208) x 2."""
    if not eligible:
        return ZERO
    h = min(D(str(hours)), rates["OT_MONTHLY_CAP_HOURS"])
    hourly = D(str(monthly_fixed_gross)) / rates["WORKING_HOURS_PER_MONTH"]
    return money(h * hourly * rates["OT_MULTIPLIER"])


def overtime_hours_paid(hours, eligible: bool, rates) -> D:
    return min(D(str(hours)), rates["OT_MONTHLY_CAP_HOURS"]) if eligible else ZERO


# ---- statutory deductions --------------------------------------------------
def pf_employee(basic_earned, pf_applicable: bool, rates) -> D:
    """Rule 6: 12% of basic, basic capped at 15,000. Only if employee is PF-applicable."""
    if not pf_applicable:
        return ZERO
    base = min(D(str(basic_earned)), rates["PF_WAGE_CEILING"])
    return money(base * rates["PF_EMPLOYEE_RATE"] / 100)


def pf_employer(basic_earned, pf_applicable: bool, rates) -> D:
    if not pf_applicable:
        return ZERO
    base = min(D(str(basic_earned)), rates["PF_WAGE_CEILING"])
    return money(base * rates["PF_EMPLOYER_RATE"] / 100)


def esi_employee(gross_pay, monthly_fixed_gross, esi_applicable: bool, rates) -> D:
    """Rule 7: 0.75% of gross pay, only if fixed gross <= 21,000 and employee ESI-applicable."""
    if not esi_applicable or D(str(monthly_fixed_gross)) > rates["ESI_WAGE_LIMIT"]:
        return ZERO
    return money(D(str(gross_pay)) * rates["ESI_EMPLOYEE_RATE"] / 100)


def esi_employer(gross_pay, monthly_fixed_gross, esi_applicable: bool, rates) -> D:
    if not esi_applicable or D(str(monthly_fixed_gross)) > rates["ESI_WAGE_LIMIT"]:
        return ZERO
    return money(D(str(gross_pay)) * rates["ESI_EMPLOYER_RATE"] / 100)


def professional_tax(gross_pay, rates) -> D:
    """Rule 8: 200 a month when gross pay >= 25,000 (exactly 25,000 pays)."""
    return rates["PT_MONTHLY"] if D(str(gross_pay)) >= rates["PT_GROSS_THRESHOLD"] else ZERO


# ---- income tax (TDS) -------------------------------------------------------
def slab_tax(taxable, slabs) -> D:
    """Unrounded tax on a yearly taxable income. slabs = [(from, to|None, rate_fraction)]."""
    taxable = D(str(taxable))
    tax = ZERO
    for lo, hi, rate in slabs:
        if taxable > lo:
            top = taxable if hi is None else min(taxable, hi)
            tax += (top - lo) * rate
    return tax


def annual_tax_with_relief(taxable, slabs, rebate_threshold) -> D:
    """Slab tax, with rebate: nothing up to 12 lakh, and marginal relief just above it
    (tax can never exceed the income above the threshold). Cess NOT included."""
    taxable = D(str(taxable))
    if taxable <= rebate_threshold:
        return ZERO
    return min(slab_tax(taxable, slabs), taxable - rebate_threshold)


def monthly_tds(monthly_fixed_gross, variable_pay, payable_days, calendar_days,
                slabs, params) -> D:
    """Rule 9 (verified on all 7,340 official rows):
    TDS = [ tax(fixed yearly taxable) / 12  x payable_days/calendar_days
          + (tax(fixed + variable) - tax(fixed)) ] x (1 + cess)
    where yearly taxable = fixed gross x 12 - standard deduction."""
    sd = params["standard_deduction"]
    cess = 1 + params["health_education_cess_percent"] / 100
    reb = params["rebate_threshold_taxable"]
    taxable = max(D(str(monthly_fixed_gross)) * 12 - sd, ZERO)
    var = D(str(variable_pay))
    t0 = annual_tax_with_relief(taxable, slabs, reb)
    t1 = annual_tax_with_relief(taxable + var, slabs, reb)
    share = D(str(payable_days)) / D(str(calendar_days))
    # round each part to the paisa separately, then add (this is what the official data does)
    return money(t0 * cess / 12 * share) + money((t1 - t0) * cess)
