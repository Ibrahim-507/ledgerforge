"""Vendor bill CSV import should link to existing books and be repeatable."""
import sqlite3
import subprocess
import sys
from pathlib import Path
import scripts.load_books_expenses as loader

ROOT = Path(__file__).resolve().parent.parent


def test_expense_import_is_idempotent_and_preserves_statuses(monkeypatch, tmp_path):
    db_path = tmp_path / "books.sqlite"
    env = dict(__import__('os').environ)
    env["LEDGERFORGE_DB"] = str(db_path)
    env["LEDGERFORGE_DATA"] = str(ROOT / "data")
    monkeypatch.setenv("LEDGERFORGE_DB", str(db_path))
    monkeypatch.setenv("LEDGERFORGE_DATA", str(ROOT / "data"))
    monkeypatch.setattr(loader, "DATA", ROOT / "data")

    init = subprocess.run([sys.executable, "-m", "scripts.init_db"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert init.returncode == 0, init.stdout + init.stderr
    official = subprocess.run([sys.executable, "-m", "scripts.load_official_books"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert official.returncode == 0, official.stdout + official.stderr

    loader.main()
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 501
    assert conn.execute("SELECT COUNT(*) FROM expenses WHERE status='PAID'").fetchone()[0] == 478
    assert conn.execute("SELECT COUNT(*) FROM expenses WHERE status='APPROVED'").fetchone()[0] == 23
    assert conn.execute("SELECT COUNT(*) FROM expenses WHERE ledger_entry_id IS NOT NULL").fetchone()[0] == 501
    conn.close()

    loader.main()
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 501
    conn.close()
