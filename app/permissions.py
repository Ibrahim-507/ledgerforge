"""Who may call which route. ONE table, used by the server, the tests and the report.
Deny by default: a route with no rule is refused (403), so a forgotten route can never be left open."""
from dataclasses import dataclass

ALL = frozenset({"ADMIN", "HR", "EMPLOYEE"})
HR_UP = frozenset({"ADMIN", "HR"})
ADMIN = frozenset({"ADMIN"})


@dataclass(frozen=True)
class Rule:
    roles: frozenset                 # roles allowed on this route
    self_param: str | None = None    # an EMPLOYEE may also call it when this path parameter is their own employee id
    note: str = ""


PUBLIC = {("POST", "/auth/login")}

RULES: dict[tuple[str, str], Rule] = {
    ("GET", "/auth/me"): Rule(ALL, note="your own profile"),
    # departments
    ("GET", "/departments"): Rule(ALL),
    ("GET", "/departments/{department_id}"): Rule(ALL),
    # employees
    ("GET", "/employees"): Rule(HR_UP, note="whole company list"),
    ("POST", "/employees"): Rule(HR_UP),
    ("GET", "/employees/{employee_id}"): Rule(HR_UP, "employee_id", "an employee sees only their own record"),
    ("PATCH", "/employees/{employee_id}"): Rule(HR_UP),
    ("DELETE", "/employees/{employee_id}"): Rule(ADMIN, note="only Admin removes people"),
    ("GET", "/employees/{employee_id}/team"): Rule(HR_UP, "employee_id"),
    # salary
    ("GET", "/employees/{employee_id}/salary"): Rule(HR_UP, "employee_id"),
    ("GET", "/employees/{employee_id}/salary/revisions"): Rule(HR_UP, "employee_id"),
    ("POST", "/employees/{employee_id}/salary/revisions"): Rule(HR_UP, note="only HR and Admin change pay"),
    # payslips
    ("GET", "/payslips/{employee_id}/{run_id}"): Rule(HR_UP, "employee_id", "an employee reads only their own payslip"),
    ("GET", "/payslips/{employee_id}/{run_id}/pdf"): Rule(HR_UP, "employee_id"),
    # payroll runs: running and approving are different permissions
    ("GET", "/payroll-runs"): Rule(HR_UP),
    ("GET", "/payroll-runs/{run_id}"): Rule(HR_UP),
    ("POST", "/payroll-runs"): Rule(HR_UP, note="create a month"),
    ("POST", "/payroll-runs/{run_id}/process"): Rule(HR_UP, note="calculate"),
    ("POST", "/payroll-runs/{run_id}/approve"): Rule(ADMIN, note="moves real money: separate permission, and not the person who ran it"),
    ("POST", "/payroll-runs/{run_id}/pay"): Rule(ADMIN),
    ("POST", "/payroll-runs/{run_id}/reverse"): Rule(ADMIN),
    # vendor bills
    ("GET", "/bills"): Rule(HR_UP),
    ("POST", "/bills"): Rule(HR_UP, note="submit a bill"),
    ("POST", "/bills/{expense_id}/approve"): Rule(ADMIN, note="not the person who submitted it"),
    ("POST", "/bills/{expense_id}/reject"): Rule(ADMIN),
    ("POST", "/bills/{expense_id}/pay"): Rule(ADMIN),
    ("GET", "/reports/spend"): Rule(HR_UP),
    # tax rules as data (Task 14): anyone in HR/Admin may read, ONLY Admin may change
    ("GET", "/tax/slabs"): Rule(HR_UP),
    ("PUT", "/tax/slabs/{slab_id}"): Rule(ADMIN, note="changes tax for the next payroll run"),
    ("GET", "/tax/parameters"): Rule(HR_UP),
    ("PUT", "/tax/parameters/{name}"): Rule(ADMIN),
    ("GET", "/tax/statutory-rates"): Rule(HR_UP),
    ("PUT", "/tax/statutory-rates/{name}"): Rule(ADMIN),
    ("GET", "/tax/rule-changes"): Rule(ADMIN, note="audit log of rule changes"),
    ("GET", "/tax/explain"): Rule(HR_UP),
    # statutory reports (Task 14)
    ("GET", "/reports/statutory-summary"): Rule(HR_UP),
    ("GET", "/reports/statutory/{kind}/{run_id}"): Rule(HR_UP),
    # financial statements (Task 15): the board's reports, Admin only
    ("GET", "/reports/trial-balance"): Rule(ADMIN),
    ("GET", "/reports/profit-and-loss"): Rule(ADMIN),
    ("GET", "/reports/balance-sheet"): Rule(ADMIN),
}


def is_public(method: str, route_path: str) -> bool:
    return (method.upper(), route_path) in PUBLIC


def decide(method: str, route_path: str, path_params: dict, user: dict | None):
    """None = allowed, otherwise (http_status, message). `route_path` is the route TEMPLATE, e.g. /employees/{employee_id}."""
    method = method.upper()
    if (method, route_path) in PUBLIC:
        return None
    if user is None:
        return 401, "Not authenticated"
    rule = RULES.get((method, route_path))
    if rule is None:
        return 403, f"No permission rule for {method} {route_path}: access denied by default"
    if user["role"] in rule.roles:
        return None
    if rule.self_param and user["role"] == "EMPLOYEE" and user.get("employee_id") \
            and path_params.get(rule.self_param) == user["employee_id"]:
        return None
    return 403, "You do not have permission for this action"


def role_table_markdown(routes) -> str:
    """routes = [(method, path), ...] -> markdown table of who may use each (flags routes with no rule)."""
    out = ["| Method | Route | Admin | HR | Employee | Note |", "|---|---|---|---|---|---|"]
    for method, path in sorted(routes, key=lambda x: (x[1], x[0])):
        if (method, path) in PUBLIC:
            out.append(f"| {method} | {path} | public | public | public | login |")
            continue
        r = RULES.get((method, path))
        if r is None:
            out.append(f"| {method} | {path} | **NO RULE** | **NO RULE** | **NO RULE** | add a rule: denied by default |")
            continue
        emp = "own only" if r.self_param and "EMPLOYEE" not in r.roles else ("yes" if "EMPLOYEE" in r.roles else "no")
        out.append(f"| {method} | {path} | {'yes' if 'ADMIN' in r.roles else 'no'} | {'yes' if 'HR' in r.roles else 'no'} | {emp} | {r.note} |")
    return "\n".join(out)
