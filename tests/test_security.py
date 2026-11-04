"""Security rules tested without a web server: hashing, tokens, login, deactivation and the role table."""
import os
from datetime import datetime, timedelta, timezone
import pytest
from app.auth_store import add_user, authenticate, get_user, login, set_active, user_from_token
from app.books_db import connect
from app.permissions import PUBLIC, RULES, decide
from app.security import AuthError, ConfigError, create_token, decode_token, get_secret, hash_password, verify_password

os.environ["LEDGERFORGE_SECRET_KEY"] = "unit-test-secret-key-at-least-32-characters!"
PW = "Passw0rd!x"


def users():
    c = connect()
    add_user(c, "U-A", "admin@x", PW, "ADMIN", "EMP-A")
    add_user(c, "U-H", "hr@x", PW, "HR", "EMP-H")
    add_user(c, "U-1", "e1@x", PW, "EMPLOYEE", "EMP-1")
    add_user(c, "U-2", "e2@x", PW, "EMPLOYEE", "EMP-2")
    add_user(c, "U-X", "gone@x", PW, "EMPLOYEE", "EMP-X", is_active="N")
    return c


# ---------------- passwords are hashed ----------------
def test_passwords_are_hashed_salted_and_verifiable():
    h1, h2 = hash_password(PW), hash_password(PW)
    assert PW not in h1 and h1.startswith("scrypt$")
    assert h1 != h2                                           # random salt: same password, different hash
    assert verify_password(PW, h1) and not verify_password("wrong-password", h1) and not verify_password(PW, "garbage")
    with pytest.raises(ValueError):
        hash_password("short")


def test_database_never_holds_the_password():
    c = users()
    stored = [r["password_hash"] for r in c.execute("SELECT password_hash FROM users")]
    assert len(stored) == 5 and all(PW not in s and s.startswith("scrypt$") for s in stored)


# ---------------- tokens ----------------
def test_token_lives_30_minutes_and_roundtrips():
    claims = decode_token(create_token({"user_id": "U-1"}))
    assert claims["sub"] == "U-1" and claims["exp"] - claims["iat"] == 30 * 60
    assert "role" not in claims and "password" not in claims   # the token only identifies the user


def test_expired_tampered_and_foreign_tokens_are_rejected():
    old = create_token({"user_id": "U-1"}, now=datetime.now(timezone.utc) - timedelta(minutes=31))
    with pytest.raises(AuthError, match="expired"):
        decode_token(old)
    good = create_token({"user_id": "U-1"})
    with pytest.raises(AuthError, match="Invalid"):
        decode_token(good[:-3] + ("AAA" if not good.endswith("AAA") else "BBB"))        # tampered signature
    with pytest.raises(AuthError, match="Invalid"):
        decode_token(create_token({"user_id": "U-1"}, secret="another-secret-key-that-is-long-enough-123"))
    with pytest.raises(AuthError):
        decode_token("not.a.token")


def test_secret_key_must_come_from_the_environment():
    saved = os.environ.pop("LEDGERFORGE_SECRET_KEY")
    try:
        with pytest.raises(ConfigError, match="LEDGERFORGE_SECRET_KEY"):
            get_secret()
        os.environ["LEDGERFORGE_SECRET_KEY"] = "short"
        with pytest.raises(ConfigError):
            get_secret()
    finally:
        os.environ["LEDGERFORGE_SECRET_KEY"] = saved


# ---------------- login ----------------
def test_login_success_and_identical_failures():
    c = users()
    ok = login(c, "e1@x", PW)
    assert ok["token_type"] == "bearer" and ok["expires_in"] == 1800 and ok["role"] == "EMPLOYEE"
    msgs = set()
    for u, p in [("e1@x", "wrong-password"), ("nobody@x", PW), ("gone@x", PW)]:    # bad password, unknown user, deactivated
        with pytest.raises(AuthError) as e:
            authenticate(c, u, p)
        msgs.add(str(e.value))
    assert msgs == {"Invalid username or password"}            # never reveals which part was wrong


# ---------------- deactivated user holding a valid token ----------------
def test_deactivated_user_is_refused_on_the_next_request_even_with_a_valid_token():
    c = users()
    token = login(c, "e1@x", PW)["access_token"]
    assert user_from_token(c, token)["user_id"] == "U-1"
    set_active(c, "U-1", False)                                # HR deactivates the account
    with pytest.raises(AuthError, match="deactivated"):
        user_from_token(c, token)                              # the token itself is still unexpired
    set_active(c, "U-1", True)
    assert user_from_token(c, token)["role"] == "EMPLOYEE"


def test_role_comes_from_the_database_not_the_token():
    c = users()
    token = login(c, "e1@x", PW)["access_token"]
    c.execute("UPDATE users SET role='ADMIN' WHERE user_id='U-1'")
    assert user_from_token(c, token)["role"] == "ADMIN"        # promotions and demotions apply immediately
    c.execute("UPDATE users SET role='EMPLOYEE' WHERE user_id='U-1'")
    assert user_from_token(c, token)["role"] == "EMPLOYEE"


