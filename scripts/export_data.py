"""Export a books table to CSV or Excel, with date filters or an incremental 'since'.
python -m scripts.export_data --list
python -m scripts.export_data TABLE --date-col COL --from 2024-01-01 --to 2025-06-30 --out payroll.csv
python -m scripts.export_data TABLE --date-col COL --since 2025-06-01 --out changes.xlsx   (needs: pip install openpyxl)"""
import argparse, csv, os, sqlite3

p = argparse.ArgumentParser()
p.add_argument("table", nargs="?")
p.add_argument("--db", default=os.environ.get("LEDGERFORGE_BOOKS_PATH", "ledgerforge.sqlite"))
p.add_argument("--date-col"); p.add_argument("--from", dest="d_from"); p.add_argument("--to")
p.add_argument("--since"); p.add_argument("--out", default="export.csv"); p.add_argument("--list", action="store_true")
a = p.parse_args()
c = sqlite3.connect(a.db)
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
if a.list or not a.table:
    print("\n".join(tables)); raise SystemExit
assert a.table in tables, "unknown table"
sql, args, where = f'SELECT * FROM "{a.table}"', [], []
if a.date_col:
    if a.d_from: where.append(f'"{a.date_col}" >= ?'); args.append(a.d_from)
    if a.to: where.append(f'"{a.date_col}" <= ?'); args.append(a.to)
    if a.since: where.append(f'"{a.date_col}" > ?'); args.append(a.since)
if where: sql += " WHERE " + " AND ".join(where)
cur = c.execute(sql, args)
head = [d[0] for d in cur.description]
if a.out.endswith(".xlsx"):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.append(head)
    n = 0
    for row in cur: ws.append(list(row)); n += 1
    wb.save(a.out)
else:
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(head); n = 0
        for row in cur: w.writerow(row); n += 1
print(f"wrote {n} rows to {a.out}")
