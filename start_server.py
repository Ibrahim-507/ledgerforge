"""LedgerForge one-command starter.  Put this file in the project folder (next to the app folder) and run:

        python start_server.py

It checks the app and routes, sets a local secret key, initializes missing demo data without overwriting populated databases,
finds a free port, starts the server and opens the browser. Every step prints [ OK ] or [FAIL] with next steps.
Press Ctrl+C in this window to stop the server."""
import ast
import importlib
import importlib.util
import os
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLACEHOLDERS = ("change-me", "changeme", "replace-me", "your-secret")

REQUIRED = [
    "app/main.py", "app/deps.py", "app/security.py", "app/auth_store.py", "app/permissions.py", "app/books_db.py",
    "app/tax_config.py", "app/routers/auth.py", "app/routers/web.py", "app/routers/books_api.py",
    "app/routers/reports_api.py", "app/routers/tax_api.py", "app/routers/jobs_api.py", "app/versioning.py", "app/jobs.py", "app/worker.py", "scripts/init_db.py",
    "scripts/load_data.py", "scripts/load_books_payroll.py", "scripts/load_books_expenses.py", "scripts/load_official_books.py",
    "data/employees.csv", "data/departments.csv", "data/roles.csv", "data/payroll_runs.csv", "data/payroll_items.csv",
    "data/journal_entries.csv", "data/journal_lines.csv", "data/chart_of_accounts.csv", "data/expenses.csv",
    "data/attendance.csv", "data/leave_types.csv", "data/holidays.csv", "data/leave_requests.csv", "data/leave_balances.csv",
]
PACKAGES = {"fastapi": "fastapi", "uvicorn": "uvicorn", "jwt": "PyJWT", "pandas": "pandas", "reportlab": "reportlab", "dotenv": "python-dotenv"}


def say(ok, msg):
    print(("[ OK ] " if ok else "[FAIL] ") + msg, flush=True)


def stop(msg):
    print("\n" + msg + "\n")
    sys.exit(1)


# ---------------------------------------------------------------- pure helpers (tested) ----
ROUTERS = [("auth", "_auth_router"), ("books_api", "_books_api"), ("reports_api", "_reports_api"), ("tax_api", "_tax_api"),
           ("jobs_api", "_jobs_api"), ("web", "_web_router")]


def patch_main_text(src: str):
    """Make app/main.py: require login on every route, put routes under /api/v1, include all new routers.
    Safe to run again. Returns (new_source, message); new_source is None when nothing could or needed to change."""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return None, f"app/main.py has a syntax error already: {e}"
    need_dep = "_authorize" not in src
    need_version = "_prefix_all" not in src
    missing = [(m, a) for m, a in ROUTERS if f"{a}.router" not in src]
    if not (need_dep or need_version or missing):
        return None, "already secured"
    node = next((n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(x, ast.Name) and x.id == "app" for x in n.targets)
                 and isinstance(n.value, ast.Call) and getattr(n.value.func, "id", getattr(n.value.func, "attr", "")) == "FastAPI"), None)
    if node is None:
        return None, "could not find a line like  app = FastAPI(...)  in app/main.py"
    if need_dep and re.search(r"FastAPI\([^)]*dependencies\s*=", src, re.S):
        return None, "your FastAPI(...) already has dependencies=; edit app/main.py by hand"
    lines = src.splitlines(keepends=True)
    if need_version:                                         # right AFTER app = FastAPI(...) and BEFORE any include_router
        lines.insert(node.end_lineno, "from app.versioning import prefix_all as _prefix_all\n_prefix_all(app)\n")
    new = "".join(lines)
    imports = ""
    if need_dep:
        imports += "from fastapi import Depends as _Depends\nfrom app.deps import authorize as _authorize\n"
    imports += "".join(f"from app.routers import {m} as {a}\n" for m, a in missing)
    m0 = re.search(r"^[ \t]*app\s*=\s*FastAPI\(", new, re.M)
    new = new[:m0.start()] + imports + ("\n" if imports else "") + new[m0.start():]
    if need_dep:
        new = re.sub(r"^([ \t]*app\s*=\s*FastAPI\()", r"\1dependencies=[_Depends(_authorize)], ", new, count=1, flags=re.M)
    if missing:
        block = "# --- login, permissions, /api/v1 and the new routers (added by start_server.py) ---\n" + \
                "".join(f"app.include_router({a}.router)\n" for _, a in missing)
        guard = re.search(r"^if\s+__name__\s*==", new, re.M)
        new = (new[:guard.start()] + block + "\n" + new[guard.start():]) if guard else (new.rstrip("\n") + "\n\n" + block)
    try:
        ast.parse(new)
    except SyntaxError as e:
        return None, f"the edited file would not be valid Python ({e})"
    return new, "patched"


