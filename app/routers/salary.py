from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Employee, SalaryRevision
from ..salary_schemas import RevisionCreate, RevisionOut, SalaryOnDate
from ..salary_service import get_structure, monthly_earnings, revise_salary
from .employees import get_session

router = APIRouter(prefix="/employees", tags=["salary"])


def employee_or_404(db: Session, employee_id: str) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.get("/{employee_id}/salary", response_model=SalaryOnDate)
def salary_on_date(
    employee_id: str,
    on: date | None = Query(None, description="Date to check (default: today)"),
    db: Session = Depends(get_session),
):
    employee_or_404(db, employee_id)
    on_date = on or date.today()
    rows = get_structure(db, employee_id, on_date)
    monthly = monthly_earnings(rows)
    return SalaryOnDate(
        employee_id=employee_id,
        on_date=on_date,
        components=rows,
        monthly_earnings=monthly,
        annual_earnings=monthly * Decimal(12),
    )


@router.get("/{employee_id}/salary/revisions", response_model=list[RevisionOut])
def salary_history(employee_id: str, db: Session = Depends(get_session)):
    employee_or_404(db, employee_id)
    stmt = (
        select(SalaryRevision)
        .where(SalaryRevision.employee_id == employee_id)
        .order_by(SalaryRevision.effective_from, SalaryRevision.revision_id)
    )
    return list(db.scalars(stmt))


@router.post("/{employee_id}/salary/revisions", response_model=RevisionOut, status_code=201)
def create_revision(employee_id: str, payload: RevisionCreate, db: Session = Depends(get_session)):
    employee_or_404(db, employee_id)
    try:
        return revise_salary(
            db, employee_id, payload.effective_from, payload.new_annual_fixed,
            payload.revision_reason, payload.approved_by, payload.role_id_after,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))