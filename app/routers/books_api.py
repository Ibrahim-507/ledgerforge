"""Payroll-run and vendor-bill endpoints. WHO is acting always comes from the login token, never from the request body,
so 'the approver is not the person who created it' cannot be faked."""
import os
from datetime import date
from decimal import Decimal
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app import expenses as bills
from app import payroll_runs as runs
from app.deps import get_db
from app.ledger import LedgerError
from app.payroll_data import PayrollSource

router = APIRouter()


@lru_cache(maxsize=1)
def get_source() -> PayrollSource:
    return PayrollSource(os.environ.get("LEDGERFORGE_DATA", "data"))


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (runs.RunSeparationError, bills.SeparationOfDutiesError) as e:
        raise HTTPException(status_code=403, detail=str(e))
    except bills.DuplicateBillError as e:
        raise HTTPException(status_code=409, detail={"message": str(e), "matches": e.matches})
    except (runs.RunError, bills.BillError, LedgerError) as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 409, detail=str(e))


def _uid(request: Request) -> str:
    return request.state.user["user_id"]


# ---------------- payroll runs ----------------
class RunIn(BaseModel):
    period_start: date


class ReverseIn(BaseModel):
    reverse_date: date
    reason: str


def _run_row(conn, run_id):
    r = conn.execute("SELECT * FROM payroll_runs WHERE run_id=?", (run_id,)).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail=f"Payroll run {run_id} not found")
    return dict(r)


@router.get("/payroll-runs", tags=["payroll runs"])
def list_runs(conn=Depends(get_db)):
    return [dict(r) for r in conn.execute("SELECT * FROM payroll_runs ORDER BY period_start, run_id")]


@router.get("/payroll-runs/{run_id}", tags=["payroll runs"])
def get_run(run_id: str, conn=Depends(get_db)):
    return _run_row(conn, run_id)


@router.post("/payroll-runs", tags=["payroll runs"])
def create_run(body: RunIn, request: Request, conn=Depends(get_db)):
    return _run_row(conn, _guard(runs.create_run, conn, body.period_start, _uid(request)))


@router.post("/payroll-runs/{run_id}/process", tags=["payroll runs"])
def process_run(run_id: str, conn=Depends(get_db)):
    _guard(runs.process_run, conn, get_source(), run_id)
    return _run_row(conn, run_id)


@router.post("/payroll-runs/{run_id}/approve", tags=["payroll runs"])
def approve_run(run_id: str, request: Request, conn=Depends(get_db)):
    _guard(runs.approve_run, conn, run_id, _uid(request))
    return _run_row(conn, run_id)


@router.post("/payroll-runs/{run_id}/pay", tags=["payroll runs"])
def pay_run(run_id: str, request: Request, conn=Depends(get_db)):
    _guard(runs.pay_run, conn, run_id, _uid(request))
    return _run_row(conn, run_id)


@router.post("/payroll-runs/{run_id}/reverse", tags=["payroll runs"])
def reverse_run(run_id: str, body: ReverseIn, request: Request, conn=Depends(get_db)):
    _guard(runs.reverse_run, conn, run_id, body.reverse_date, body.reason, _uid(request))
    return _run_row(conn, run_id)


# ---------------- vendor bills ----------------
class BillIn(BaseModel):
    vendor_id: str
    bill_date: date
    category_account: int
    amount_excl_gst: Decimal
    gst_rate_percent: Decimal = Decimal("18")
    department_id: str | None = None
    description: str | None = None
    bill_reference: str | None = None
    allow_duplicate: bool = False


class RejectIn(BaseModel):
    reason: str = ""


class PayBillIn(BaseModel):
    paid_date: date
    payment_mode: str = "NEFT"


def _bill_row(conn, expense_id):
    r = conn.execute("SELECT * FROM expenses WHERE expense_id=?", (expense_id,)).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail=f"Bill {expense_id} not found")
    return dict(r)


@router.get("/bills", tags=["vendor bills"])
def list_bills(status: str | None = None, conn=Depends(get_db)):
    sql, args = "SELECT * FROM expenses", ()
    if status:
        sql, args = sql + " WHERE status=?", (status,)
    return [dict(r) for r in conn.execute(sql + " ORDER BY expense_date, expense_id LIMIT 500", args)]


@router.post("/bills", tags=["vendor bills"])
def submit_bill(body: BillIn, request: Request, conn=Depends(get_db)):
    eid = _guard(bills.submit_bill, conn, body.vendor_id, body.bill_date, body.category_account, body.amount_excl_gst,
                 body.gst_rate_percent, _uid(request), body.department_id, body.description, body.bill_reference,
                 body.allow_duplicate)
    return _bill_row(conn, eid)


@router.post("/bills/{expense_id}/approve", tags=["vendor bills"])
def approve_bill(expense_id: str, request: Request, conn=Depends(get_db)):
    _guard(bills.approve_bill, conn, expense_id, _uid(request))
    return _bill_row(conn, expense_id)


@router.post("/bills/{expense_id}/reject", tags=["vendor bills"])
def reject_bill(expense_id: str, body: RejectIn, request: Request, conn=Depends(get_db)):
    _guard(bills.reject_bill, conn, expense_id, _uid(request), body.reason)
    return _bill_row(conn, expense_id)


@router.post("/bills/{expense_id}/pay", tags=["vendor bills"])
def pay_bill(expense_id: str, body: PayBillIn, request: Request, conn=Depends(get_db)):
    _guard(bills.pay_bill, conn, expense_id, body.paid_date, body.payment_mode, _uid(request))
    return _bill_row(conn, expense_id)


@router.get("/reports/spend", tags=["reports"])
def spend(conn=Depends(get_db)):
    return bills.spend_report(conn)
