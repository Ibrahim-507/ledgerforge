"""The CSV loader seeds employee, salary, attendance and leave data together."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_load_data_imports_attendance_and_leave_tables(tmp_path):
    db = tmp_path / "people.sqlite"
    env = os.environ.copy()
    env["DATA_DIR"] = str(ROOT / "data")
    env["DATABASE_URL"] = f"sqlite:///{db}"
    schema = "from app.database import Base,engine; import app.models; Base.metadata.create_all(engine)"
    create = subprocess.run([sys.executable, "-c", schema], cwd=ROOT, env=env, capture_output=True, text=True)
    assert create.returncode == 0, create.stdout + create.stderr
    load = subprocess.run([sys.executable, "-m", "scripts.load_data"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert load.returncode == 0, load.stdout + load.stderr

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 745
    assert conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0] == 150155
    assert conn.execute("SELECT COUNT(*) FROM leave_requests").fetchone()[0] == 3441
    assert conn.execute("SELECT COUNT(*) FROM leave_balances").fetchone()[0] == 441
    conn.close()
