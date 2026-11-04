"""Create the books database and the demo users:  python -m scripts.init_db   (add --all-users to include inactive users)
Set the secret first (once per terminal):
    $env:LEDGERFORGE_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
Every demo user gets the same demo password (default Demo@12345, or set DEMO_PASSWORD). Only the salted hash is stored."""
import os
import sys
import pandas as pd
from app.auth_store import seed_users
from app.books_db import connect
from app.deps import db_path
from app.expenses import add_vendor
from app.ledger import load_chart
from app.tax_config import seed_rules

DATA = os.environ.get("LEDGERFORGE_DATA", "data")
demo = os.environ.get("DEMO_PASSWORD", "Demo@12345")
conn = connect(db_path())
if conn.execute("SELECT COUNT(*) n FROM chart_of_accounts").fetchone()["n"] == 0:
    load_chart(conn, f"{DATA}/chart_of_accounts.csv")
if conn.execute("SELECT COUNT(*) n FROM vendors").fetchone()["n"] == 0:
    for v in pd.read_csv(f"{DATA}/vendors.csv").itertuples():
        add_vendor(conn, v.vendor_id, v.vendor_name, v.primary_expense_account, int(v.payment_terms_days), v.city, v.gst_registration)
seed_rules(conn, DATA)
print("seeding users (about 50 ms each, please wait) ...")
n = seed_users(conn, f"{DATA}/users.csv", demo, active_only="--all-users" not in sys.argv)
print(f"added {n} users; database: {db_path()}\n")
print("Try logging in (password = the demo password):")
for role in ("ADMIN", "HR", "EMPLOYEE"):
    r = conn.execute("SELECT username, employee_id FROM users WHERE role=? AND is_active='Y' ORDER BY user_id LIMIT 2", (role,)).fetchall()
    for x in r:
        print(f"  {role:<9}{x['username']}   (employee {x['employee_id']})")
