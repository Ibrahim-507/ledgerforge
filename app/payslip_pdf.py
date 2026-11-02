"""Draw a payslip as a PDF with ReportLab (pure Python, works on Windows)."""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

COMPANY_NAME = "Zenith Nova"   # change to your company name


def render_payslip_pdf(p: dict) -> bytes:
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=18, spaceAfter=2)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    normal = styles["Normal"]

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Payslip {p['employee_id']} {p['run_id']}")
    story = [
        Paragraph(COMPANY_NAME, title),
        Paragraph(f"Payslip for {p['period_start']} to {p['period_end']}", small),
        Spacer(1, 6 * mm),
    ]

    days = p["days"]
    info = [
        ["Employee", p["employee_name"] or p["employee_id"], "Employee ID", p["employee_id"]],
        ["Department", p["department_id"] or "-", "Role", p["role_id"] or "-"],
        ["Pay run", p["run_id"], "Pay date", p["pay_date"] or "-"],
        ["Days in month", str(days["calendar_days"]), "Loss of pay days", days["loss_of_pay_days"]],
    ]
    info_table = Table(info, colWidths=[30 * mm, 55 * mm, 32 * mm, 55 * mm])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [info_table, Spacer(1, 6 * mm)]

    earnings, deductions = p["earnings"], p["deductions"]
    rows = [["Earnings", "INR", "Deductions", "INR"]]
    for i in range(max(len(earnings), len(deductions))):
        e = earnings[i] if i < len(earnings) else None
        d = deductions[i] if i < len(deductions) else None
        rows.append([e["name"] if e else "", e["display"] if e else "",
                     d["name"] if d else "", d["display"] if d else ""])
    rows.append(["Gross pay", p["gross_pay"]["display"], "Total deductions", p["total_deductions"]["display"]])
    last = len(rows) - 1
    table = Table(rows, colWidths=[52 * mm, 33 * mm, 52 * mm, 33 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14213d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.lightgrey),
        ("FONTNAME", (0, last), (-1, last), "Helvetica-Bold"),
        ("LINEABOVE", (0, last), (-1, last), 0.8, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [table, Spacer(1, 8 * mm)]

    net = Table([[f"NET PAY    INR {p['net_pay']['display']}"]], colWidths=[170 * mm], rowHeights=[16 * mm])
    net.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e8f1e4")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 20),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [net, Spacer(1, 6 * mm),
              Paragraph("This is a computer-generated payslip. Amounts are in Indian rupees (INR).", small)]

    doc.build(story)
    return buffer.getvalue()