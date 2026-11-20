"""Smoke tests for the connected LedgerForge web workspace and explicit API wiring."""
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_dashboard_serves_navigation_and_api_connected_pages():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    for label in ("Dashboard", "Employees", "Departments", "Payroll", "Payslips", "Accounting", "Reports", "Vendor bills", "Tax & rules", "Background jobs"):
        assert label in html
    for endpoint in ("/employees", "/payroll-runs", "/reports/balance-sheet", "/payslips/", "/bills", "/tax/parameters", "/jobs"):
        assert endpoint in html


def test_api_login_is_versioned_and_validation_reaches_endpoint():
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 422  # endpoint exists; required credentials are missing

    old_path = client.post("/auth/login", json={})
    assert old_path.status_code == 404  # unversioned API path is not mounted


def test_protected_api_rejects_anonymous_request():
    response = client.get("/api/v1/employees")
    assert response.status_code == 401
