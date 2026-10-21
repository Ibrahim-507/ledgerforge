from pydantic import BaseModel, ConfigDict
class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    department_id: str
    department_name: str
    cost_center: str
    description: str | None = None
