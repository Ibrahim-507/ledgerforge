from app.payroll_data import PayrollSource
from app.api_payslips import build_router

router = build_router(PayrollSource("data"))