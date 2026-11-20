"""Backup the books SQLite file (safe while running) and, if DATABASE_URL is Postgres and
pg_dump exists, the main database too.   python -m scripts.backup [path-to-sqlite]"""
import os, shutil, sqlite3, subprocess, sys, time

src = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LEDGERFORGE_BOOKS_PATH", "ledgerforge.sqlite")
os.makedirs("backups", exist_ok=True)
stamp = time.strftime("%Y%m%d_%H%M%S")
dst = f"backups/books_{stamp}.sqlite"
a = sqlite3.connect(src); b = sqlite3.connect(dst)
a.backup(b); b.close(); a.close()
print("books backup:", dst)
url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgres") and shutil.which("pg_dump"):
    out = f"backups/main_{stamp}.sql"
    subprocess.run(["pg_dump", "--no-owner", "-f", out, url.replace("+psycopg2", "")], check=True)
    print("postgres backup:", out)
elif url.startswith("postgres"):
    print("pg_dump not installed here. In Docker use: docker compose exec db pg_dump -U <user> <db> > backups/main.sql")
