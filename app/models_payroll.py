"""Tables for payroll_runs and payroll_items (the official payroll data, stored for payslips)."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

MONEY = Numeric(14, 2)


class PayrollRun(Base):
    __tablename__ = "payroll_runs"

    run_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    pay_date: Mapped[date | None] = mapped_column(Date)
    employees_paid: Mapped[int]
    total_gross: Mapped[Decimal] = mapped_column(MONEY)
    total_deductions: Mapped[Decimal] = mapped_column(MONEY)
    total_net: Mapped[Decimal] = mapped_column(MONEY)
    total_employer_contributions: Mapped[Decimal] = mapped_column(MONEY)
    total_employer_cost: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(40))
    run_by: Mapped[str | None] = mapped_column(String(20))
    approved_by: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    idempotency_key: Mapped[str | None] = mapped_column(String(60))
    journal_entry_id: Mapped[str | None] = mapped_column(String(20))
    calculation_version: Mapped[str | None] = mapped_column(String(40))


class PayrollItem(Base):
    __tablename__ = "payroll_items"

    payroll_item_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("payroll_runs.run_id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    department_id: Mapped[str | None] = mapped_column(String(10))
    role_id: Mapped[str | None] = mapped_column(String(10))
    calendar_days: Mapped[int]
    days_employed: Mapped[int]
    lop_days: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    payable_days: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    monthly_fixed_gross: Mapped[Decimal] = mapped_column(MONEY)
    basic: Mapped[Decimal] = mapped_column(MONEY)
    hra: Mapped[Decimal] = mapped_column(MONEY)
    conveyance: Mapped[Decimal] = mapped_column(MONEY)
    medical: Mapped[Decimal] = mapped_column(MONEY)
    special_allowance: Mapped[Decimal] = mapped_column(MONEY)
    earned_fixed_pay: Mapped[Decimal] = mapped_column(MONEY)
    overtime_hours_paid: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    overtime_pay: Mapped[Decimal] = mapped_column(MONEY)
    variable_pay: Mapped[Decimal] = mapped_column(MONEY)
    variable_pay_type: Mapped[str | None] = mapped_column(String(60))
    gross_pay: Mapped[Decimal] = mapped_column(MONEY)
    pf_employee: Mapped[Decimal] = mapped_column(MONEY)
    esi_employee: Mapped[Decimal] = mapped_column(MONEY)
    professional_tax: Mapped[Decimal] = mapped_column(MONEY)
    tds: Mapped[Decimal] = mapped_column(MONEY)
    other_deductions: Mapped[Decimal] = mapped_column(MONEY)
    total_deductions: Mapped[Decimal] = mapped_column(MONEY)
    net_pay: Mapped[Decimal] = mapped_column(MONEY)
    pf_employer: Mapped[Decimal] = mapped_column(MONEY)
    esi_employer: Mapped[Decimal] = mapped_column(MONEY)
    employer_cost: Mapped[Decimal] = mapped_column(MONEY)
    calculation_note: Mapped[str | None] = mapped_column(String(255))