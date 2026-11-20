from datetime import date

from pydantic import BaseModel, ConfigDict, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class EmployeeOut(BaseModel):
    """Used in lists. No date of birth or other sensitive fields."""
    model_config = ConfigDict(from_attributes=True)

    employee_id: str
    full_name: str
    work_email: str
    department_id: str
    role_id: str
    manager_id: str | None = None
    employment_status: str | None = None
    hire_date: date
    exit_date: date | None = None


class EmployeeDetail(EmployeeOut):
    first_name: str
    last_name: str
    gender: str | None = None
    employment_type: str | None = None
    work_location: str | None = None
    work_mode: str | None = None


class EmployeePage(BaseModel):
    items: list[EmployeeOut]
    total: int
    page: int
    page_size: int


class EmployeeCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=20, examples=["EMP-0500"])
    first_name: str = Field(min_length=1, max_length=100, examples=["Priya"])
    last_name: str = Field(min_length=1, max_length=100, examples=["Sharma"])
    work_email: str = Field(pattern=EMAIL_PATTERN, examples=["priya.sharma@znova.example"])
    hire_date: date = Field(examples=["2025-01-15"])
    department_id: str = Field(examples=["DEPT-ENG"])
    role_id: str = Field(examples=["ROLE-SE"])
    manager_id: str | None = Field(default=None, examples=["EMP-0011"])
    gender: str | None = Field(default=None, examples=["F"])
    employment_status: str | None = Field(default="Active", examples=["Active"])
    employment_type: str | None = Field(default=None, examples=["Full-time"])
    work_location: str | None = Field(default=None, examples=["Bangalore"])
    work_mode: str | None = Field(default=None, examples=["Hybrid"])


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100, examples=["Priya"])
    last_name: str | None = Field(default=None, min_length=1, max_length=100, examples=["Sharma"])
    work_email: str | None = Field(default=None, pattern=EMAIL_PATTERN, examples=["priya.sharma@znova.example"])
    department_id: str | None = Field(default=None, examples=["DEPT-ENG"])
    role_id: str | None = Field(default=None, examples=["ROLE-SE"])
    manager_id: str | None = Field(default=None, examples=["EMP-0011"])
    employment_status: str | None = Field(default=None, examples=["Active"])
    employment_type: str | None = Field(default=None, examples=["Full-time"])
    work_location: str | None = Field(default=None, examples=["Bangalore"])
    work_mode: str | None = Field(default=None, examples=["Hybrid"])