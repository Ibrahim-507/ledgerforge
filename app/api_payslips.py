"""Payslip endpoints. WHO may call them is decided centrally by app/permissions.py (the `authorize` dependency, set on the
app). The service ALSO checks ownership (defence in depth), using the user that `authorize` stored on the request."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from app.payslip_service import get_payslip_for_user, render_pdf


def build_router(source, users_csv=None) -> APIRouter:      # users_csv kept for old callers; logins now come from the token
    router = APIRouter(prefix="/payslips", tags=["payslips"])

    def fetch(request: Request, employee_id: str, run_id: str):
        try:
            return get_payslip_for_user(request.state.user, source, employee_id, run_id)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.get("/{employee_id}/{run_id}")
    def payslip_json(employee_id: str, run_id: str, request: Request):
        return fetch(request, employee_id, run_id)

    @router.get("/{employee_id}/{run_id}/pdf")
    def payslip_pdf(employee_id: str, run_id: str, request: Request):
        pdf = render_pdf(fetch(request, employee_id, run_id))
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="payslip_{employee_id}_{run_id}.pdf"'})

    return router
