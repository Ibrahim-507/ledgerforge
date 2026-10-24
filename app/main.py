from fastapi import FastAPI


from .routers import departments, employees

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