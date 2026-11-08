"""Adds the security dependency and the new routers to app/main.py. Safe to run twice. Makes app/main.py.bak first.
Run from the project folder:   python scripts\\patch_main.py"""
import ast
import re
import shutil
import sys
from pathlib import Path

MAIN = Path("app/main.py")
if not MAIN.exists():
    sys.exit("Run this from the project folder (the one that contains the app folder). app/main.py was not found.")
src = MAIN.read_text(encoding="utf-8")

if "_authorize" in src and "_auth_router.router" in src:
    print("app/main.py is already patched. Nothing to do.")
    sys.exit(0)

m = re.search(r"^(?P<indent>[ \t]*)app\s*=\s*FastAPI\(", src, re.M)
if not m:
    sys.exit("Could not find a line like  app = FastAPI(...)  in app/main.py. Paste the file in the chat and I will edit it for you.")
if re.search(r"FastAPI\([^)]*dependencies\s*=", src, re.S):
    sys.exit("Your FastAPI(...) already has dependencies=. Paste app/main.py in the chat and I will edit it for you.")

shutil.copy(MAIN, "app/main.py.bak")

imports = (
    "from fastapi import Depends as _Depends\n"
    "from app.deps import authorize as _authorize\n"
    "from app.routers import auth as _auth_router, books_api as _books_api, reports_api as _reports_api, tax_api as _tax_api\n\n"
)
src = src[:m.start()] + imports + src[m.start():]
src = re.sub(r"^([ \t]*app\s*=\s*FastAPI\()", r"\1dependencies=[_Depends(_authorize)], ", src, count=1, flags=re.M)

block = (
    "\n# --- Tasks 13-15: login, permissions and the new routers (added by scripts/patch_main.py) ---\n"
    "app.include_router(_auth_router.router)\n"
    "app.include_router(_books_api.router)\n"
    "app.include_router(_reports_api.router)\n"
    "app.include_router(_tax_api.router)\n"
)
main_guard = re.search(r"^if\s+__name__\s*==", src, re.M)
if main_guard:
    src = src[:main_guard.start()] + block.lstrip("\n") + "\n" + src[main_guard.start():]
else:
    src = src.rstrip("\n") + "\n" + block

try:
    ast.parse(src)
except SyntaxError as e:
    sys.exit(f"The edited file would not be valid Python ({e}). Nothing was changed. Paste app/main.py in the chat.")

MAIN.write_text(src, encoding="utf-8")
print("Patched app/main.py (backup saved as app/main.py.bak). Now run:  python -c \"import app.main\"")