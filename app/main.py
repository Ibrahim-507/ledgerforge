from fastapi import FastAPI
from app.routers import payslips


from .routers import departments, employees, salary, payslips

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