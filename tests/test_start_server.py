"""The main.py patcher must cope with a file that starts with a hidden BOM (Windows PowerShell adds one when it saves a file)."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOM = b"\xef\xbb\xbf"


def load_start_server():
    spec = importlib.util.spec_from_file_location("start_server_under_test", ROOT / "start_server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_patch_script_handles_a_main_py_with_a_bom():
    work = Path(tempfile.mkdtemp())
    (work / "app").mkdir()
    (work / "app" / "main.py").write_bytes(BOM + b'from fastapi import FastAPI\napp = FastAPI(title="X")\n')
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "patch_main.py")], cwd=work, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    new = (work / "app" / "main.py").read_bytes()
    assert not new.startswith(BOM) and b"_prefix_all(app)" in new and b"_authorize" in new
    assert (work / "app" / "main.py.bak").exists()
    again = subprocess.run([sys.executable, str(ROOT / "scripts" / "patch_main.py")], cwd=work, capture_output=True, text=True, timeout=60)
    assert again.returncode != 0 and "already secured" in (again.stdout + again.stderr)        # a second run changes nothing


def test_patching_puts_the_version_line_before_every_include():
    ss = load_start_server()
    new, msg = ss.patch_main_text('from fastapi import FastAPI\nfrom app.routers import employees\napp = FastAPI()\napp.include_router(employees.router)\n')
    assert msg == "patched" and new.index("_prefix_all(app)") < new.index("app.include_router(employees.router)")
    assert ss.patch_main_text(new) == (None, "already secured")


def test_a_real_syntax_error_is_reported_not_hidden():
    ss = load_start_server()
    new, msg = ss.patch_main_text("app = FastAPI(\n")
    assert new is None and "syntax error" in msg
