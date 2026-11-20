"""Container start-up:  check the settings, seed the data ONCE, then start the API.
A marker file in the data volume remembers that seeding is done, so restarting the container does not seed twice."""
import os
import subprocess
import sys
from pathlib import Path

PLACEHOLDERS = ("change-me", "changeme", "replace-me", "your-secret")


def fail(msg):
    print("[FAIL] " + msg, flush=True)
    sys.exit(1)


def run(cmd, required=True):
    print("[ .. ] " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        (fail if required else print)(f"{' '.join(cmd)} exited with code {r.returncode}")
    return r.returncode == 0


key = os.environ.get("LEDGERFORGE_SECRET_KEY", "")
if len(key) < 32 or any(p in key.lower() for p in PLACEHOLDERS):
    fail("LEDGERFORGE_SECRET_KEY is missing, too short or still the example value. Put a real random value in .env "
         "(python -c \"import secrets; print(secrets.token_urlsafe(48))\").")

seed = Path(os.environ.get("LEDGERFORGE_DATA", "/app/seed"))
if not (seed.exists() and any(seed.glob("*.csv"))):
    fail(f"The seed data folder {seed} is empty or missing. On your computer run  python -m scripts.make_seed , then  git add seed , "
         "commit, and build the image again.")

state = Path(os.environ.get("LEDGERFORGE_STATE_DIR", "/var/lib/ledgerforge"))
state.mkdir(parents=True, exist_ok=True)
marker = state / ".seeded-v1"

if not marker.exists():
    print("[ .. ] first start: seeding (about 30 seconds) ...", flush=True)
    if Path("alembic.ini").exists() and os.environ.get("RUN_MIGRATIONS", "1") != "0":
        run(["alembic", "upgrade", "head"], required=False)
    run([sys.executable, "-m", "scripts.init_db"])                                # users, chart of accounts, vendors, tax rules
    if os.environ.get("LOAD_OFFICIAL_BOOKS", "1") != "0":
        run([sys.executable, "-m", "scripts.load_official_books"])                # the official ledger, invoices and clients
    if Path("app/load_data.py").exists() and os.environ.get("LOAD_EMPLOYEE_DATA", "1") != "0":
        run([sys.executable, "-m", "app.load_data"], required=False)              # your Task 1 to 6 data loader
    marker.write_text("seeded\n")
    print("[ OK ] seeding finished", flush=True)
else:
    print("[ OK ] already seeded, skipping", flush=True)

print("[ OK ] starting the API on port 8000", flush=True)
os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
