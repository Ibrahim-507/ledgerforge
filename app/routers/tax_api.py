"""Task 14: tax rules as data. Anyone in HR/Admin may READ them; only ADMIN may change them (see app/permissions.py)."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app import tax_config as tc
from app.deps import get_db
from app.tax_explain import explain_tds

router = APIRouter(prefix="/tax", tags=["tax rules"])


class SlabChange(BaseModel):
    rate_percent: Decimal | None = None
    income_to: Decimal | None = None
    reason: str


class ValueChange(BaseModel):
    value: Decimal
    reason: str


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except tc.RuleError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))


@router.get("/slabs")
def slabs(financial_year: str | None = None, conn=Depends(get_db)):
    return tc.list_slabs(conn, financial_year)


@router.put("/slabs/{slab_id}")
def change_slab(slab_id: str, body: SlabChange, request: Request, conn=Depends(get_db)):
    return _guard(tc.update_slab, conn, slab_id, request.state.user["user_id"], body.reason, body.rate_percent, body.income_to)


@router.get("/parameters")
def parameters(conn=Depends(get_db)):
    return [dict(r) for r in conn.execute("SELECT * FROM tax_parameters")]


@router.put("/parameters/{name}")
def change_parameter(name: str, body: ValueChange, request: Request, conn=Depends(get_db)):
    return _guard(tc.update_parameter, conn, name, body.value, request.state.user["user_id"], body.reason)


@router.get("/statutory-rates")
def statutory_rates(conn=Depends(get_db)):
    return [dict(r) for r in conn.execute("SELECT * FROM statutory_rates")]


@router.put("/statutory-rates/{name}")
def change_rate(name: str, body: ValueChange, request: Request, conn=Depends(get_db)):
    return _guard(tc.update_statutory_rate, conn, name, body.value, request.state.user["user_id"], body.reason)


@router.get("/rule-changes")
def rule_changes(conn=Depends(get_db)):
    return tc.list_changes(conn)


@router.get("/explain")
def explain(monthly_fixed_gross: Decimal, financial_year: str = "FY2025-26", variable_pay: Decimal = Decimal("0"),
            payable_days: Decimal = Decimal("30"), calendar_days: Decimal = Decimal("30"), conn=Depends(get_db)):
    """The tax calculation step by step for one month."""
    rules = tc.load_rules(conn)
    if rules is None or financial_year not in rules[2]:
        raise HTTPException(status_code=404, detail=f"No tax rules loaded for {financial_year}")
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in explain_tds(monthly_fixed_gross, variable_pay, payable_days,
                                                                                   calendar_days, rules[2][financial_year], rules[1]).items()
            if k != "slab_lines"}