def free_port(start=8000, tries=30):
    for p in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:     # nothing is listening there
                return p
    return None


def ensure_secret(root: Path) -> str:
    """The key comes from the environment. For local use it is remembered in .secret_key (never committed to git)."""
    key = os.environ.get("LEDGERFORGE_SECRET_KEY", "")
    invalid = len(key) < 32 or any(p in key.lower() for p in PLACEHOLDERS)
    if invalid:
        f = root / ".secret_key"
        key = f.read_text().strip() if f.exists() else ""
        if len(key) < 32 or any(p in key.lower() for p in PLACEHOLDERS):
            key = secrets.token_urlsafe(48)
            f.write_text(key)
        os.environ["LEDGERFORGE_SECRET_KEY"] = key
    gi = root / ".gitignore"
    text = gi.read_text() if gi.exists() else ""
    add = [x for x in (".secret_key", "*.sqlite") if x not in text.split()]
    if add:
        gi.write_text(text.rstrip("\n") + ("\n" if text else "") + "\n".join(add) + "\n")
    return key


def wait_then_open(url, port, seconds=60):
    """Open the browser only when the server really answers (a browser opened too early shows 'refused to connect')."""
    end = time.time() + seconds
    while time.time() < end:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                print(f"\n[ OK ] The server is answering. Opening {url} in your browser.", flush=True)
                webbrowser.open(url)
                return
        time.sleep(0.5)
    print(f"\n[FAIL] Nothing answered on port {port} after {seconds} seconds. Read the lines above for the reason.", flush=True)


