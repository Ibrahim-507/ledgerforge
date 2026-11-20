"""Time a query, show its plan, optionally add an index, then time again.
python -m scripts.explain "SELECT ..." --add-index "CREATE INDEX IF NOT EXISTS idx_x ON t(col)"
python -m scripts.explain --tables      (lists tables and columns)"""
import argparse, os, sqlite3, time

p = argparse.ArgumentParser()
p.add_argument("sql", nargs="?")
p.add_argument("--db", default=os.environ.get("LEDGERFORGE_BOOKS_PATH", "ledgerforge.sqlite"))
p.add_argument("--add-index")
p.add_argument("--tables", action="store_true")
a = p.parse_args()
c = sqlite3.connect(a.db)

if a.tables:
    for (n,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        cols = [r[1] for r in c.execute(f'PRAGMA table_info("{n}")')]
        print(n, "->", ", ".join(cols))
    raise SystemExit


def measure(label):
    print(f"--- {label} ---")
    for row in c.execute("EXPLAIN QUERY PLAN " + a.sql):
        print("plan:", row[-1])
    t = []
    for _ in range(5):
        s = time.perf_counter(); c.execute(a.sql).fetchall(); t.append((time.perf_counter() - s) * 1000)
    print(f"time ms (best of 5): {min(t):.2f}")


measure("BEFORE")
if a.add_index:
    c.execute(a.add_index); c.commit()
    measure("AFTER")
