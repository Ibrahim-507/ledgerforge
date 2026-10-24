from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SalaryRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    structure_id: str
    component_id: str
    component_name: str
    component_type: str | None = None
    monthly_amount: Decimal
    effective_from: date
    effective_to: date | None = None
    revision_id: str | None = None


class SalaryOnDate(BaseModel):
    employee_id: str
    on_date: date
    components: list[SalaryRow]
    monthly_earnings: Decimal
    annual_earnings: Decimal


class RevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    revision_id: str
    employee_id: str
    effective_from: date
    revision_reason: str
    previous_annual_fixed: Decimal | None = None
    new_annual_fixed: Decimal
    pct_change: Decimal | None = None
    role_id_after: str | None = None
    approved_by: str | None = None


class RevisionCreate(BaseModel):
    effective_from: date
    new_annual_fixed: Decimal = Field(gt=0)
    revision_reason: str = Field(min_length=1, max_length=100)
    approved_by: str | None = None
    role_id_after: str | None = None
    