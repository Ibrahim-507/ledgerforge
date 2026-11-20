# Tasks 13, 14, 15: copy, wire up and run

## One-time setup (in the project folder, with (.venv) active)
```powershell
git checkout -b lf-13-15-secure-system        # branch FIRST, before copying files
pip install PyJWT
$src = "C:\Users\ibrah\Downloads\ledgerforge_tasks_13_15"      # where you extracted the zip
Copy-Item "$src\app\*.py" app\
Copy-Item "$src\app\routers\*.py" app\routers\
Copy-Item "$src\tests\*.py" tests\
Copy-Item "$src\scripts\*.py" scripts\
Copy-Item "$src\docs\*" docs\
```
Edit `app\main.py` (keep your own arguments and routers):
```python
from fastapi import Depends, FastAPI
from app.deps import authorize
from app.routers import auth, books_api, reports_api, tax_api

app = FastAPI(title="LedgerForge API", dependencies=[Depends(authorize)])
app.include_router(auth.router)
app.include_router(books_api.router)
app.include_router(reports_api.router)
app.include_router(tax_api.router)
```
Create or extend `tests\conftest.py` so your OLD API tests still run (they have no login):
```python
import pytest
from app.deps import authorize
from app.main import app

@pytest.fixture(autouse=True)
def open_api_for_old_tests(request):
    if "security" in request.node.fspath.basename or "api_reports" in request.node.fspath.basename:
        yield
        return
    app.dependency_overrides[authorize] = lambda: None
    yield
    app.dependency_overrides.pop(authorize, None)
```

## Task 13: logins
```powershell
$env:LEDGERFORGE_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
python -m scripts.init_db
python -m pytest tests/test_security.py tests/test_api_security.py -q
python -m scripts.print_role_table
```
## Task 14: taxes and statutory reports
```powershell
python -m pytest tests/test_tax_config.py tests/test_statutory_reports.py -q
python -m scripts.task14_run
```
## Task 15: financial reports
```powershell
python -m pytest tests/test_financials.py tests/test_api_reports.py -q
python -m scripts.task15_run
python verify_ledgerforge.py summary --data csv
python verify_ledgerforge.py trial-balance my_trial_balance.csv --data csv
```
## Try the API in the browser
```powershell
python -m scripts.load_official_books
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs. Log in with `POST /auth/login`, click Authorize, paste the token, then call `/reports/balance-sheet?as_of=2026-09-30`.

## Everything, then submit
```powershell
python -m pytest -q
git add .
git commit -m "Tasks 13-15: logins and roles, tax rules as data, statutory and financial reports"
git push --set-upstream origin lf-13-15-secure-system
git tag phase-3
git push --tags
```
