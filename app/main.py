from fastapi import Depends, FastAPI

from app.deps import authorize
from app.routers import (
    auth, books_api, departments, employees, payslips, reports_api, salary, tax_api,
)

# ONE app. Every route is checked by authorize() against the rules in app/permissions.py.
app = FastAPI(
    title="LedgerForge API",
    version="0.1.0",
    description="Payroll, accounting and employee data engine for Zenith Nova Technologies",
    dependencies=[Depends(authorize)],
)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "ledgerforge"}


app.include_router(auth.router)
app.include_router(books_api.router)
app.include_router(reports_api.router)
app.include_router(tax_api.router)
app.include_router(departments.router)
app.include_router(employees.router)
app.include_router(salary.router)
app.include_router(payslips.router)
