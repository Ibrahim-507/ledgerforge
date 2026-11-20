"""Background jobs: start the bulk payroll and watch its progress."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app import jobs
from app.deps import db_path, get_db

router = APIRouter(tags=["jobs"])


class PayrollJobIn(BaseModel):
    first: str = Field(default="2025-04", examples=["2025-04"])
    last: str = Field(default="2026-09", examples=["2026-09"])
    pay: bool = Field(default=False, examples=[False])


def _start(kind, body: PayrollJobIn, request: Request, conn):
    try:
        job_id = jobs.create_job(conn, kind, body.model_dump(), request.state.user["user_id"])
    except jobs.JobError as e:
        raise HTTPException(status_code=400, detail=str(e))
    jobs.enqueue(job_id, db_path())
    return jobs.get_job(conn, job_id)


@router.post("/jobs/payroll-process", status_code=202)
def start_process(body: PayrollJobIn, request: Request, conn=Depends(get_db)):
    """Create and process every month in the range. Returns at once with a job id: poll GET /jobs/{job_id}."""
    return _start("payroll-process", body, request, conn)


@router.post("/jobs/payroll-approve", status_code=202)
def start_approve(body: PayrollJobIn, request: Request, conn=Depends(get_db)):
    """Approve (post to the ledger) every processed month, and pay them if pay=true. Months you ran yourself are skipped."""
    return _start("payroll-approve", body, request, conn)


@router.get("/jobs")
def list_jobs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), conn=Depends(get_db)):
    return jobs.list_jobs(conn, limit, offset)


@router.get("/jobs/{job_id}")
def job_progress(job_id: str, conn=Depends(get_db)):
    """Progress: status, done, total, percent, message, and the result when finished."""
    try:
        return jobs.get_job(conn, job_id)
    except jobs.JobError as e:
        raise HTTPException(status_code=404, detail=str(e))
