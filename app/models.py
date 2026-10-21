"""PATTERN TO COPY: one SQLAlchemy model per table. Department is done for you.
Your job (LF-02): add Role, Employee, EmployeeAssignment ... following the same style."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
class Department(Base):
    __tablename__ = "departments"
    department_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    department_name: Mapped[str] = mapped_column(String(100))
    cost_center: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
