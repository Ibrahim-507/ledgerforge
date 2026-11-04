"""The same rules through a real FastAPI app: no token is 401, wrong role is 403, and a deactivated user is refused.
Uses a small test app with the SAME `authorize` dependency the real app uses."""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.auth_store import add_user, set_active
from app.books_db import connect
from app.deps import authorize
from app.permissions import PUBLIC, RULES
from app.routers import auth as auth_router
from app.security import create_token

PW = "Passw0rd!x"


@pytest.fixture
def api(tmp_path, monkeypatch):
    db = str(tmp_path / "t.sqlite")
    monkeypatch.setenv("LEDGERFORGE_SECRET_KEY", "api-test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("LEDGERFORGE_DB", db)
    c = connect(db)
    add_user(c, "U-A", "admin@x", PW, "ADMIN", "EMP-A")
    add_user(c, "U-H", "hr@x", PW, "HR", "EMP-H")
    add_user(c, "U-1", "e1@x", PW, "EMPLOYEE", "EMP-1")
    add_user(c, "U-2", "e2@x", PW, "EMPLOYEE", "EMP-2")
    c.close()

    app = FastAPI(dependencies=[Depends(authorize)])
    app.include_router(auth_router.router)

    @app.get("/employees")
    def list_employees():
        return {"ok": True}

    @app.delete("/employees/{employee_id}")
    def delete_employee(employee_id: str):
        return {"deleted": employee_id}

    @app.get("/payslips/{employee_id}/{run_id}")
    def payslip(employee_id: str, run_id: str):
        return {"employee_id": employee_id}

    @app.post("/payroll-runs/{run_id}/approve")
    def approve(run_id: str):
        return {"approved": run_id}

    @app.get("/bills")
    def bills():
        return []

    @app.get("/not-in-the-table")
    def forgotten():
        return {"oops": True}

    client = TestClient(app)
    client.db = db
    return client


def token(api, username):
    r = api.post("/auth/login", json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


ROUTES = [("GET", "/employees"), ("DELETE", "/employees/EMP-2"), ("GET", "/payslips/EMP-2/PR-2025-04"),
          ("POST", "/payroll-runs/PR-2025-04/approve"), ("GET", "/bills")]


def test_no_token_is_401_on_five_routes(api):
    for method, path in ROUTES:
        r = api.request(method, path)
        assert r.status_code == 401, (method, path, r.status_code)
        assert r.headers.get("www-authenticate") == "Bearer"


def test_wrong_role_is_403(api):
    emp, hr = token(api, "e1@x"), token(api, "hr@x")
    assert api.get("/employees", headers=emp).status_code == 403
    assert api.get("/bills", headers=emp).status_code == 403
    assert api.delete("/employees/EMP-2", headers=hr).status_code == 403
    assert api.post("/payroll-runs/PR-2025-04/approve", headers=hr).status_code == 403
    assert api.get("/employees", headers=hr).status_code == 200
    assert api.post("/payroll-runs/PR-2025-04/approve", headers=token(api, "admin@x")).status_code == 200


def test_employee_cannot_read_another_payslip_by_changing_the_id(api):
    emp = token(api, "e1@x")
    assert api.get("/payslips/EMP-1/PR-2025-04", headers=emp).status_code == 200
    assert api.get("/payslips/EMP-2/PR-2025-04", headers=emp).status_code == 403


def test_bad_tokens_are_401(api):
    assert api.get("/employees", headers={"Authorization": "Bearer not.a.token"}).status_code == 401
    expired = create_token({"user_id": "U-H"}, now=datetime.now(timezone.utc) - timedelta(minutes=31))
    assert api.get("/employees", headers={"Authorization": "Bearer " + expired}).status_code == 401


def test_deactivated_user_with_a_valid_token_is_refused(api):
    hr = token(api, "hr@x")
    assert api.get("/employees", headers=hr).status_code == 200
    c = connect(api.db)
    set_active(c, "U-H", False)
    c.close()
    r = api.get("/employees", headers=hr)
    assert r.status_code == 401 and "deactivated" in r.json()["detail"]


def test_login_failures_and_public_login(api):
    assert api.post("/auth/login", json={"username": "e1@x", "password": "nope-nope"}).status_code == 401
    assert api.post("/auth/login", json={"username": "ghost@x", "password": PW}).status_code == 401
    assert api.get("/auth/me", headers=token(api, "e1@x")).json()["role"] == "EMPLOYEE"


def test_route_without_a_rule_is_denied_by_default(api):
    assert api.get("/not-in-the-table", headers=token(api, "admin@x")).status_code == 403


def test_every_route_of_the_real_app_has_a_permission_rule():
    """Fails and lists the routes you still need to add to app/permissions.py RULES."""
    from app.main import app
    missing = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                if (method, route.path) not in RULES and (method, route.path) not in PUBLIC:
                    missing.append(f"{method} {route.path}")
    assert not missing, "Routes with no permission rule: " + ", ".join(sorted(missing))
