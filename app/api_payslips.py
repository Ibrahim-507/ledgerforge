"""FastAPI endpoints for payslips. Mount with:
    from app.api_payslips import build_router
    app.include_router(build_router(PayrollSource("data")))
Authentication here is a STAND-IN: the caller sends header  X-User-Id: U-0099  and the user is
looked up in users.csv. Replace get_current_user with your JWT dependency in Task 13."""
import pandas as pd
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from app.payslip_service import get_payslip_for_user, render_pdf


def build_router(source, users_csv=None) -> APIRouter:
    users = pd.read_csv(users_csv or f"{source.dir}/users.csv").set_index("user_id")
    router = APIRouter(prefix="/payslips", tags=["payslips"])

    def get_current_user(x_user_id: str | None) -> dict:
        if not x_user_id or x_user_id not in users.index:
            raise HTTPException(status_code=401, detail="Unknown or missing user")
        u = users.loc[x_user_id]
        return {"user_id": x_user_id, "role": u.role, "employee_id": u.employee_id, "is_active": u.is_active}

    def fetch(x_user_id, employee_id, run_id):
        user = get_current_user(x_user_id)
        try:
            return get_payslip_for_user(user, source, employee_id, run_id)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.get("/{employee_id}/{run_id}")
    def payslip_json(employee_id: str, run_id: str, x_user_id: str | None = Header(default=None)):
        return fetch(x_user_id, employee_id, run_id)

    @router.get("/{employee_id}/{run_id}/pdf")
    def payslip_pdf(employee_id: str, run_id: str, x_user_id: str | None = Header(default=None)):
        pdf = render_pdf(fetch(x_user_id, employee_id, run_id))
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="payslip_{employee_id}_{run_id}.pdf"'})

    return router
