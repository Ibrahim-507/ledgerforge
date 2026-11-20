"""Payroll engine: employee + month in, payslip numbers out. A PURE function:
same input, same output, no database access inside."""
from dataclasses import dataclass, asdict
from decimal import Decimal as D
from pathlib import Path
import pandas as pd
from app import payroll_rules as R

COMPONENTS = {"BASIC": "basic", "HRA": "hra", "CONV": "conveyance",
              "MED": "medical", "SPECIAL": "special_allowance"}


def load_rates(data_dir="data"):
    p = Path(data_dir)
    sr = pd.read_csv(p / "statutory_rates.csv")
    rates = {r.parameter: D(str(r.value)) for r in sr.itertuples()}
    tp = pd.read_csv(p / "tax_parameters.csv")
    params = {r.parameter: D(str(r.value)) for r in tp.itertuples()}
    ts = pd.read_csv(p / "tax_slabs.csv")
    slabs = {}
    for fy, g in ts.groupby("financial_year"):
        g = g.sort_values("income_from")
        slabs[fy] = [(D(str(a)), None if pd.isna(b) else D(str(b)), D(str(r)) / 100)
                     for a, b, r in zip(g.income_from, g.income_to, g.rate_percent)]
    return rates, params, slabs


def financial_year(d) -> str:
    y = d.year if d.month >= 4 else d.year - 1
    return f"FY{y}-{str(y + 1)[2:]}"


@dataclass(frozen=True)
class Payslip:
    monthly_fixed_gross: D
    basic: D; hra: D; conveyance: D; medical: D; special_allowance: D
    earned_fixed_pay: D
    overtime_hours_paid: D
    overtime_pay: D
    variable_pay: D
    gross_pay: D
    pf_employee: D
    esi_employee: D
    professional_tax: D
    tds: D
    other_deductions: D
    total_deductions: D
    net_pay: D
    pf_employer: D
    esi_employer: D
    employer_cost: D

    def as_dict(self):
        return {k: float(v) for k, v in asdict(self).items()}


def calculate_employee_month(*, components, payable_days, calendar_days, period_start,
                             overtime_hours=0, overtime_eligible=False, variable_pay=0,
                             other_deductions=0, pf_applicable=True, esi_applicable=False,
                             rates, params, slabs) -> Payslip:
    """components: {'BASIC': 40000, 'HRA': ..., 'CONV':..., 'MED':..., 'SPECIAL':...} full monthly amounts."""
    full = {c: D(str(components[c])) for c in COMPONENTS}
    fixed_gross = sum(full.values())
    earned = {c: R.prorate(v, payable_days, calendar_days) for c, v in full.items()}
    earned_fixed = sum(earned.values())

    ot_hours = R.overtime_hours_paid(overtime_hours, overtime_eligible, rates)
    ot = R.overtime_pay(overtime_hours, fixed_gross, overtime_eligible, rates)
    var = R.money(variable_pay)
    gross = earned_fixed + ot + var

    pf = R.pf_employee(earned["BASIC"], pf_applicable, rates)
    esi = R.esi_employee(gross, fixed_gross, esi_applicable, rates)
    pt = R.professional_tax(gross, rates)
    tds = R.monthly_tds(fixed_gross, var, payable_days, calendar_days,
                        slabs[financial_year(period_start)], params)
    other = R.money(other_deductions)
    total_ded = pf + esi + pt + tds + other
    pf_er = R.pf_employer(earned["BASIC"], pf_applicable, rates)
    esi_er = R.esi_employer(gross, fixed_gross, esi_applicable, rates)

    return Payslip(fixed_gross, earned["BASIC"], earned["HRA"], earned["CONV"], earned["MED"],
                   earned["SPECIAL"], earned_fixed, ot_hours, ot, var, gross, pf, esi, pt, tds,
                   other, total_ded, gross - total_ded, pf_er, esi_er, gross + pf_er + esi_er)
