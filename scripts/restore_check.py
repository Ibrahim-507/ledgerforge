"""Restore a backup into a FRESH file and compare row counts with the source.
python -m scripts.restore_check backups/books_XXXX.sqlite [source.sqlite]"""
import os, shutil, sqlite3, sys, tempfile

backup = sys.argv[1]
source = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("LEDGERFORGE_BOOKS_PATH", "ledgerforge.sqlite")
fresh = os.path.join(tempfile.mkdtemp(), "restored.sqlite")
shutil.copy(backup, fresh)


def counts(p):
    c = sqlite3.connect(p)
    names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    out = {n: c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
    c.close()
    return out


s, r = counts(source), counts(fresh)
ok = True
print(f"{'table':35}{'source':>10}{'restored':>10}")
for n in sorted(s):
    same = s[n] == r.get(n)
    ok &= same
    print(f"{n:35}{s[n]:>10}{r.get(n, 'MISSING'):>10}  {'OK' if same else 'DIFF'}")
print("RESTORE", "PROVED" if ok else "FAILED")
sys.exit(0 if ok else 1)
