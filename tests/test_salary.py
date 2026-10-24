from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app
from app.models import Department, Employee, Role, SalaryRevision, SalaryStructure
from app.routers.employees import get_session
from app.salary_service import get_structure, monthly_earnings, revise_salary


@pytest.fixture()
def db_engine():
    """Own in-memory database. Employee E1 earns 20,000 a month from 1 Jan 2024."""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all([
            Department(department_id="D01", department_name="HR", cost_center="CC1"),
            Role(role_id="R01", department_id="D01", role_title="Manager"),
        ])
        s.commit()
        s.add(Employee(
            employee_id="E1", first_name="Asha", last_name="Rao", full_name="Asha Rao",
            work_email="asha@zn.com", hire_date=date(2024, 1, 1), department_id="D01", role_id="R01",
        ))
        s.commit()
        s.add(SalaryRevision(
            revision_id="SR-00001", employee_id="E1", effective_from=date(2024, 1, 1),
            revision_reason="Joining", new_annual_fixed=Decimal("240000"),
        ))
        s.commit()
        parts = [("BASIC", "Basic Salary", "8000"), ("HRA", "House Rent Allowance", "4000"),
                 ("SPECIAL", "Special Allowance", "8000")]
        for i, (cid, name, amount) in enumerate(parts, 1):
            s.add(SalaryStructure(
                structure_id=f"SS-{i:06d}", employee_id="E1", component_id=cid, component_name=name,
                component_type="EARNING", monthly_amount=Decimal(amount),
                effective_from=date(2024, 1, 1), revision_id="SR-00001",
            ))
        s.commit()
    return eng


@pytest.fixture()
def client(db_engine):
    def override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def total_on(db_engine, on_date):
    with Session(db_engine) as s:
        return monthly_earnings(get_structure(s, "E1", on_date))


def raise_on_1_jan(db_engine):
    with Session(db_engine) as s:
        revise_salary(s, "E1", date(2025, 1, 1), Decimal("300000"), "Annual raise")


def test_first_day_of_structure(db_engine):
    assert total_on(db_engine, date(2024, 1, 1)) == Decimal("20000")


def test_day_before_structure_has_no_pay(db_engine):
    assert total_on(db_engine, date(2023, 12, 31)) == Decimal("0")


def test_raise_31_dec_is_old_pay_and_1_jan_is_new_pay(db_engine):
    raise_on_1_jan(db_engine)
    assert total_on(db_engine, date(2024, 12, 31)) == Decimal("20000")
    assert total_on(db_engine, date(2025, 1, 1)) == Decimal("25000")


def test_no_overlap_and_no_gap_after_raise(db_engine):
    raise_on_1_jan(db_engine)
    with Session(db_engine) as s:
        assert len(get_structure(s, "E1", date(2024, 12, 31))) == 3
        assert len(get_structure(s, "E1", date(2025, 1, 1))) == 3
        old_rows = [r for r in get_structure(s, "E1", date(2024, 12, 31))]
        assert all(r.effective_to == date(2024, 12, 31) for r in old_rows)


def test_new_annual_matches_requested_amount(db_engine):
    raise_on_1_jan(db_engine)
    assert total_on(db_engine, date(2025, 1, 1)) * 12 == Decimal("300000")


def test_money_is_decimal_not_float(db_engine):
    with Session(db_engine) as s:
        row = get_structure(s, "E1", date(2024, 6, 1))[0]
        assert isinstance(row.monthly_amount, Decimal)


def test_old_rows_are_kept_not_overwritten(db_engine):
    raise_on_1_jan(db_engine)
    with Session(db_engine) as s:
        assert s.query(SalaryStructure).filter_by(employee_id="E1").count() == 6


def test_salary_endpoint_on_a_date(client):
    body = client.get("/employees/E1/salary?on=2024-06-15").json()
    assert Decimal(body["monthly_earnings"]) == Decimal("20000")
    assert len(body["components"]) == 3


def test_revision_history_lists_each_change_with_reason(client):
    r = client.post("/employees/E1/salary/revisions", json={
        "effective_from": "2025-01-01", "new_annual_fixed": "300000", "revision_reason": "Annual raise"})
    assert r.status_code == 201
    history = client.get("/employees/E1/salary/revisions").json()
    assert [h["revision_reason"] for h in history] == ["Joining", "Annual raise"]


def test_cannot_revise_on_or_before_current_start(client):
    payload = {"new_annual_fixed": "300000", "revision_reason": "Bad date"}
    assert client.post("/employees/E1/salary/revisions", json={**payload, "effective_from": "2024-01-01"}).status_code == 422
    assert client.post("/employees/E1/salary/revisions", json={**payload, "effective_from": "2023-06-01"}).status_code == 422


def test_zero_salary_is_422(client):
    r = client.post("/employees/E1/salary/revisions", json={
        "effective_from": "2025-01-01", "new_annual_fixed": "0", "revision_reason": "Bad"})
    assert r.status_code == 422


def test_unknown_employee_is_404(client):
    assert client.get("/employees/NOPE/salary").status_code == 404
    assert client.get("/employees/NOPE/salary/revisions").status_code == 404