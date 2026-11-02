import pytest
from pathlib import Path
import pandas as pd
from app.money_format import inr
from app.payroll_data import PayrollSource
from app.payslip_service import build_payslip, can_view_payslip, get_payslip_for_user, render_pdf

DATA = Path(__file__).resolve().parent.parent / "data"
src = PayrollSource(str(DATA))
key = pd.read_csv(DATA / "payroll_items.csv").set_index(["employee_id", "run_id"])

OWNER = {"user_id": "U-0002", "role": "EMPLOYEE", "employee_id": "EMP-0002", "is_active": "Y"}
STRANGER = {"user_id": "U-0003", "role": "EMPLOYEE", "employee_id": "EMP-0003", "is_active": "Y"}
HR = {"user_id": "U-0005", "role": "HR", "employee_id": "EMP-0005", "is_active": "Y"}


def test_indian_number_format():
    assert inr(123456) == "1,23,456.00"
    assert inr("12345678.9") == "1,23,45,678.90"
    assert inr(999) == "999.00" and inr(1000) == "1,000.00" and inr(0) == "0.00" and inr(-1500.5) == "-1,500.50"


def test_three_payslips_equal_official_totals():
    for emp, run in [("EMP-0002", "PR-2025-04"), ("EMP-0131", "PR-2025-12"), ("EMP-0319", "PR-2025-04")]:
        d = build_payslip(src, emp, run)
        official = key.loc[(emp, run)]
        assert d["gross_pay"] == official.gross_pay
        assert d["total_deductions"] == official.total_deductions
        assert d["net_pay"] == official.net_pay
        assert round(sum(x["amount"] for x in d["earnings"]), 2) == d["gross_pay"]
        assert round(sum(x["amount"] for x in d["deductions"]), 2) == d["total_deductions"]


def test_stranger_is_refused():
    with pytest.raises(PermissionError):
        get_payslip_for_user(STRANGER, src, "EMP-0002", "PR-2025-04")


def test_owner_and_hr_allowed():
    assert get_payslip_for_user(OWNER, src, "EMP-0002", "PR-2025-04")["net_pay"] == 158504.61
    assert get_payslip_for_user(HR, src, "EMP-0002", "PR-2025-04")["net_pay"] == 158504.61


def test_inactive_user_refused_and_missing_payslip():
    assert not can_view_payslip({**OWNER, "is_active": "N"}, "EMP-0002")
    assert not can_view_payslip(None, "EMP-0002")
    with pytest.raises(LookupError):
        get_payslip_for_user(HR, src, "EMP-0002", "PR-1999-01")


def test_stranger_cannot_even_probe_for_existence():
    with pytest.raises(PermissionError):      # not LookupError: permission is checked first
        get_payslip_for_user(STRANGER, src, "EMP-0002", "PR-1999-01")


def test_pdf_is_generated():
    pdf = render_pdf(build_payslip(src, "EMP-0002", "PR-2025-04"))
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000
