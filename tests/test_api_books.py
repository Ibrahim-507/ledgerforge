"""Vendor bills and payroll runs through the real FastAPI routes, with the real login and role checks."""
from pathlib import Path
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth_store import add_user
from app.books_db import connect
from app.deps import authorize
from app.expenses import add_vendor
from app.ledger import load_chart
from app.routers import auth as auth_router
from app.routers import books_api

DATA = str(Path(__file__).resolve().parent.parent / "data")
PW = "Passw0rd!x"
BILL = {"vendor_id": "V-001", "bill_date": "2025-04-01", "category_account": 5101, "amount_excl_gst": "100000", "gst_rate_percent": "18",
        "department_id": "D09", "description": "Rent", "bill_reference": "RENT-APR"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    db = str(tmp_path / "t.sqlite")
    monkeypatch.setenv("LEDGERFORGE_SECRET_KEY", "api-test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("LEDGERFORGE_DB", db)
    monkeypatch.setenv("LEDGERFORGE_DATA", DATA)
    c = connect(db)
    load_chart(c, Path(DATA) / "chart_of_accounts.csv")
    add_vendor(c, "V-001", "Skyline Realty", 5101, 30)
    add_user(c, "U-A", "admin@x", PW, "ADMIN", "EMP-A")
    add_user(c, "U-H", "hr@x", PW, "HR", "EMP-H")
    add_user(c, "U-1", "e1@x", PW, "EMPLOYEE", "EMP-1")
    c.close()
    app = FastAPI(dependencies=[Depends(authorize)])
    app.include_router(auth_router.router)
    app.include_router(books_api.router)
    return TestClient(app)


def headers(api, username):
    r = api.post("/auth/login", json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_a_bill_goes_submitted_approved_paid_with_the_right_people(api):
    hr, admin = headers(api, "hr@x"), headers(api, "admin@x")
    bill = api.post("/bills", json=BILL, headers=hr)
    assert bill.status_code == 200 and bill.json()["status"] == "SUBMITTED" and bill.json()["submitted_by"] == "U-H"
    eid = bill.json()["expense_id"]
    assert api.post(f"/bills/{eid}/approve", headers=hr).status_code == 403                  # HR may not approve at all
    approved = api.post(f"/bills/{eid}/approve", headers=admin)
    assert approved.status_code == 200 and approved.json()["status"] == "APPROVED" and approved.json()["approved_by"] == "U-A"
    paid = api.post(f"/bills/{eid}/pay", json={"paid_date": "2025-04-10"}, headers=admin)
    assert paid.status_code == 200 and paid.json()["status"] == "PAID"
    assert [b["expense_id"] for b in api.get("/bills", params={"status": "PAID"}, headers=hr).json()] == [eid]
    spend = api.get("/reports/spend", headers=hr).json()
    assert spend[0]["vendor_id"] == "V-001" and spend[0]["total"] == "118000.00"


def test_the_person_who_submitted_a_bill_cannot_approve_it(api):
    admin = headers(api, "admin@x")
    eid = api.post("/bills", json=BILL, headers=admin).json()["expense_id"]                 # Admin submits it ...
    r = api.post(f"/bills/{eid}/approve", headers=admin)                                     # ... and may not approve it too
    assert r.status_code == 403 and "cannot also approve" in r.json()["detail"]


def test_duplicate_and_unknown_bills(api):
    hr, admin = headers(api, "hr@x"), headers(api, "admin@x")
    assert api.post("/bills", json=BILL, headers=hr).status_code == 200
    dup = api.post("/bills", json={**BILL, "bill_date": "2025-04-03", "bill_reference": "RENT-APR-2"}, headers=hr)
    assert dup.status_code == 409 and dup.json()["detail"]["matches"]
    assert api.post("/bills", json={**BILL, "bill_date": "2025-04-03", "allow_duplicate": True}, headers=hr).status_code == 200
    assert api.post("/bills/EXP-99999/approve", headers=admin).status_code == 404
    assert api.post("/bills", json={**BILL, "vendor_id": "V-404"}, headers=hr).status_code == 404
    assert api.get("/bills", headers=headers(api, "e1@x")).status_code == 403


def test_payroll_run_flow_and_roles(api):
    hr, admin = headers(api, "hr@x"), headers(api, "admin@x")
    run = api.post("/payroll-runs", json={"period_start": "2025-04-01"}, headers=hr).json()
    rid = run["run_id"]
    assert rid == "PR-2025-04" and run["status"] == "DRAFT" and run["run_by"] == "U-H"
    assert api.post("/payroll-runs", json={"period_start": "2025-04-15"}, headers=hr).json()["run_id"] == rid        # same month, same run
    processed = api.post(f"/payroll-runs/{rid}/process", headers=hr).json()
    assert processed["status"] == "PROCESSED" and processed["employees_paid"] == 386
    assert api.post(f"/payroll-runs/{rid}/approve", headers=hr).status_code == 403
    approved = api.post(f"/payroll-runs/{rid}/approve", headers=admin).json()
    assert approved["status"] == "APPROVED" and approved["journal_entry_id"] and approved["approved_by"] == "U-A"
    assert api.post(f"/payroll-runs/{rid}/approve", headers=admin).json()["journal_entry_id"] == approved["journal_entry_id"]   # double click
    rev = api.post(f"/payroll-runs/{rid}/reverse", json={"reverse_date": "2025-05-02", "reason": "test"}, headers=admin)
    assert rev.status_code == 200 and rev.json()["status"] == "REVERSED"
    assert [r["run_id"] for r in api.get("/payroll-runs", headers=hr).json()] == [rid]
    assert api.get("/payroll-runs/PR-1999-01", headers=hr).status_code == 404


def test_the_person_who_ran_payroll_cannot_approve_it(api):
    admin = headers(api, "admin@x")
    rid = api.post("/payroll-runs", json={"period_start": "2025-04-01"}, headers=admin).json()["run_id"]
    api.post(f"/payroll-runs/{rid}/process", headers=admin)
    r = api.post(f"/payroll-runs/{rid}/approve", headers=admin)
    assert r.status_code == 403 and "cannot also approve" in r.json()["detail"]
