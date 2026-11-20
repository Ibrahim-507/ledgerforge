"""Task 16: background jobs. The 18-month payroll is too big to run inside one web request, so it runs as a JOB:
  * the API creates a job row and puts its id on a queue (Celery + Redis in Docker, a thread when there is no Redis),
  * a worker runs it and writes progress (done / total) into the `jobs` table after every month,
  * GET /api/v1/jobs/{id} just reads that row, so progress works whichever process runs the job.
Two kinds, because running payroll and approving it must stay two different people (separation of duties):
  payroll-process  create + process every month           (HR or Admin)
  payroll-approve  approve (post) every processed month, optionally pay   (Admin; months you ran yourself are skipped)
Jobs are safe to repeat: months already done are skipped, so a job that stopped halfway can simply be started again."""
import json
import os
import threading
import traceback
from datetime import datetime

from app.books_db import connect, next_id
from app.payroll_runs import RunError, RunSeparationError, approve_run, create_run, months_between, pay_run, process_run

KINDS = ("payroll-process", "payroll-approve")


class JobError(Exception):
    pass


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row(r) -> dict:
    d = dict(r)
    d["params"] = json.loads(d["params"]) if d.get("params") else {}
    d["result"] = json.loads(d["result"]) if d.get("result") else None
    d["percent"] = round(100 * d["done"] / d["total"], 1) if d["total"] else (100.0 if d["status"] == "DONE" else 0.0)
    return d


def _valid_month(m: str) -> str:
    try:
        datetime.strptime(m, "%Y-%m")
    except (TypeError, ValueError):
        raise JobError(f"'{m}' is not a month. Use YYYY-MM, for example 2025-04")
    return m


def create_job(conn, kind, params: dict, created_by) -> str:
    if kind not in KINDS:
        raise JobError(f"Unknown job kind '{kind}'. Use one of: {', '.join(KINDS)}")
    if not created_by:
        raise JobError("A job must record who started it")
    first, last = _valid_month(params.get("first", "2025-04")), _valid_month(params.get("last", "2026-09"))
    if first > last:
        raise JobError("'first' must not be after 'last'")
    total = len(list(months_between(first, last)))
    if total > 60:
        raise JobError("A job can cover at most 60 months")
    params = {"first": first, "last": last, "pay": bool(params.get("pay", False))}
    job_id = next_id(conn, "jobs", "job_id", "JOB-", 6)
    conn.execute("INSERT INTO jobs(job_id, kind, status, total, done, message, params, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                 (job_id, kind, "QUEUED", total, 0, "Waiting for a worker", json.dumps(params), created_by, _now()))
    conn.commit()
    return job_id


def get_job(conn, job_id) -> dict:
    r = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if r is None:
        raise JobError(f"Job {job_id} not found")
    return _row(r)


def list_jobs(conn, limit=50, offset=0):
    return [_row(r) for r in conn.execute("SELECT * FROM jobs ORDER BY job_id DESC LIMIT ? OFFSET ?", (limit, offset))]


def _progress(conn, job_id, done, message):
    conn.execute("UPDATE jobs SET done=?, message=? WHERE job_id=?", (done, message, job_id))
    conn.commit()


def execute_job(db_path, job_id, data_dir=None, source=None) -> dict:
    """Run one job to the end. Called by the Celery worker (or a thread). Never raises: a failure is written on the job row."""
    conn = connect(db_path, check_same_thread=False)
    try:
        job = get_job(conn, job_id)
        if job["status"] in ("RUNNING", "DONE"):
            return job                                                    # a repeat delivery of the same message: do nothing
        conn.execute("UPDATE jobs SET status='RUNNING', started_at=?, message='Starting' WHERE job_id=?", (_now(), job_id))
        conn.commit()
        if source is None:
            from app.payroll_data import PayrollSource
            source = PayrollSource(data_dir or os.environ.get("LEDGERFORGE_DATA", "data"))
        p = job["params"]
        months = list(months_between(p["first"], p["last"]))
        result = {"months": len(months), "processed": 0, "already_done": 0, "approved": 0, "skipped_same_person": 0, "paid": 0}
        for i, start in enumerate(months, 1):
            label = f"{start:%Y-%m}"
            if job["kind"] == "payroll-process":
                rid = create_run(conn, start, job["created_by"])
                row = conn.execute("SELECT status FROM payroll_runs WHERE run_id=?", (rid,)).fetchone()
                if row["status"] == "DRAFT":
                    process_run(conn, source, rid)
                    result["processed"] += 1
                else:
                    result["already_done"] += 1
            else:
                r = conn.execute("SELECT run_id, status FROM payroll_runs WHERE period_start=? AND status IN ('PROCESSED','APPROVED','PAID')",
                                 (start.isoformat(),)).fetchone()
                if r is None:
                    raise JobError(f"{label} has not been processed yet: run a payroll-process job first")
                try:
                    if r["status"] == "PROCESSED":
                        approve_run(conn, r["run_id"], job["created_by"])
                        result["approved"] += 1
                    else:
                        result["already_done"] += 1
                except RunSeparationError:
                    result["skipped_same_person"] += 1                    # you ran this month, so you may not approve it
                if p["pay"]:
                    cur = conn.execute("SELECT status FROM payroll_runs WHERE run_id=?", (r["run_id"],)).fetchone()["status"]
                    if cur == "APPROVED":
                        pay_run(conn, r["run_id"], job["created_by"])
                        result["paid"] += 1
            _progress(conn, job_id, i, f"Finished {label} ({i} of {len(months)})")
        conn.execute("UPDATE jobs SET status='DONE', finished_at=?, message=?, result=? WHERE job_id=?",
                     (_now(), "All months finished", json.dumps(result), job_id))
        conn.commit()
    except Exception as exc:                                              # the job FAILS visibly; nothing crashes the worker
        conn.rollback()
        conn.execute("UPDATE jobs SET status='FAILED', finished_at=?, error=?, message=? WHERE job_id=?",
                     (_now(), f"{type(exc).__name__}: {exc}"[:600], "Stopped by an error: start the job again to continue", job_id))
        conn.commit()
        print(traceback.format_exc())
    finally:
        out = get_job(conn, job_id)
        conn.close()
    return out


def enqueue(job_id, db_path) -> str:
    """Put the job on the queue. With CELERY_BROKER_URL set (Docker) a Celery worker runs it; otherwise a thread does (laptop, tests).
    The backend name is written BEFORE the job is handed over, so a fast worker can never run it first."""
    from app import worker
    backend = "celery" if worker.celery_app is not None else "thread"
    conn = connect(db_path, check_same_thread=False)
    conn.execute("UPDATE jobs SET backend=? WHERE job_id=?", (backend, job_id))
    conn.commit()
    conn.close()
    if backend == "celery":
        worker.run_job_task.delay(job_id)
    else:
        threading.Thread(target=execute_job, args=(db_path, job_id), daemon=True).start()
    return backend
