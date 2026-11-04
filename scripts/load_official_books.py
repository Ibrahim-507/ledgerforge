"""Put the official books and the tax rules into the API database, so the report endpoints show real numbers:
    python -m scripts.load_official_books"""
import os
from app.books_db import connect
from app.deps import db_path
from app.seed_official import import_official
from app.tax_config import seed_rules

DATA = os.environ.get("LEDGERFORGE_DATA", "data")
conn = connect(db_path())
if conn.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"]:
    print("The database already has journal entries; nothing loaded.")
else:
    import_official(conn, DATA)
    print("Loaded the official ledger, invoices and clients.")
print("Tax rules loaded:", seed_rules(conn, DATA))
print("Entries:", conn.execute("SELECT COUNT(*) n FROM journal_entries").fetchone()["n"], " database:", db_path())