# ---------------------------------------------------------------- the steps ----
def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    print("LedgerForge starter\n" + "=" * 60)

    # 1. files
    missing = [f for f in REQUIRED if not (ROOT / f).exists()]
    if missing:
        for f in missing:
            say(False, f"missing file: {f}")
        stop("Copy the missing files from the zip files I gave you (ledgerforge_tasks_13_15.zip and ledgerforge_login_page.zip)\n"
             "into this project, keeping the same folders. Then run  python start_server.py  again.")
    say(True, "all project files are present")

    # 2. packages
    absent = [pip for mod, pip in PACKAGES.items() if importlib.util.find_spec(mod) is None]
    if absent:
        say(False, "missing packages: " + ", ".join(absent))
        stop("Install them, then run this again:\n    pip install " + " ".join(absent))
    say(True, "required packages are installed")

    # 2.5 load local environment settings (never ship the .env file).
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    except Exception:
        pass

    # 3. secret key
    ensure_secret(ROOT)
    say(True, "secret key is set (kept in .secret_key, which is not committed to git)")

    # 4-5. import the app and verify routes through HTTP requests. FastAPI may
    # represent included routers as lazy/internal router objects; inspecting
    # app.routes for a .path attribute is not a reliable route check. Do not
    # rewrite app/main.py automatically (that was the source of earlier failures).
    try:
        # Use the project's local CSV seed folder unless the operator has explicitly
        # configured another one. These must be set before app.config is imported.
        os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
        os.environ.setdefault("LEDGERFORGE_DATA", str(ROOT / "data"))
        from fastapi.testclient import TestClient
        m = importlib.import_module("app.main")
        client = TestClient(m.app)
        root = client.get("/")
        login_probe = client.post("/api/v1/auth/login", json={})
        protected_probe = client.get("/api/v1/employees")
        root_ok = root.status_code == 200 and "LedgerForge" in root.text
        login_ok = login_probe.status_code == 422  # endpoint found; empty body fails validation
        protected_ok = protected_probe.status_code == 401
        deps = getattr(m.app.router, "dependencies", [])
        secure_ok = any(getattr(getattr(d, "dependency", None), "__name__", "") == "authorize" for d in deps)
    except Exception:
        say(False, "the app could not start. The reason (last lines):")
        print("".join(traceback.format_exc().splitlines(keepends=True)[-12:]))
        stop("Copy the lines above into the chat and I will tell you the fix.")
    say(root_ok, "login/dashboard page / responds")
    say(login_ok, "login route /api/v1/auth/login responds (validation probe)")
    say(protected_ok, "API routes are protected by login")
    say(secure_ok, "global authorize dependency is enabled")
    if not (root_ok and login_ok and protected_ok and secure_ok):
        stop("App routes/security did not pass the HTTP checks. Copy the check output into the chat.")

    # 6. Seed the two data stores used by LedgerForge: the books/API SQLite
    # database and the SQLAlchemy employee/salary database. Each loader is additive
    # or runs only when its target tables are empty; it never resets existing data.
    from app.deps import db_path
    dbp = Path(db_path())
    n_users = 0
    if dbp.exists():
        try:
            with sqlite3.connect(str(dbp)) as probe:
                n_users = probe.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        except sqlite3.Error:
            n_users = 0
    if n_users == 0:
        print("       creating demo users and book tables ...", flush=True)
        r = subprocess.run([sys.executable, "-m", "scripts.init_db"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            say(False, "creating the demo users failed:")
            print("\n".join((r.stdout + r.stderr).strip().splitlines()[-12:]))
            stop("Copy the lines above into the chat.")

    con = sqlite3.connect(str(dbp))
    try:
        n_entries = con.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
        n_runs = con.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0]
        n_payroll_items = con.execute("SELECT COUNT(*) FROM payroll_items").fetchone()[0]
        n_expenses = con.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        n_users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    except sqlite3.Error as e:
        con.close()
        stop(f"Books database check failed: {e}")
    con.close()
    if n_entries == 0:
        print("       importing official ledger and invoice CSVs ...", flush=True)
        r = subprocess.run([sys.executable, "-m", "scripts.load_official_books"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            say(False, "official books import failed:")
            print("\n".join((r.stdout + r.stderr).strip().splitlines()[-12:]))
            stop("Copy the lines above into the chat.")
    if n_runs == 0 or n_payroll_items == 0:
        print("       linking historical payroll runs and payslip items ...", flush=True)
        r = subprocess.run([sys.executable, "-m", "scripts.load_books_payroll"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            say(False, "payroll register import failed:")
            print("\n".join((r.stdout + r.stderr).strip().splitlines()[-12:]))
            stop("Copy the lines above into the chat.")

    if n_expenses == 0:
        print("       linking vendor bills and their ledger/payment entries ...", flush=True)
        r = subprocess.run([sys.executable, "-m", "scripts.load_books_expenses"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            say(False, "expense register import failed:")
            print("\n".join((r.stdout + r.stderr).strip().splitlines()[-12:]))
            stop("Copy the lines above into the chat.")

    # Employee/department/salary API uses a separate SQLAlchemy database.
    try:
        from app.database import Base, engine, SessionLocal
        from app.models import Employee
        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            n_employees = session.query(Employee).count()
        if n_employees == 0 and (ROOT / "data" / "employees.csv").exists():
            print("       loading employee, department, role and salary master data ...", flush=True)
            seed_env = os.environ.copy()
            seed_env["DATA_DIR"] = str(ROOT / "data")
            r = subprocess.run([sys.executable, "-m", "scripts.load_data"], cwd=ROOT, env=seed_env, capture_output=True, text=True)
            if r.returncode != 0:
                say(False, "employee master-data import failed:")
                print("\n".join((r.stdout + r.stderr).strip().splitlines()[-12:]))
                stop("Copy the lines above into the chat.")
            with SessionLocal() as session:
                n_employees = session.query(Employee).count()
        say(n_employees > 0, f"employee master data ready ({n_employees} employees)")
    except Exception:
        say(False, "employee database initialization failed:")
        print("\n".join(traceback.format_exc().splitlines()[-12:]))
        stop("Copy the lines above into the chat.")

    say(n_users > 0, f"demo users are ready ({n_users} users)")
    con = sqlite3.connect(str(dbp))
    sample = {}
    for role in ("ADMIN", "HR", "EMPLOYEE"):
        row = con.execute("SELECT username FROM users WHERE role=? AND is_active='Y' ORDER BY user_id LIMIT 1", (role,)).fetchone()
        if row:
            sample[role] = row[0]
    con.close()

    # 7. port
    port = free_port(8000)
    if port is None:
        stop("No free port between 8000 and 8030. Close other programs and try again.")
    if port != 8000:
        say(True, f"port 8000 is busy (an old server is probably still running), so I will use port {port}")
    else:
        say(True, "port 8000 is free")

    url = f"http://127.0.0.1:{port}/"
    pw = os.environ.get("DEMO_PASSWORD", "Demo@12345")
    print("\n" + "=" * 60)
    print(f"  LOGIN PAGE :  {url}")
    print(f"  API DOCS   :  {url}docs   (all API routes are under /api/v1)")
    print(f"  PASSWORD   :  {pw}   (the same for every demo user)")
    for role, name in sample.items():
        print(f"  {role:<9}  :  {name}")
    print("=" * 60)
    print("  Leave this window open. Press Ctrl+C here to stop the server.\n")

    threading.Thread(target=wait_then_open, args=(url, port), daemon=True).start()
    import uvicorn
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")
    except SystemExit:
        pass
    print("\n[STOPPED] The server is not running any more.")
    print("If you did not press Ctrl+C, copy the lines printed ABOVE this one into the chat.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer stopped.")
