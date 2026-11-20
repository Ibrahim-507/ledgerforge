"""Smoke test: health, login, one payroll call. Uses only the Python standard library.
Run:  python smoke_test.py https://YOUR-LIVE-ADDRESS
Optional env: SMOKE_USER, SMOKE_PASSWORD, SMOKE_PAYROLL_PATH (e.g. /api/v1/payroll/...)"""
import json, os, sys, urllib.request, urllib.error, urllib.parse

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_URL", "http://127.0.0.1:8000")).rstrip("/")
USER = os.environ.get("SMOKE_USER", "admin")
PASSWORD = os.environ.get("SMOKE_PASSWORD", "Demo@12345")
results = []


def call(method, path, body=None, headers=None, form=False):
    data = None
    h = dict(headers or {})
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name + (" - " + detail if detail else ""))


print("Smoke test against", BASE)
code, text = call("GET", "/health")
check("health", code == 200, f"HTTP {code} {text[:120]}")

code, text = call("GET", "/openapi.json")
check("docs/openapi reachable", code == 200, f"HTTP {code}")
paths = json.loads(text).get("paths", {}) if code == 200 else {}

login_path = next((p for p in paths if "login" in p.lower() and "post" in paths[p]), None)
token = None
if login_path:
    content = paths[login_path]["post"].get("requestBody", {}).get("content", {})
    if "application/x-www-form-urlencoded" in content:
        code, text = call("POST", login_path, {"username": USER, "password": PASSWORD}, form=True)
    else:
        code, text = call("POST", login_path, {"username": USER, "email": USER, "password": PASSWORD})
    if code == 200:
        j = json.loads(text)
        token = j.get("access_token") or j.get("token")
    check("login " + login_path, bool(token), f"HTTP {code}")
else:
    check("login", False, "no login path found in openapi.json")

if token:
    auth = {"Authorization": "Bearer " + token}
    pp = os.environ.get("SMOKE_PAYROLL_PATH") or next(
        (p for p in paths if "payroll" in p.lower() and "{" not in p and "get" in paths[p]), None)
    if pp:
        code, text = call("GET", pp, headers=auth)
        check("payroll call " + pp, code == 200, f"HTTP {code} {text[:100]}")
    else:
        check("payroll call", False, "set SMOKE_PAYROLL_PATH")

print("RESULT:", "ALL PASSED" if all(results) else "SOME FAILED")
sys.exit(0 if all(results) else 1)
