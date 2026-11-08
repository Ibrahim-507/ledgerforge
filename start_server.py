"""LedgerForge one-command starter.  Put this file in the project folder (next to the app folder) and run:

        python start_server.py

It checks your files, secures app/main.py, sets the secret key, creates the demo users, finds a free port, starts the
server and opens the login page in your browser. Every step prints [ OK ] or [FAIL] with what to do about it.
Press Ctrl+C in this window to stop the server."""
import ast
import importlib
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

REQUIRED = [
    "app/main.py", "app/deps.py", "app/security.py", "app/auth_store.py", "app/permissions.py", "app/books_db.py",
    "app/tax_config.py", "app/routers/auth.py", "app/routers/web.py", "app/routers/books_api.py",
    "app/routers/reports_api.py", "app/routers/tax_api.py", "scripts/init_db.py",
]
PACKAGES = {"fastapi": "fastapi", "uvicorn": "uvicorn", "jwt": "PyJWT", "pandas": "pandas", "reportlab": "reportlab"}


def say(ok, msg):
    print(("[ OK ] " if ok else "[FAIL] ") + msg, flush=True)


def stop(msg):
    print("\n" + msg + "\n")
    sys.exit(1)


# ---------------------------------------------------------------- pure helpers (tested) ----
def patch_main_text(src: str):
    """Return (new_source, message). new_source is None when nothing could or needed to change."""
    need_base = not ("_authorize" in src and "_auth_router.router" in src)
    need_web = "_web_router" not in src
    if not need_base and not need_web:
        return None, "already secured"
    m = re.search(r"^(?P<indent>[ \t]*)app\s*=\s*FastAPI\(", src, re.M)
    if not m:
        return None, "could not find a line like  app = FastAPI(...)  in app/main.py"
    if need_base and re.search(r"FastAPI\([^)]*dependencies\s*=", src, re.S):
        return None, "your FastAPI(...) already has dependencies=; edit app/main.py by hand"
    imports, includes = "", []
    if need_base:
        imports += ("from fastapi import Depends as _Depends\n"
                    "from app.deps import authorize as _authorize\n"
                    "from app.routers import auth as _auth_router, books_api as _books_api, reports_api as _reports_api, tax_api as _tax_api\n")
        includes += ["app.include_router(_auth_router.router)", "app.include_router(_books_api.router)",
                     "app.include_router(_reports_api.router)", "app.include_router(_tax_api.router)"]
    if need_web:
        imports += "from app.routers import web as _web_router\n"
        includes += ["app.include_router(_web_router.router)"]
    new = src[:m.start()] + imports + "\n" + src[m.start():]
    if need_base:
        new = re.sub(r"^([ \t]*app\s*=\s*FastAPI\()", r"\1dependencies=[_Depends(_authorize)], ", new, count=1, flags=re.M)
    block = "# --- login, permissions, login page and new routers (added by start_server.py) ---\n" + "\n".join(includes) + "\n"
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
    if len(key) < 32:
        f = root / ".secret_key"
        key = f.read_text().strip() if f.exists() else ""
        if len(key) < 32:
            key = secrets.token_urlsafe(48)
            f.write_text(key)
        os.environ["LEDGERFORGE_SECRET_KEY"] = key
    gi = root / ".gitignore"
    text = gi.read_text() if gi.exists() else ""
    add = [x for x in (".secret_key", "*.sqlite") if x not in text.split()]
    if add:
        gi.write_text(text.rstrip("\n") + ("\n" if text else "") + "\n".join(add) + "\n")
    return key


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

    # 3. secret key
    ensure_secret(ROOT)
    say(True, "secret key is set (kept in .secret_key, which is not committed to git)")

    # 4. main.py secured and has the login page
    mp = ROOT / "app" / "main.py"
    new, msg = patch_main_text(mp.read_text(encoding="utf-8"))
    if new is not None:
        shutil.copy(mp, ROOT / "app" / "main.py.bak")
        mp.write_text(new, encoding="utf-8")
        say(True, "app/main.py was updated to require login and to serve the login page (backup: app/main.py.bak)")
    elif msg == "already secured":
        say(True, "app/main.py already requires login")
    else:
        say(False, "app/main.py: " + msg)
        stop("Open app/main.py and copy it into the chat. I will edit it for you.")

    # 5. the app loads and has the right routes
    try:
        m = importlib.import_module("app.main")
    except Exception:
        say(False, "the app could not start. The reason (last lines):")
        print("".join(traceback.format_exc().splitlines(keepends=True)[-12:]))
        stop("Copy the lines above into the chat and I will tell you the fix.")
    paths = {getattr(r, "path", None) for r in m.app.routes}
    deps = [getattr(d.dependency, "__name__", "") for d in m.app.router.dependencies]
    say("/auth/login" in paths, "login route /auth/login exists")
    say("/" in paths, "login page route / exists")
    say("authorize" in deps, "every route requires a login (the security check is switched on)")
    if not ({"/auth/login", "/"} <= paths and "authorize" in deps):
        stop("app/main.py is not wired correctly. Copy it into the chat and I will edit it for you.")

    # 6. database and demo users
    from app.deps import db_path
    dbp = Path(db_path())
    n_users = 0
    if dbp.exists():
        try:
            n_users = sqlite3.connect(str(dbp)).execute("SELECT COUNT(*) FROM users").fetchone()[0]
        except sqlite3.Error:
            n_users = 0
    if n_users == 0:
        print("       creating demo users (about 25 seconds, please wait) ...", flush=True)
        r = subprocess.run([sys.executable, "-m", "scripts.init_db"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            say(False, "creating the demo users failed:")
            print("\n".join((r.stdout + r.stderr).strip().splitlines()[-12:]))
            stop("Copy the lines above into the chat.")
    con = sqlite3.connect(str(dbp))
    n_users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    say(n_users > 0, f"demo users are ready ({n_users} users)")
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
    print(f"  API DOCS   :  {url}docs")
    print(f"  PASSWORD   :  {pw}   (the same for every demo user)")
    for role, name in sample.items():
        print(f"  {role:<9}  :  {name}")
    print("=" * 60)
    print("  Leave this window open. Press Ctrl+C here to stop the server.\n")

    threading.Thread(target=lambda: (time.sleep(2.5), webbrowser.open(url)), daemon=True).start()
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer stopped.")
