"""Secures app/main.py (login on every route, /api/v1, new routers). Same logic as start_server.py.   python scripts\\patch_main.py"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from start_server import patch_main_text      # noqa: E402

main = Path("app/main.py")
if not main.exists():
    sys.exit("Run this from the project folder (the one that contains the app folder).")
new, msg = patch_main_text(main.read_text(encoding="utf-8-sig"))      # strips the hidden BOM that Windows PowerShell can add
if new is None:
    sys.exit("Nothing changed: " + msg)
shutil.copy(main, "app/main.py.bak")
main.write_text(new, encoding="utf-8")
print("Patched app/main.py (backup: app/main.py.bak).  Now run:  python -c \"import app.main\"")
