"""The report and tax-rule endpoints through a real FastAPI app with the real `authorize` dependency."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth_store import add_user
from app.books_db import connect
from app.deps import authorize
from app.ledger import create_journal_entry, load_chart
from app.routers import auth as auth_router
from app.routers import reports_api, tax_api
from app.tax_config import seed_rules
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
PW = "Passw0rd!x"


def L(code, dr=0, cr=0):
    return {"account_code": code, "debit": dr, "credit": cr}


@pytest.fixture
def api(tmp_path, monkeypatch):
    db = str(tmp_path / "t.sqlite")
    monkeypatch.setenv("LEDGERFORGE_SECRET_KEY", "api-test-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("LEDGERFORGE_DB", db)
    c = connect(db)
    load_chart(c, DATA / "chart_of_accounts.csv")
    seed_rules(c, str(DATA))
    create_journal_entry(c, "2025-04-01", "capital", [L(1001, 1000000), L(3001, cr=1000000)])
    create_journal_entry(c, "2025-04-10", "invoice", [L(1100, 118000), L(4003, cr=100000), L(2200, cr=18000)])
    create_journal_entry(c, "2025-04-20", "rent bill", [L(5101, 30000), L(1200, 5400), L(2001, cr=35400)])
    add_user(c, "U-A", "admin@x", PW, "ADMIN", "EMP-A")
    add_user(c, "U-H", "hr@x", PW, "HR", "EMP-H")
    c.close()
    app = FastAPI(dependencies=[Depends(authorize)])
    app.include_router(auth_router.router)
    app.include_router(reports_api.router)
    app.include_router(tax_api.router)
    return TestClient(app)


def headers(api, username):
    r = api.post("/auth/login", json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_trial_balance_endpoint(api):
    r = api.get("/reports/trial-balance", params={"from": "2025-04-01", "to": "2025-04-30"}, headers=headers(api, "admin@x"))
    assert r.status_code == 200
    body = r.json()
    assert body["balanced"] is True and body["difference"] == "0.00" and body["total_debit"] == body["total_credit"]


def test_profit_and_loss_endpoint(api):
    r = api.get("/reports/profit-and-loss", params={"from": "2025-04-01", "to": "2025-04-30"}, headers=headers(api, "admin@x"))
    assert r.status_code == 200
    body = r.json()
    assert (body["total_income"], body["total_expenses"], body["net_profit"]) == ("100000.00", "30000.00", "70000.00")


def test_balance_sheet_endpoint(api):
    r = api.get("/reports/balance-sheet", params={"as_of": "2025-04-30"}, headers=headers(api, "admin@x"))
    assert r.status_code == 200
    body = r.json()
    assert body["balanced"] is True and body["total_assets"] == "1123400.00" and body["current_profit"] == "70000.00"


def test_financial_statements_are_admin_only(api):
    for path in ("/reports/trial-balance", "/reports/profit-and-loss", "/reports/balance-sheet"):
        assert api.get(path).status_code == 401
        assert api.get(path, headers=headers(api, "hr@x")).status_code == 403


def test_only_admin_can_change_a_slab_and_the_change_is_logged(api):
    body = {"rate_percent": 25, "reason": "test"}
    assert api.put("/tax/slabs/TS-005", json=body).status_code == 401
    assert api.put("/tax/slabs/TS-005", json=body, headers=headers(api, "hr@x")).status_code == 403
    r = api.put("/tax/slabs/TS-005", json=body, headers=headers(api, "admin@x"))
    assert r.status_code == 200 and r.json()["rate_percent"] == "25"
    slabs = api.get("/tax/slabs", params={"financial_year": "FY2025-26"}, headers=headers(api, "hr@x")).json()
    assert next(s for s in slabs if s["slab_id"] == "TS-005")["rate_percent"] == "25"
    log = api.get("/tax/rule-changes", headers=headers(api, "admin@x")).json()
    assert len(log) == 1 and log[0]["changed_by"] == "U-A" and log[0]["old_value"] == "20" and log[0]["new_value"] == "25"
    assert api.put("/tax/slabs/TS-005", json={"rate_percent": 150, "reason": "typo"}, headers=headers(api, "admin@x")).status_code == 400
    assert api.get("/tax/rule-changes", headers=headers(api, "hr@x")).status_code == 403


def test_statutory_report_for_a_missing_run_is_404(api):
    assert api.get("/reports/statutory/pf/PR-1999-01", headers=headers(api, "hr@x")).status_code == 404
