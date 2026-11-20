from decimal import Decimal as D
from pathlib import Path
import pandas as pd
import pytest
from app.books_db import connect
from app.ledger import load_chart
from app.payroll_data import PayrollSource
from app.payroll_runs import approve_run, create_run, process_run, run_all_months
from app.statutory_reports import ReportError, amount_due, export_csv, monthly_summary, statutory_report
from app.tax_config import seed_rules

DATA = Path(__file__).resolve().parent.parent / "data"
src = PayrollSource(str(DATA))
official = pd.read_csv(DATA / "payroll_items.csv")


def full_books():
    c = connect()
    load_chart(c, DATA / "chart_of_accounts.csv")
    seed_rules(c, str(DATA))
    run_all_months(c, src)
    return c


def test_report_totals_equal_the_payroll_sums_for_all_18_months():
    c = full_books()
    g = official.groupby("run_id")[["pf_employee", "esi_employee", "tds", "professional_tax"]].sum()
    summary = monthly_summary(c)
    assert len(summary) == 18
    for line in summary:
        o = g.loc[line["run_id"]]
        assert abs(float(statutory_report(c, line["run_id"], "pf")["totals"]["pf_employee"]) - o.pf_employee) < 0.005
        assert abs(float(statutory_report(c, line["run_id"], "esi")["totals"]["esi_employee"]) - o.esi_employee) < 0.005
        assert abs(float(line["tds"]) - o.tds) < 0.005 and abs(float(line["pt"]) - o.professional_tax) < 0.005


def test_every_month_equals_what_the_ledger_owes_for_pf_esi_tds_and_pt():
    c = full_books()
    for line in monthly_summary(c):
        assert line["ok"], line
        assert {line["pf_diff"], line["esi_diff"], line["tds_diff"], line["pt_diff"]} == {"0.00"}


def test_report_contents_and_employer_share():
    c = full_books()
    pf = statutory_report(c, "PR-2025-04", "pf")
    assert pf["employees"] == 358 and pf["totals"]["pf_employee"] == pf["totals"]["pf_employer"] == "618963.94"
    assert D(pf["totals"]["total_pf"]) == amount_due(pf) == D("1237927.88")
    esi = statutory_report(c, "PR-2025-04", "esi")
    assert D(esi["totals"]["total_esi"]) == D(esi["totals"]["esi_employee"]) + D(esi["totals"]["esi_employer"])
    tds = statutory_report(c, "PR-2025-04", "tds")
    assert tds["rows"][0].keys() >= {"employee_id", "tds"} and all(D(r["tds"]) > 0 for r in tds["rows"])


def test_unknown_report_or_unprocessed_run_is_refused(tmp_path=None):
    c = connect()
    load_chart(c, DATA / "chart_of_accounts.csv")
    with pytest.raises(ReportError, match="not found"):
        statutory_report(c, "PR-2025-04", "pf")
    rid = create_run(c, "2025-04-01", "U-0237")
    with pytest.raises(ReportError, match="not been processed"):
        statutory_report(c, rid, "pf")
    process_run(c, src, rid)
    with pytest.raises(ReportError, match="Unknown report"):
        statutory_report(c, rid, "gst")


def test_csv_export_has_a_total_line(tmp_path):
    c = full_books()
    path = export_csv(statutory_report(c, "PR-2025-04", "pf"), tmp_path / "pf.csv")
    lines = Path(path).read_text().strip().splitlines()
    assert lines[0].startswith("employee_id") and lines[-1].startswith("TOTAL") and "1237927.88" not in lines[-1]
    assert "618963.94" in lines[-1]
