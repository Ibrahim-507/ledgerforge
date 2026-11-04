"""Task 15 financial reports and Task 14 statutory reports (read only)."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from app import financials as fin
from app import statutory_reports as sr
from app.deps import get_db

router = APIRouter(tags=["reports"])


@router.get("/reports/trial-balance")
def trial_balance(date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"), conn=Depends(get_db)):
    """Trial balance for a date range (leave both empty for everything)."""
    return fin.trial_balance(conn, date_from, date_to)


@router.get("/reports/profit-and-loss")
def profit_and_loss(date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"), conn=Depends(get_db)):
    return fin.profit_and_loss(conn, date_from, date_to)


@router.get("/reports/balance-sheet")
def balance_sheet(as_of: date | None = None, conn=Depends(get_db)):
    return fin.balance_sheet(conn, as_of)


@router.get("/reports/statutory-summary")
def statutory_summary(conn=Depends(get_db)):
    """What to remit each month for PF, ESI, TDS and professional tax, and whether it equals the ledger."""
    return sr.monthly_summary(conn)


@router.get("/reports/statutory/{kind}/{run_id}")
def statutory(kind: str, run_id: str, conn=Depends(get_db)):
    try:
        return sr.statutory_report(conn, run_id, kind)
    except sr.ReportError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
