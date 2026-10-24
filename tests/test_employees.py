from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app
from app.models import Department, Employee, Role
from app.routers.employees import get_session


def make_employee(emp_id, first, last, dept="D01", role="R01", manager=None, exit_date=None):
    return Employee(
        employee_id=emp_id, first_name=first, last_name=last,
        full_name=f"{first} {last}", work_email=f"{first.lower()}@zn.com",
        hire_date=date(2024, 1, 1), department_id=dept, role_id=role,
        manager_id=manager, exit_date=exit_date, employment_status="Active",
    )


@pytest.fixture()
def client():
    """Own in-memory database: tests never touch ledgerforge.db."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([
            Department(department_id="D01", department_name="HR", cost_center="CC1"),
            Department(department_id="D02", department_name="Tech", cost_center="CC2"),
            Role(role_id="R01", department_id="D01", role_title="Manager"),
            Role(role_id="R02", department_id="D02", role_title="Developer"),
        ])
        s.commit()
        s.add_all([
            make_employee("E001", "Asha", "Boss"),
            make_employee("E002", "Ravi", "Kumar", manager="E001"),
            make_employee("E003", "Priya", "Nair", dept="D02", role="R02", manager="E001"),
            make_employee("E004", "Leo", "Gone", manager="E001", exit_date=date(2025, 1, 31)),
        ])
        s.commit()

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


NEW = {
    "employee_id": "E100", "first_name": "Mohan", "last_name": "Das",
    "work_email": "mohan.das@zn.com", "hire_date": "2025-02-01",
    "department_id": "D01", "role_id": "R01", "manager_id": "E001",
}


def test_list_returns_page_without_date_of_birth(client):
    body = client.get("/employees").json()
    assert body["total"] == 4
    assert len(body["items"]) == 4
    assert "date_of_birth" not in body["items"][0]


def test_pagination(client):
    body = client.get("/employees?page=2&page_size=3").json()
    assert body["total"] == 4
    assert len(body["items"]) == 1


def test_search_by_name(client):
    items = client.get("/employees?q=priya").json()["items"]
    assert [e["employee_id"] for e in items] == ["E003"]


def test_filter_by_department(client):
    assert client.get("/employees?department_id=D02").json()["total"] == 1


def test_get_employee(client):
    r = client.get("/employees/E002")
    assert r.status_code == 200
    assert r.json()["full_name"] == "Ravi Kumar"


def test_unknown_employee_is_404(client):
    assert client.get("/employees/NOPE").status_code == 404


def test_create_employee(client):
    r = client.post("/employees", json=NEW)
    assert r.status_code == 201
    assert client.get("/employees/E100").json()["full_name"] == "Mohan Das"


def test_create_with_bad_email_is_422(client):
    assert client.post("/employees", json={**NEW, "work_email": "not-an-email"}).status_code == 422


def test_create_with_unknown_department_is_422(client):
    assert client.post("/employees", json={**NEW, "department_id": "D99"}).status_code == 422


def test_create_duplicate_id_is_409(client):
    assert client.post("/employees", json={**NEW, "employee_id": "E001"}).status_code == 409


def test_patch_employee(client):
    r = client.patch("/employees/E002", json={"first_name": "Ravindra"})
    assert r.status_code == 200
    assert r.json()["full_name"] == "Ravindra Kumar"


def test_patch_unknown_is_404(client):
    assert client.patch("/employees/NOPE", json={"first_name": "X"}).status_code == 404


def test_delete_sets_exit_date_and_keeps_row(client):
    r = client.delete("/employees/E002")
    assert r.status_code == 200
    assert r.json()["exit_date"] is not None
    assert client.get("/employees/E002").status_code == 200


def test_team_excludes_people_who_left_by_default(client):
    ids = [e["employee_id"] for e in client.get("/employees/E001/team").json()]
    assert ids == ["E002", "E003"]


def test_team_can_include_people_who_left(client):
    ids = [e["employee_id"] for e in client.get("/employees/E001/team?include_left=true").json()]
    assert ids == ["E002", "E003", "E004"]


def test_team_of_unknown_manager_is_404(client):
    assert client.get("/employees/NOPE/team").status_code == 404


def test_bad_page_size_is_422(client):
    assert client.get("/employees?page_size=0").status_code == 422