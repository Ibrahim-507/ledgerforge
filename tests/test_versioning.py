from app.permissions import RULES, decide, is_public, role_table_markdown
from app.versioning import API_PREFIX, normalize, prefix_all


class FakeApp:
    def __init__(self):
        self.calls = []

    def include_router(self, router, **kwargs):
        self.calls.append((router, kwargs))


class Router:
    pass


def test_every_router_gets_the_version_prefix_except_the_login_page():
    app = prefix_all(FakeApp())
    normal, page, already = Router(), Router(), Router()
    page._unversioned = True
    app.include_router(normal)
    app.include_router(page)
    app.include_router(normal, prefix="/extra")
    app.include_router(already, prefix="/api/v1/x")
    assert [k for _, k in app.calls] == [{"prefix": "/api/v1"}, {}, {"prefix": "/api/v1/extra"}, {"prefix": "/api/v1/x"}]


def test_normalize_removes_only_the_version_prefix():
    assert API_PREFIX == "/api/v1"
    assert normalize("/api/v1/employees/{employee_id}") == "/employees/{employee_id}"
    assert normalize("/api/v1") == "/" and normalize("/health") == "/health" and normalize("/api/v10/x") == "/api/v10/x"


def test_the_permission_table_works_with_and_without_the_prefix():
    emp = {"role": "EMPLOYEE", "employee_id": "EMP-1"}
    hr = {"role": "HR", "employee_id": "EMP-H"}
    admin = {"role": "ADMIN", "employee_id": "EMP-A"}
    for path in ("/employees", "/api/v1/employees"):
        assert decide("GET", path, {}, emp)[0] == 403 and decide("GET", path, {}, hr) is None
        assert decide("GET", path, {}, None) == (401, "Not authenticated")
    slip = "/api/v1/payslips/{employee_id}/{run_id}"
    assert decide("GET", slip, {"employee_id": "EMP-1"}, emp) is None and decide("GET", slip, {"employee_id": "EMP-2"}, emp)[0] == 403
    assert is_public("POST", "/api/v1/auth/login") and is_public("POST", "/auth/login") and not is_public("GET", "/api/v1/employees")
    assert decide("POST", "/api/v1/auth/login", {}, None) is None
    assert "| GET | /employees |" in role_table_markdown([("GET", "/api/v1/employees")])      # the role table shows the short path


def test_job_routes_hr_runs_payroll_only_admin_approves():
    emp = {"role": "EMPLOYEE", "employee_id": "EMP-1"}
    hr = {"role": "HR", "employee_id": "EMP-H"}
    admin = {"role": "ADMIN", "employee_id": "EMP-A"}
    for path, who, ok in [("/api/v1/jobs/payroll-process", hr, True), ("/api/v1/jobs/payroll-process", emp, False),
                          ("/api/v1/jobs/payroll-approve", hr, False), ("/api/v1/jobs/payroll-approve", admin, True),
                          ("/api/v1/jobs", hr, True), ("/api/v1/jobs/{job_id}", emp, False)]:
        method = "POST" if "payroll-" in path else "GET"
        assert (decide(method, path, {}, who) is None) == ok, (method, path, who["role"])
    assert ("POST", "/jobs/payroll-approve") in RULES
