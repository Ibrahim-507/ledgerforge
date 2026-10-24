from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import engine
from ..employee_schemas import (
    EmployeeCreate,
    EmployeeDetail,
    EmployeeOut,
    EmployeePage,
    EmployeeUpdate,
)
from ..models import Department, Employee, Role

router = APIRouter(prefix="/employees", tags=["employees"])


def get_session():
    with Session(engine) as session:
        yield session


def get_or_404(db: Session, employee_id: str) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def check_links(db: Session, department_id=None, role_id=None, manager_id=None):
    """Bad foreign keys are bad input (422), not server errors."""
    if department_id is not None and db.get(Department, department_id) is None:
        raise HTTPException(status_code=422, detail=f"Unknown department_id {department_id}")
    if role_id is not None and db.get(Role, role_id) is None:
        raise HTTPException(status_code=422, detail=f"Unknown role_id {role_id}")
    if manager_id is not None and db.get(Employee, manager_id) is None:
        raise HTTPException(status_code=422, detail=f"Unknown manager_id {manager_id}")


@router.get("", response_model=EmployeePage)
def list_employees(
    q: str | None = Query(None, description="Search name, email or id"),
    department_id: str | None = None,
    active_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    stmt = select(Employee)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Employee.full_name.ilike(like),
            Employee.work_email.ilike(like),
            Employee.employee_id.ilike(like),
        ))
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if active_only:
        stmt = stmt.where(Employee.exit_date.is_(None))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(
        stmt.order_by(Employee.employee_id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return EmployeePage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{employee_id}", response_model=EmployeeDetail)
def get_employee(employee_id: str, db: Session = Depends(get_session)):
    return get_or_404(db, employee_id)


@router.post("", response_model=EmployeeDetail, status_code=201)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_session)):
    if db.get(Employee, payload.employee_id) is not None:
        raise HTTPException(status_code=409, detail="employee_id already exists")
    if db.scalar(select(Employee).where(Employee.work_email == payload.work_email)):
        raise HTTPException(status_code=409, detail="work_email already exists")
    check_links(db, payload.department_id, payload.role_id, payload.manager_id)

    data = payload.model_dump()
    employee = Employee(**data, full_name=f"{payload.first_name} {payload.last_name}")
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.patch("/{employee_id}", response_model=EmployeeDetail)
def update_employee(employee_id: str, payload: EmployeeUpdate, db: Session = Depends(get_session)):
    employee = get_or_404(db, employee_id)
    changes = payload.model_dump(exclude_unset=True)
    check_links(db, changes.get("department_id"), changes.get("role_id"), changes.get("manager_id"))
    if changes.get("manager_id") == employee_id:
        raise HTTPException(status_code=422, detail="An employee cannot be their own manager")

    for field, value in changes.items():
        setattr(employee, field, value)
    if "first_name" in changes or "last_name" in changes:
        employee.full_name = f"{employee.first_name} {employee.last_name}"
    db.commit()
    db.refresh(employee)
    return employee


@router.delete("/{employee_id}", response_model=EmployeeOut)
def remove_employee(employee_id: str, db: Session = Depends(get_session)):
    """Soft delete: the row stays, because payroll needs history."""
    employee = get_or_404(db, employee_id)
    if employee.exit_date is None:
        employee.exit_date = date.today()
        db.commit()
        db.refresh(employee)
    return employee


@router.get("/{employee_id}/team", response_model=list[EmployeeOut])
def get_team(employee_id: str, include_left: bool = False, db: Session = Depends(get_session)):
    get_or_404(db, employee_id)
    stmt = select(Employee).where(Employee.manager_id == employee_id)
    if not include_left:
        stmt = stmt.where(Employee.exit_date.is_(None))
    return db.scalars(stmt.order_by(Employee.employee_id)).all()