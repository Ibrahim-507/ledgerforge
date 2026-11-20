"""Post one payroll run (from the Task 7 engine) into the ledger.
Debit the employer cost by department; credit what the company now owes:
  5001 Salaries & Wages        = earned fixed pay          2100 Net salaries payable = net pay
  5002 Overtime Expense        = overtime pay              2110 PF payable           = employee + employer PF
  5003 Incentives & Bonus      = variable pay              2120 ESI payable          = employee + employer ESI
  5004 Employer PF             = employer PF               2130 TDS payable          = income tax
  5005 Employer ESI            = employer ESI              2140 Professional tax payable
                                                           1300 Employee advances    = loan recovery"""
from collections import defaultdict
from decimal import Decimal as D
from app.ledger import create_journal_entry

DEBITS = [(5001, "Salaries & Wages", "earned_fixed_pay"), (5002, "Overtime Expense", "overtime_pay"),
          (5003, "Incentives & Bonus", "variable_pay"), (5004, "Employer PF Contribution", "pf_employer"),
          (5005, "Employer ESI Contribution", "esi_employer")]


def payroll_run_lines(source, run_id):
    """-> (lines, period_end). Totals come from the ENGINE, not from copied payroll data."""
    by_dept = defaultdict(lambda: defaultdict(D))
    cr = defaultdict(D)
    period_end = None
    rows = source.items[source.items.run_id == run_id]   # only this run's rows (fast)
    for r in rows.itertuples():
        p = source.calculate_row(r)
        period_end = r.period_end
        for _, _, f in DEBITS:
            by_dept[r.department_id][f] += getattr(p, f)
        cr[2100] += p.net_pay
        cr[2110] += p.pf_employee + p.pf_employer
        cr[2120] += p.esi_employee + p.esi_employer
        cr[2130] += p.tds
        cr[2140] += p.professional_tax
        cr[1300] += p.other_deductions
    if period_end is None:
        raise ValueError(f"No payroll rows for {run_id}")
    lines = []
    for dept in sorted(by_dept):
        for code, name, f in DEBITS:
            if by_dept[dept][f] > 0:
                lines.append({"account_code": code, "debit": by_dept[dept][f], "credit": 0,
                              "cost_center_department_id": dept, "line_description": f"{name} - {dept}"})
    names = {2100: "Net salaries payable", 2110: "PF payable (employee + employer)",
             2120: "ESI payable (employee + employer)", 2130: "TDS on salary payable",
             2140: "Professional tax payable", 1300: "Recovery of employee advances"}
    for code in (2100, 2110, 2120, 2130, 2140, 1300):
        if cr[code] > 0:
            lines.append({"account_code": code, "debit": 0, "credit": cr[code], "line_description": names[code]})
    return lines, period_end


def post_payroll_run(conn, source, run_id, created_by=None) -> str:
    lines, period_end = payroll_run_lines(source, run_id)
    return create_journal_entry(conn, period_end.date(), f"Payroll posting {run_id}", lines,
                                source_type="PAYROLL_RUN", source_id=run_id, created_by=created_by)
