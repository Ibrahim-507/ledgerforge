from fastapi import FastAPI
from app.routers import payslips


from .routers import departments, employees, salary, payslips
from fastapi import Depends, FastAPI
from app.deps import authorize
from app.routers import auth, books_api,  reports_api, tax_api

app = FastAPI(title="LedgerForge API", dependencies=[Depends(authorize)])   # keep your other arguments
app.include_router(auth.router)
app.include_router(books_api.router)
app.include_router(reports_api.router)
app.include_router(tax_api.router)
app = FastAPI(
    title="LedgerForge API",
    version="0.1.0",
    description="Payroll, accounting and employee data engine for Zenith Nova Technologies",
)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "ledgerforge"}


app.include_router(departments.router)
app.include_router(employees.router)
app.include_router(salary.router)
app.include_router(payslips.router)