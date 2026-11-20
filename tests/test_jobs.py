import os
import sqlite3
import time
from pathlib import Path
import pytest
import app.jobs as J
from app.books_db import connect
from app.checks import check2_payroll_matches_ledger
from app.jobs import JobError, create_job, enqueue, execute_job, get_job, list_jobs
from app.ledger import load_chart

DATA = str(Path(__file__).resolve().parent.parent / "data")
RUN_BY, ADMIN = "U-0237", "U-0099"


def db_file(tmp_path):
    path = str(Path(tmp_path) / "jobs.sqlite")
    c = connect(path)
    load_chart(c, Path(DATA) / "chart_of_accounts.csv")
    c.close()
    return path


def n(c, sql):
    return c.execute(sql).fetchone()[0]


def test_bad_jobs_are_refused():
    c = connect()
    for kind, params, who, msg in [("payroll-nothing", {}, RUN_BY, "Unknown job kind"), ("payroll-process", {"first": "2025-13"}, RUN_BY, "not a month"),
                                   ("payroll-process", {"first": "April"}, RUN_BY, "not a month"), ("payroll-process", {"first": "2026-05", "last": "2026-01"}, RUN_BY, "must not be after"),
                                   ("payroll-process", {"first": "2020-01", "last": "2030-12"}, RUN_BY, "at most 60"), ("payroll-process", {}, "", "who started")]:
        with pytest.raises(JobError, match=msg):
            create_job(c, kind, params, who)
    with pytest.raises(JobError, match="not found"):
        get_job(c, "JOB-999999")


def test_process_job_runs_every_month_and_reports_progress(tmp_path):
    db = db_file(tmp_path)
    c = connect(db)
    job = create_job(c, "payroll-process", {"first": "2025-04", "last": "2025-06"}, RUN_BY)
    first = get_job(c, job)
    assert (first["status"], first["done"], first["total"], first["percent"]) == ("QUEUED", 0, 3, 0.0)
    seen, real = [], J.process_run

    def watching(conn, source, run_id):
        seen.append(get_job(conn, job)["done"])               # progress as the worker moves from month to month
        return real(conn, source, run_id)
    J.process_run = watching
    try:
        out = execute_job(db, job, DATA)
    finally:
        J.process_run = real
    assert seen == [0, 1, 2]
    assert (out["status"], out["done"], out["total"], out["percent"]) == ("DONE", 3, 3, 100.0)
    assert out["result"]["processed"] == 3 and out["message"] == "All months finished" and out["finished_at"]
    assert n(c, "SELECT COUNT(*) FROM payroll_runs WHERE status='PROCESSED'") == 3
    assert n(c, "SELECT COUNT(*) FROM journal_entries") == 0              # processing posts nothing: approval is a separate step


def test_a_job_is_safe_to_repeat(tmp_path):
    db = db_file(tmp_path)
    c = connect(db)
    execute_job(db, create_job(c, "payroll-process", {"first": "2025-04", "last": "2025-05"}, RUN_BY), DATA)
    items = n(c, "SELECT COUNT(*) FROM payroll_items")
    again = execute_job(db, create_job(c, "payroll-process", {"first": "2025-04", "last": "2025-05"}, RUN_BY), DATA)
    assert again["result"]["processed"] == 0 and again["result"]["already_done"] == 2
    assert n(c, "SELECT COUNT(*) FROM payroll_items") == items and n(c, "SELECT COUNT(*) FROM payroll_runs") == 2
    assert execute_job(db, create_job(c, "payroll-process", {"first": "2025-04", "last": "2025-05"}, RUN_BY), DATA)["status"] == "DONE"
    done = execute_job(db, again["job_id"], DATA)                            # the same message delivered twice: nothing happens
    assert done["status"] == "DONE"


def test_approve_job_posts_every_month_once_and_pays(tmp_path):
    db = db_file(tmp_path)
    c = connect(db)
    execute_job(db, create_job(c, "payroll-process", {"first": "2025-04", "last": "2025-06"}, RUN_BY), DATA)
    out = execute_job(db, create_job(c, "payroll-approve", {"first": "2025-04", "last": "2025-06", "pay": True}, ADMIN), DATA)
    assert out["status"] == "DONE" and out["result"]["approved"] == 3 and out["result"]["paid"] == 3
    assert n(c, "SELECT COUNT(*) FROM journal_entries") == 6                  # 3 postings + 3 salary payments
    k = check2_payroll_matches_ledger(c)
    assert k["ok"] and k["runs"] == 3 and all(d["difference"] == "0.00" for d in k["detail"])
    again = execute_job(db, create_job(c, "payroll-approve", {"first": "2025-04", "last": "2025-06", "pay": True}, ADMIN), DATA)
    assert again["result"]["approved"] == 0 and n(c, "SELECT COUNT(*) FROM journal_entries") == 6   # a second job posts nothing


def test_nobody_can_approve_months_they_ran_themselves(tmp_path):
    db = db_file(tmp_path)
    c = connect(db)
    execute_job(db, create_job(c, "payroll-process", {"first": "2025-04", "last": "2025-05"}, RUN_BY), DATA)
    out = execute_job(db, create_job(c, "payroll-approve", {"first": "2025-04", "last": "2025-05"}, RUN_BY), DATA)   # same person
    assert out["status"] == "DONE" and out["result"]["skipped_same_person"] == 2 and out["result"]["approved"] == 0
    assert n(c, "SELECT COUNT(*) FROM payroll_runs WHERE status='PROCESSED'") == 2 and n(c, "SELECT COUNT(*) FROM journal_entries") == 0


def test_failures_are_visible_and_a_new_job_can_continue(tmp_path):
    db = db_file(tmp_path)
    c = connect(db)
    out = execute_job(db, create_job(c, "payroll-approve", {"first": "2025-04", "last": "2025-04"}, ADMIN), DATA)
    assert out["status"] == "FAILED" and "has not been processed" in out["error"] and "start the job again" in out["message"]
    bad = execute_job(db, create_job(c, "payroll-process", {"first": "2025-04", "last": "2025-04"}, RUN_BY), str(Path(tmp_path) / "no-such-data"))
    assert bad["status"] == "FAILED" and bad["error"]                           # a missing data folder fails the job, not the worker
    good = execute_job(db, create_job(c, "payroll-process", {"first": "2025-04", "last": "2025-04"}, RUN_BY), DATA)
    assert good["status"] == "DONE"


def test_without_a_broker_enqueue_uses_a_thread_and_the_job_finishes(tmp_path):
    db = db_file(tmp_path)
    c = connect(db)
    os.environ["LEDGERFORGE_DATA"] = DATA
    job = create_job(c, "payroll-process", {"first": "2025-04", "last": "2025-04"}, RUN_BY)
    assert enqueue(job, db) == "thread"
    reader = connect(db)                                                       # one reading connection, reused while the worker writes
    end, final = time.time() + 120, None
    while time.time() < end:
        try:
            final = get_job(reader, job)
        except sqlite3.OperationalError:                                       # the worker holds the write lock for a moment: try again
            final = None
        if final and final["status"] in ("DONE", "FAILED"):
            break
        time.sleep(0.3)
    assert final and final["status"] == "DONE" and final["backend"] == "thread"


def test_list_jobs_newest_first_with_paging():
    c = connect()
    ids = [create_job(c, "payroll-process", {"first": "2025-04", "last": "2025-04"}, RUN_BY) for _ in range(3)]
    assert [j["job_id"] for j in list_jobs(c)] == ids[::-1]
    assert [j["job_id"] for j in list_jobs(c, limit=1, offset=1)] == [ids[1]]
