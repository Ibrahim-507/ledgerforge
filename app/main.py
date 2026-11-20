from fastapi import Depends, FastAPI

from app.deps import authorize
from app.routers import (
    auth, books_api, departments, employees, jobs_api, payslips,
    reports_api, salary, tax_api, web,
)

# All API endpoints are mounted explicitly under /api/v1. The web login/dashboard
# remains at / and health remains at /health. Keep the authorization dependency
# global; app.permissions decides public routes and role permissions.
app = FastAPI(
    title="LedgerForge API",
    version="0.1.0",
    description="Payroll, accounting and employee data engine for Zenith Nova Technologies",
    dependencies=[Depends(authorize)],
)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "ledgerforge"}


# Browser UI (public login; subsequent calls use bearer token)
app.include_router(web.router)

# Versioned API routers. Each router is included exactly once.
app.include_router(auth.router, prefix="/api/v1")
app.include_router(books_api.router, prefix="/api/v1")
app.include_router(reports_api.router, prefix="/api/v1")
app.include_router(tax_api.router, prefix="/api/v1")
app.include_router(departments.router, prefix="/api/v1")
app.include_router(employees.router, prefix="/api/v1")
app.include_router(salary.router, prefix="/api/v1")
app.include_router(payslips.router, prefix="/api/v1")
app.include_router(jobs_api.router, prefix="/api/v1")

from app.observability import install
install(app)
