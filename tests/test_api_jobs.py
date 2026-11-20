"""The job endpoints through a real FastAPI app: start, watch the progress, role checks."""
import os
import time
from pathlib import Path
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth_store import add_user
from app.books_db import connect
from app.deps import authorize
from app.ledger import load_chart
from app.routers import auth as auth_router
from app.routers import jobs_api

DATA = str(Path(__file__).resolve().parent.parent / "data")
PW = "Passw0rd!x"


@pytest.fixture
def api(tmp_path, monkeypatch):
    db = str(tmp_path / "t.sqlite")
    monkeypatch.setenv("LEDGERFORGE_SECRET_KEY", "api-test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("LEDGERFORGE_DB", db)
    monkeypatch.setenv("LEDGERFORGE_DATA", DATA)
    c = connect(db)
    load_chart(c, Path(DATA) / "chart_of_accounts.csv")
    add_user(c, "U-A", "admin@x", PW, "ADMIN", "EMP-A")
    add_user(c, "U-H", "hr@x", PW, "HR", "EMP-H")
    add_user(c, "U-1", "e1@x", PW, "EMPLOYEE", "EMP-1")
    c.close()
    app = FastAPI(dependencies=[Depends(authorize)])
    app.include_router(auth_router.router)
    app.include_router(jobs_api.router)
    return TestClient(app)


def headers(api, username):
    r = api.post("/auth/login", json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def wait_done(api, job_id, who):
    end = time.time() + 120
    while time.time() < end:
        job = api.get(f"/jobs/{job_id}", headers=who).json()
        if job["status"] in ("DONE", "FAILED"):
            return job
        time.sleep(0.5)
    raise AssertionError("job did not finish")


def test_hr_starts_a_job_and_watches_its_progress(api):
    hr = headers(api, "hr@x")
    r = api.post("/jobs/payroll-process", json={"first": "2025-04", "last": "2025-05"}, headers=hr)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] in ("QUEUED", "RUNNING", "DONE") and body["total"] == 2 and body["created_by"] == "U-H"
    done = wait_done(api, body["job_id"], hr)
    assert done["status"] == "DONE" and done["done"] == 2 and done["percent"] == 100.0 and done["result"]["processed"] == 2
    assert [j["job_id"] for j in api.get("/jobs", headers=hr).json()] == [body["job_id"]]


def test_only_admin_can_start_the_approval_job_and_hr_cannot_approve_own_months(api):
    hr, admin = headers(api, "hr@x"), headers(api, "admin@x")
    assert api.post("/jobs/payroll-approve", json={"first": "2025-04", "last": "2025-04"}, headers=hr).status_code == 403
    job = api.post("/jobs/payroll-process", json={"first": "2025-04", "last": "2025-04"}, headers=hr).json()
    wait_done(api, job["job_id"], hr)
    a = api.post("/jobs/payroll-approve", json={"first": "2025-04", "last": "2025-04", "pay": True}, headers=admin)
    assert a.status_code == 202
    final = wait_done(api, a.json()["job_id"], admin)
    assert final["status"] == "DONE" and final["result"]["approved"] == 1 and final["result"]["paid"] == 1


def test_job_endpoints_need_a_login_and_a_valid_request(api):
    assert api.post("/jobs/payroll-process", json={}).status_code == 401
    assert api.get("/jobs/JOB-000001").status_code == 401
    emp, hr = headers(api, "e1@x"), headers(api, "hr@x")
    assert api.post("/jobs/payroll-process", json={}, headers=emp).status_code == 403
    assert api.post("/jobs/payroll-process", json={"first": "April"}, headers=hr).status_code == 400
    assert api.get("/jobs/JOB-999999", headers=hr).status_code == 404
