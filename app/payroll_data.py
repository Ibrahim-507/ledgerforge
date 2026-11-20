"""Gathers every input the payroll engine needs for one employee-month and runs the engine.
Reads the dataset CSVs (swap the loaders for DB queries when your tables are ready - the engine
itself never touches data)."""
from functools import cached_property
from decimal import Decimal as D
import pandas as pd
from app.payroll_engine import calculate_employee_month, load_rates, COMPONENTS, Payslip
from app.attendance_rules import monthly_inputs


class PayrollSource:
    def __init__(self, data_dir="data", own_inputs=True):
        self.dir = data_dir
        self.own_inputs = own_inputs   # True: LOP/overtime/days computed from attendance
        self.rates, self.params, self.slabs = load_rates(data_dir)

    # ---- loading -----------------------------------------------------------------------
    @cached_property
    def items(self) -> pd.DataFrame:
        """The payroll_items rows (employee-month list + inputs that are decisions, not
        formulas: variable pay, loan recovery). With own_inputs=True days/LOP/OT are recomputed."""
        k = pd.read_csv(f"{self.dir}/payroll_items.csv", parse_dates=["period_start", "period_end"])
        emp = pd.read_csv(f"{self.dir}/employees.csv")[["employee_id", "pf_applicable", "esi_applicable"]]
        roles = pd.read_csv(f"{self.dir}/roles.csv")[["role_id", "overtime_eligible"]]
        k = k.merge(emp, on="employee_id").merge(roles, on="role_id")
        limit = float(self.rates["ESI_WAGE_LIMIT"])
        # ESI enrolment: employees.esi_applicable shows status at the cut-off date. Employees who
        # were within the limit and later outgrew it have flag N but paid ESI in the official data.
        ss = self.structures
        latest = ss[ss.effective_from == ss.groupby("employee_id").effective_from.transform("max")]
        latest_fixed = latest.groupby("employee_id").monthly_amount.sum()
        k["esi_enrolled"] = (k.esi_applicable == "Y") | (
            (k.monthly_fixed_gross <= limit) & k.employee_id.map(latest_fixed).gt(limit))
        if self.own_inputs:
            k = monthly_inputs(k, self.dir)
        return k.reset_index(drop=True)

    @cached_property
    def structures(self) -> pd.DataFrame:
        s = pd.read_csv(f"{self.dir}/salary_structures.csv", parse_dates=["effective_from", "effective_to"])
        return s[s.component_id.isin(COMPONENTS)]

    @cached_property
    def _by_emp(self):
        return {k: v for k, v in self.structures.groupby("employee_id")}

    def structure(self, employee_id, start, end) -> dict:
        """Full monthly components in force during the month (the latest revision that overlaps it)."""
        x = self._by_emp[employee_id]
        x = x[(x.effective_from <= end) & (x.effective_to.isna() | (x.effective_to >= start))]
        x = x[x.effective_from == x.effective_from.max()]
        return x.set_index("component_id").monthly_amount.to_dict()

    # ---- running -----------------------------------------------------------------------
    def calculate_row(self, r) -> Payslip:
        return calculate_employee_month(
            components=self.structure(r.employee_id, r.period_start, r.period_end),
            payable_days=r.payable_days, calendar_days=r.calendar_days, period_start=r.period_start,
            overtime_hours=r.overtime_hours_paid, overtime_eligible=(r.overtime_eligible == "Y"),
            variable_pay=r.variable_pay, other_deductions=r.other_deductions,
            pf_applicable=(r.pf_applicable == "Y"), esi_applicable=bool(r.esi_enrolled),
            rates=self.rates, params=self.params, slabs=self.slabs)

    def all_rows(self):
        for r in self.items.itertuples():
            yield r, self.calculate_row(r)

    def payslip(self, employee_id, run_id):
        """-> (row, Payslip) for one employee and payroll run, or None if there is no such row."""
        m = self.items[(self.items.employee_id == employee_id) & (self.items.run_id == run_id)]
        if m.empty:
            return None
        r = next(m.itertuples())
        return r, self.calculate_row(r)
