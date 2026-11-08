"""Task 14: monthly PF, ESI, TDS and professional-tax reports, built from the STORED payroll rows of a run,
and checked against the payroll sums and against the amounts the ledger holds as 'payable' for that run."""
import csv
from decimal import Decimal as D
from app.books_db import dec, fmt

KINDS = {
    "pf": {"title": "Provident Fund (PF)", "account": 2110, "cols": ["basic", "pf_employee", "pf_employer"], "where": "(pf_employee != '0.00' OR pf_employer != '0.00')"},
    "esi": {"title": "Employee State Insurance (ESI)", "account": 2120, "cols": ["gross_pay", "esi_employee", "esi_employer"], "where": "(esi_employee != '0.00' OR esi_employer != '0.00')"},
    "tds": {"title": "Income tax deducted at source (TDS)", "account": 2130, "cols": ["monthly_fixed_gross", "variable_pay", "tds"], "where": "tds != '0.00'"},
    "pt": {"title": "Professional tax (PT)", "account": 2140, "cols": ["gross_pay", "professional_tax"], "where": "professional_tax != '0.00'"},
}


class ReportError(Exception):
    pass


def _run(conn, run_id):
    r = conn.execute("SELECT * FROM payroll_runs WHERE run_id=?", (run_id,)).fetchone()
    if r is None:
        raise ReportError(f"Payroll run {run_id} not found")
    if r["status"] in ("DRAFT",):
        raise ReportError(f"{run_id} has not been processed yet")
    return r


def statutory_report(conn, run_id, kind) -> dict:
    """One report: a row per employee plus totals. kind = pf | esi | tds | pt."""
    if kind not in KINDS:
        raise ReportError(f"Unknown report '{kind}'. Use one of: {', '.join(KINDS)}")
    run = _run(conn, run_id)
    spec = KINDS[kind]
    cols = spec["cols"]
    rows = [dict(r) for r in conn.execute(
        f"SELECT employee_id, department_id, {', '.join(cols)} FROM payroll_items WHERE run_id=? AND {spec['where']} ORDER BY employee_id", (run_id,))]
    totals = {c: D("0") for c in cols}
    for r in rows:
        for c in cols:
            totals[c] += dec(r[c])
    if kind == "pf":
        totals["total_pf"] = totals["pf_employee"] + totals["pf_employer"]
    if kind == "esi":
        totals["total_esi"] = totals["esi_employee"] + totals["esi_employer"]
    return {"run_id": run_id, "kind": kind, "title": spec["title"], "period_start": run["period_start"], "period_end": run["period_end"],
            "employees": len(rows), "rows": rows, "totals": {k: fmt(v) for k, v in totals.items()}}


def amount_due(report) -> D:
    """What the company must remit for this report (matches the ledger payable account for the run)."""
    t = report["totals"]
    return {"pf": dec(t.get("total_pf")), "esi": dec(t.get("total_esi")), "tds": dec(t.get("tds")), "pt": dec(t.get("professional_tax"))}[report["kind"]]


def monthly_summary(conn) -> list:
    """One line per run: what to remit for PF, ESI, TDS and PT, and whether it equals the ledger and the payroll rows."""
    out = []
    for run in conn.execute("SELECT * FROM payroll_runs WHERE status IN ('PROCESSED','APPROVED','PAID') ORDER BY period_start, run_id").fetchall():
        line = {"run_id": run["run_id"], "month": run["period_start"][:7], "status": run["status"]}
        ok = True
        for kind, spec in KINDS.items():
            due = amount_due(statutory_report(conn, run["run_id"], kind))
            line[kind] = fmt(due)
            if run["journal_entry_id"]:
                led = conn.execute("SELECT dsum(credit) c FROM journal_lines WHERE entry_id=? AND account_code=?", (run["journal_entry_id"], spec["account"])).fetchone()["c"]
                line[f"{kind}_ledger"] = led
                line[f"{kind}_diff"] = fmt(due - dec(led))
                ok &= due == dec(led)
        line["ok"] = bool(ok and run["journal_entry_id"])
        out.append(line)
    return out


def export_csv(report, path):
    cols = list(report["rows"][0].keys()) if report["rows"] else ["employee_id"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in report["rows"]:
            w.writerow([r[c] for c in cols])
        w.writerow(["TOTAL", ""] + [report["totals"].get(c, "") for c in cols[2:]])
    return path
