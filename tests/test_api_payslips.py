"""Payslip endpoints through the real login: the owner and HR may read a payslip, a stranger may not."""
from pathlib import Path
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api_payslips import build_router
from app.auth_store import add_user
from app.books_db import connect
from app.deps import authorize
from app.payroll_data import PayrollSource
from app.routers import auth as auth_router

DATA = str(Path(__file__).resolve().parent.parent / "data")
PW = "Passw0rd!x"
SOURCE = PayrollSource(DATA)


@pytest.fixture
def api(tmp_path, monkeypatch):
    db = str(tmp_path / "t.sqlite")
    monkeypatch.setenv("LEDGERFORGE_SECRET_KEY", "api-test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("LEDGERFORGE_DB", db)
    c = connect(db)
    add_user(c, "U-2", "owner@x", PW, "EMPLOYEE", "EMP-0002")
    add_user(c, "U-3", "stranger@x", PW, "EMPLOYEE", "EMP-0003")
    add_user(c, "U-H", "hr@x", PW, "HR", "EMP-H")
    c.close()
    app = FastAPI(dependencies=[Depends(authorize)])
    app.include_router(auth_router.router)
    app.include_router(build_router(SOURCE))
    return TestClient(app)


def headers(api, username):
    r = api.post("/auth/login", json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_owner_and_hr_read_the_payslip_and_the_figures_match_the_official_data(api):
    for who in ("owner@x", "hr@x"):
        r = api.get("/payslips/EMP-0002/PR-2025-04", headers=headers(api, who))
        assert r.status_code == 200
        body = r.json()
        assert body["net_pay"] == 158504.61 and body["gross_pay"] == 179130.4 and body["employee"]["employee_id"] == "EMP-0002"


def test_a_stranger_is_refused_and_no_token_is_401(api):
    assert api.get("/payslips/EMP-0002/PR-2025-04", headers=headers(api, "stranger@x")).status_code == 403
    assert api.get("/payslips/EMP-0002/PR-2025-04/pdf", headers=headers(api, "stranger@x")).status_code == 403
    assert api.get("/payslips/EMP-0002/PR-2025-04").status_code == 401


def test_pdf_download_and_unknown_payslip(api):
    r = api.get("/payslips/EMP-0002/PR-2025-04/pdf", headers=headers(api, "owner@x"))
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert api.get("/payslips/EMP-0002/PR-1999-01", headers=headers(api, "hr@x")).status_code == 404