# ---------------- 401 and 403 on 5+ routes ----------------
CASES = [("GET", "/employees", {}), ("POST", "/employees", {}), ("DELETE", "/employees/{employee_id}", {"employee_id": "EMP-2"}),
         ("GET", "/payslips/{employee_id}/{run_id}", {"employee_id": "EMP-2", "run_id": "PR-2025-04"}),
         ("POST", "/payroll-runs/{run_id}/approve", {"run_id": "PR-2025-04"}), ("GET", "/bills", {}),
         ("POST", "/bills/{expense_id}/approve", {"expense_id": "EXP-00001"})]


def test_no_token_is_401_on_every_protected_route():
    for method, path, params in CASES:
        assert decide(method, path, params, None) == (401, "Not authenticated"), (method, path)


def user(c, uid):
    return get_user(c, uid)


def test_wrong_role_is_403():
    c = users()
    emp, hr, admin = user(c, "U-1"), user(c, "U-H"), user(c, "U-A")
    assert decide("GET", "/employees", {}, emp)[0] == 403                                    # employee cannot list everyone
    assert decide("POST", "/employees", {}, emp)[0] == 403
    assert decide("DELETE", "/employees/{employee_id}", {"employee_id": "EMP-2"}, hr)[0] == 403   # only Admin deletes
    assert decide("POST", "/payroll-runs/{run_id}/approve", {"run_id": "R"}, hr)[0] == 403         # HR runs payroll, cannot approve
    assert decide("POST", "/bills/{expense_id}/approve", {"expense_id": "E"}, hr)[0] == 403
    assert decide("POST", "/employees/{employee_id}/salary/revisions", {"employee_id": "EMP-1"}, emp)[0] == 403
    assert decide("GET", "/employees", {}, hr) is None and decide("GET", "/employees", {}, admin) is None
    assert decide("POST", "/payroll-runs/{run_id}/approve", {"run_id": "R"}, admin) is None
    assert decide("POST", "/payroll-runs/{run_id}/process", {"run_id": "R"}, hr) is None


def test_employee_cannot_read_another_payslip_by_changing_the_id():
    c = users()
    emp1 = user(c, "U-1")
    route = "/payslips/{employee_id}/{run_id}"
    assert decide("GET", route, {"employee_id": "EMP-1", "run_id": "PR-2025-04"}, emp1) is None      # own payslip
    assert decide("GET", route, {"employee_id": "EMP-2", "run_id": "PR-2025-04"}, emp1)[0] == 403    # someone else's
    assert decide("GET", route + "/pdf", {"employee_id": "EMP-2", "run_id": "PR-2025-04"}, emp1)[0] == 403
    assert decide("GET", "/employees/{employee_id}", {"employee_id": "EMP-2"}, emp1)[0] == 403
    assert decide("GET", "/employees/{employee_id}/salary", {"employee_id": "EMP-2"}, emp1)[0] == 403
    assert decide("GET", route, {"employee_id": "EMP-2", "run_id": "PR-2025-04"}, user(c, "U-H")) is None   # HR may


def test_a_route_with_no_rule_is_denied_by_default():
    c = users()
    assert decide("GET", "/brand-new-route", {}, user(c, "U-A"))[0] == 403         # even Admin
    assert decide("GET", "/brand-new-route", {}, None)[0] == 401                   # anonymous learns nothing


def test_only_login_is_public_and_every_rule_names_real_roles():
    assert PUBLIC == {("POST", "/auth/login")}
    assert decide("POST", "/auth/login", {}, None) is None
    for key, rule in RULES.items():
        assert rule.roles and rule.roles <= {"ADMIN", "HR", "EMPLOYEE"}, key
        assert key not in PUBLIC
    for method, path in RULES:                                   # money-moving actions are Admin-only
        if path.endswith(("/approve", "/pay", "/reverse")):
            assert RULES[(method, path)].roles == {"ADMIN"}, path


def test_only_admin_can_change_tax_rules_and_read_the_financial_statements():
    c = users()
    hr, emp, admin = user(c, "U-H"), user(c, "U-1"), user(c, "U-A")
    for method, path in RULES:
        if method == "PUT" and path.startswith("/tax"):
            assert RULES[(method, path)].roles == {"ADMIN"}, path
            assert decide(method, path, {"slab_id": "TS-005", "name": "x"}, hr)[0] == 403
            assert decide(method, path, {"slab_id": "TS-005", "name": "x"}, emp)[0] == 403
            assert decide(method, path, {"slab_id": "TS-005", "name": "x"}, admin) is None
    for path in ("/reports/trial-balance", "/reports/profit-and-loss", "/reports/balance-sheet"):
        assert decide("GET", path, {}, hr)[0] == 403 and decide("GET", path, {}, admin) is None
    assert decide("GET", "/reports/statutory-summary", {}, hr) is None and decide("GET", "/reports/statutory-summary", {}, emp)[0] == 403
