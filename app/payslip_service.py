"""Task 8: payslip as data (dict) and as PDF. Every figure comes from the payroll ENGINE,
never from copied payroll_items numbers, so the PDF and the books cannot disagree."""
from decimal import Decimal as D
from io import BytesIO
import pandas as pd
from app.money_format import inr

COMPANY = "Zenith Nova Technologies Pvt Ltd"


# ---------------- who may see what -------------------------------------------------------
def can_view_payslip(user: dict, employee_id: str) -> bool:
    """HR and ADMIN may see anyone's payslip; an EMPLOYEE only their own. Inactive users: nobody."""
    if not user or str(user.get("is_active", "Y")).upper() == "N":
        return False
    return user.get("role") in ("HR", "ADMIN") or user.get("employee_id") == employee_id


def get_payslip_for_user(user, source, employee_id, run_id) -> dict:
    """Permission check FIRST (a stranger must not learn whether a payslip exists)."""
    if not can_view_payslip(user, employee_id):
        raise PermissionError("You are not allowed to view this payslip")
    data = build_payslip(source, employee_id, run_id)
    if data is None:
        raise LookupError("Payslip not found")
    return data


# ---------------- data -----------------------------------------------------------------
def build_payslip(source, employee_id, run_id):
    found = source.payslip(employee_id, run_id)
    if found is None:
        return None
    r, p = found
    d = source.dir
    emp = pd.read_csv(f"{d}/employees.csv").set_index("employee_id").loc[employee_id]
    dept = pd.read_csv(f"{d}/departments.csv").set_index("department_id")
    role = pd.read_csv(f"{d}/roles.csv").set_index("role_id").loc[r.role_id]
    dept_name = dept.loc[r.department_id].iloc[0] if r.department_id in dept.index else r.department_id

    earnings = [("Basic Salary", p.basic), ("House Rent Allowance", p.hra),
                ("Conveyance Allowance", p.conveyance), ("Medical Allowance", p.medical),
                ("Special Allowance", p.special_allowance)]
    if p.overtime_pay:
        earnings.append((f"Overtime ({p.overtime_hours_paid} hrs)", p.overtime_pay))
    if p.variable_pay:
        label = r.variable_pay_type if isinstance(r.variable_pay_type, str) else "Variable Pay"
        earnings.append((label, p.variable_pay))
    deductions = [("Provident Fund", p.pf_employee), ("ESI", p.esi_employee),
                  ("Professional Tax", p.professional_tax), ("Income Tax (TDS)", p.tds)]
    if p.other_deductions:
        deductions.append(("Loan / Advance Recovery", p.other_deductions))

    return {
        "company": COMPANY,
        "employee": {"employee_id": employee_id, "name": emp.full_name, "department": dept_name,
                     "designation": role.role_title, "location": emp.work_location,
                     "date_of_joining": str(emp.hire_date)},
        "run_id": run_id,
        "period": {"start": r.period_start.date().isoformat(), "end": r.period_end.date().isoformat()},
        "days": {"calendar_days": int(r.calendar_days), "lop_days": float(r.lop_days),
                 "payable_days": float(r.payable_days)},
        "earnings": [{"name": n, "amount": float(a)} for n, a in earnings],
        "deductions": [{"name": n, "amount": float(a)} for n, a in deductions],
        "gross_pay": float(p.gross_pay), "total_deductions": float(p.total_deductions),
        "net_pay": float(p.net_pay),
        "employer_contributions": {"pf": float(p.pf_employer), "esi": float(p.esi_employer)},
    }


# ---------------- PDF ----------------------------------------------------------------------
def render_pdf(data: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=16, spaceAfter=2)
    small = ParagraphStyle("small", parent=ss["Normal"], fontSize=8, textColor=colors.grey)
    navy = colors.HexColor("#1f3a5f")
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"Payslip {data['employee']['employee_id']} {data['run_id']}")
    e, per, dy = data["employee"], data["period"], data["days"]
    story = [Paragraph(data["company"], h1),
             Paragraph(f"Payslip for {per['start']} to {per['end']}  |  Run {data['run_id']}",
                       ParagraphStyle("c", parent=ss["Normal"], alignment=1, spaceAfter=8))]

    info = [["Employee", e["name"], "Employee ID", e["employee_id"]],
            ["Designation", e["designation"], "Department", e["department"]],
            ["Location", e["location"], "Date of joining", e["date_of_joining"]],
            ["Calendar days", str(dy["calendar_days"]), "Paid days / LOP days",
             f"{dy['payable_days']:g} / {dy['lop_days']:g}"]]
    t = Table(info, colWidths=[30 * mm, 55 * mm, 38 * mm, 55 * mm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                           ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                           ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                           ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f6f9"))]))
    story += [t, Spacer(1, 6 * mm)]

    n = max(len(data["earnings"]), len(data["deductions"]))
    rows = [["EARNINGS", "Amount (INR)", "DEDUCTIONS", "Amount (INR)"]]
    for i in range(n):
        a = data["earnings"][i] if i < len(data["earnings"]) else None
        b = data["deductions"][i] if i < len(data["deductions"]) else None
        rows.append([a["name"] if a else "", inr(a["amount"]) if a else "",
                     b["name"] if b else "", inr(b["amount"]) if b else ""])
    rows.append(["Gross pay", inr(data["gross_pay"]), "Total deductions", inr(data["total_deductions"])])
    t = Table(rows, colWidths=[52 * mm, 36 * mm, 52 * mm, 36 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                           ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                           ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
                           ("GRID", (0, 0), (-1, -2), 0.25, colors.lightgrey),
                           ("BOX", (0, 0), (-1, -1), 0.5, colors.grey)]))
    story += [t, Spacer(1, 8 * mm)]

    net = Table([[Paragraph("<b>NET PAY</b>", ParagraphStyle("n1", parent=ss["Normal"], fontSize=14,
                                                              textColor=colors.white)),
                  Paragraph(f"<b>INR {inr(data['net_pay'])}</b>",
                            ParagraphStyle("n2", parent=ss["Normal"], fontSize=20, alignment=2,
                                           textColor=colors.white, leading=24))]],
                colWidths=[60 * mm, 116 * mm])
    net.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), navy), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [net, Spacer(1, 6 * mm),
              Paragraph(f"Employer contributions (not deducted from you): PF INR "
                        f"{inr(data['employer_contributions']['pf'])}, ESI INR "
                        f"{inr(data['employer_contributions']['esi'])}.", small),
              Paragraph("This is a computer-generated payslip and needs no signature. Sample training data - "
                        "fictional company.", small)]
    doc.build(story)
    return buf.getvalue()
