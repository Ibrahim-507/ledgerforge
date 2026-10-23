"""Database models: one SQLAlchemy class per table."""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Department(Base):
    __tablename__ = "departments"

    department_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    department_name: Mapped[str] = mapped_column(String(100))
    cost_center: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(String(20), primary_key=True)
    department_id = Column(String(20), ForeignKey("departments.department_id"), nullable=False, index=True)
    role_title = Column(String(100), nullable=False)
    level = Column(String(50))
    grade = Column(String(20))
    band_min_annual = Column(Numeric(12, 2))
    band_mid_annual = Column(Numeric(12, 2))
    band_max_annual = Column(Numeric(12, 2))
    overtime_eligible = Column(Boolean)
    band_year = Column(Integer)


class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column(String(20), primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    full_name = Column(String(200), nullable=False)
    work_email = Column(String(200), nullable=False, unique=True)
    gender = Column(String(20))
    date_of_birth = Column(Date)  # sensitive: never show in list endpoints
    hire_date = Column(Date, nullable=False)
    exit_date = Column(Date)  # empty while the person still works here
    employment_status = Column(String(30))
    employment_type = Column(String(30))
    department_id = Column(String(20), ForeignKey("departments.department_id"), nullable=False, index=True)
    role_id = Column(String(20), ForeignKey("roles.role_id"), nullable=False, index=True)
    manager_id = Column(String(20), ForeignKey("employees.employee_id"), index=True)  # empty for the top person
    work_location = Column(String(100))
    work_mode = Column(String(30))
    highest_education = Column(String(100))
    prior_experience_years = Column(Numeric(5, 1))
    career_gap_months = Column(Integer)
    commute_distance_km = Column(Numeric(6, 1))
    pf_applicable = Column(Boolean)
    esi_applicable = Column(Boolean)
    notice_period_days = Column(Integer)
    resignation_date = Column(Date)
    exit_type = Column(String(50))
    exit_reason = Column(String(200))
    created_at = Column(Date)


class EmployeeAssignment(Base):
    __tablename__ = "employee_assignments"

    assignment_id = Column(String(20), primary_key=True)
    employee_id = Column(String(20), ForeignKey("employees.employee_id"), nullable=False, index=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)  # empty for the current assignment
    department_id = Column(String(20), ForeignKey("departments.department_id"), nullable=False, index=True)
    role_id = Column(String(20), ForeignKey("roles.role_id"), nullable=False)
    job_level = Column(String(50))
    manager_id = Column(String(20), ForeignKey("employees.employee_id"))
    change_reason = Column(String(200))

    __table_args__ = (Index("ix_assignment_dates", "effective_from", "effective_to"),)