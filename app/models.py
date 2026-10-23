"""Database models: one SQLAlchemy class per table.

Department uses the Mapped style from the starter project.
Role, Employee and EmployeeAssignment use Column style (same tables, same result).
"""
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