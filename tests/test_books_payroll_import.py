"""The books payroll CSV loader must be repeatable and preserve register links."""
from pathlib import Path
import sqlite3

from app.books_db import connect
import scripts.load_books_payroll as loader

ROOT = Path(__file__).resolve().parent.parent


def test_historical_payroll_import_is_idempotent(monkeypatch, tmp_path):
    books_db = tmp_path / "books.sqlite"
    monkeypatch.setenv("LEDGERFORGE_DB", str(books_db))
    monkeypatch.setenv("LEDGERFORGE_DATA", str(ROOT / "data"))
    monkeypatch.setattr(loader, "DATA", ROOT / "data")

    loader.main()
    conn = connect(str(books_db))
    first_runs = conn.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0]
    first_items = conn.execute("SELECT COUNT(*) FROM payroll_items").fetchone()[0]
    linked = conn.execute("SELECT COUNT(*) FROM payroll_runs WHERE journal_entry_id IS NOT NULL").fetchone()[0]
    conn.close()

    assert first_runs == 18
    assert first_items == 7340
    assert linked == 18


    loader.main()
    conn = connect(str(books_db))
    assert conn.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0] == first_runs
    assert conn.execute("SELECT COUNT(*) FROM payroll_items").fetchone()[0] == first_items
    conn.close()
