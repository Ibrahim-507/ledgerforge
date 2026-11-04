"""Task 14: the tax calculation as readable steps (annual taxable income -> slab tax -> rebate -> cess -> divide by 12)."""
from decimal import Decimal as D
from app import payroll_rules as R


def explain_tds(monthly_fixed_gross, variable_pay, payable_days, calendar_days, slabs, params) -> dict:
    sd, cess_pct, reb = params["standard_deduction"], params["health_education_cess_percent"], params["rebate_threshold_taxable"]
    cess = 1 + cess_pct / 100
    annual = D(str(monthly_fixed_gross)) * 12
    taxable = max(annual - sd, D(0))
    var = D(str(variable_pay))
    slab_rows, tax_before_relief = [], D(0)
    for lo, hi, rate in slabs:
        if taxable > lo:
            top = taxable if hi is None else min(taxable, hi)
            amount = (top - lo) * rate
            tax_before_relief += amount
            slab_rows.append({"from": lo, "to": hi, "rate_percent": rate * 100, "income_in_slab": top - lo, "tax": amount})
    t0 = R.annual_tax_with_relief(taxable, slabs, reb)
    t1 = R.annual_tax_with_relief(taxable + var, slabs, reb)
    share = D(str(payable_days)) / D(str(calendar_days))
    fixed_part = R.money(t0 * cess / 12 * share)
    variable_part = R.money((t1 - t0) * cess)
    steps = {
        "annual_fixed_income": annual, "standard_deduction": sd, "annual_taxable_income": taxable, "slab_lines": slab_rows,
        "slab_tax": tax_before_relief, "rebate_or_marginal_relief": tax_before_relief - t0, "tax_after_relief": t0,
        "cess_percent": cess_pct, "annual_tax_with_cess": t0 * cess, "monthly_tax_before_loss_of_pay": t0 * cess / 12,
        "payable_days": D(str(payable_days)), "calendar_days": D(str(calendar_days)), "fixed_part": fixed_part,
        "variable_pay": var, "extra_tax_on_variable_pay_with_cess": variable_part, "monthly_tds": fixed_part + variable_part}
    return steps


def explain_text(s: dict) -> str:
    f = lambda x: f"{D(str(x)):,.2f}"
    out = [f"Annual fixed income      {f(s['annual_fixed_income'])}", f"- standard deduction     {f(s['standard_deduction'])}",
           f"= taxable income         {f(s['annual_taxable_income'])}"]
    for r in s["slab_lines"]:
        out.append(f"  slab {r['rate_percent']:>4.0f}%  on {f(r['income_in_slab'])}  = {f(r['tax'])}")
    out += [f"Slab tax                 {f(s['slab_tax'])}", f"- rebate / marginal relief {f(s['rebate_or_marginal_relief'])}",
            f"+ cess {s['cess_percent']}%                {f(s['annual_tax_with_cess'] - s['tax_after_relief'])}",
            f"= annual tax             {f(s['annual_tax_with_cess'])}   /12 = {f(s['monthly_tax_before_loss_of_pay'])} a month",
            f"x paid days {s['payable_days']}/{s['calendar_days']}      = {f(s['fixed_part'])}",
            f"+ tax on bonus {f(s['variable_pay'])}   = {f(s['extra_tax_on_variable_pay_with_cess'])}",
            f"MONTHLY TDS              {f(s['monthly_tds'])}"]
    return "\n".join(out)
