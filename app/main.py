from fastapi import FastAPI
from .database import Base, engine
from .routers import departments
Base.metadata.create_all(engine)   # LF-02 upgrade: replace this with Alembic migrations
app = FastAPI(title="LedgerForge API", version="0.1.0", description="Payroll, accounting and employee data engine for Zenith Nova Technologies")
@app.get("/health", tags=["system"])
def health(): return {"status": "ok", "service": "ledgerforge"}
app.include_router(departments.router)
# LF-04: include your employees router here, and so on.
