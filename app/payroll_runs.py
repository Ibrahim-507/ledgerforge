"""Task 12: payroll runs that post to the ledger automatically, safely and ONLY ONCE.

Status flow:   DRAFT -> PROCESSED -> APPROVED (posted to the ledger) -> PAID        APPROVED -> REVERSED
  create   one run per month, guarded by an idempotency key  ('payroll:2025-04:ZNT')
  process  runs the Task 7 engine for every employee employed in the month and stores the payslip rows
  approve  a DIFFERENT person approves; posts ONE journal entry built from the stored rows; id stored on the run
  pay      posts the salary payment (DR 2100 salaries payable, CR 1001 bank)
  reverse  cancels an approved run by posting the mirror entry; the month can then be run again as '-R1'

Rule for a failed ledger post ("think for yourself"): the post, the journal id and the status change happen in ONE
transaction. If any part fails, everything rolls back: the run stays PROCESSED, no half entry exists, the error is
recorded on the run, and approving again is safe. A repeat call on an already approved run changes nothing."""
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal as D
import pandas as pd
from app.books_db import dec, fmt, next_id
from app.ledger import LedgerError, create_journal_entry, reverse_entry, _to_date

CALC_VERSION = "ledgerforge-engine-1.0"
SALARIES_PAYABLE, BANK = 2100, 1001


class RunError(Exception):
    pass


class RunSeparationError(RunError):
    """The person who ran payroll tried to approve it."""


def month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def default_pay_date(period_end: date) -> date:
    """Next day after the period, moved forward past weekends (matches the official pay dates)."""
    d = period_end + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _run(conn, run_id):
    r = conn.execute("SELECT * FROM payroll_runs WHERE run_id=?", (run_id,)).fetchone()
    if r is None:
        raise RunError(f"Payroll run {run_id} not found")
    return r


# ---------------- create ---------------------------------------------------------------------------
def create_run(conn, period_start, run_by, company="ZNT") -> str:
    """Create the run for a month. Calling it again for the same month (a double click) returns the SAME run.
    A month whose run was REVERSED can be run again: it gets the next suffix (-R1, -R2 ...)."""
    start = _to_date(period_start).replace(day=1)
    end = month_end(start)
    base = f"payroll:{start:%Y-%m}:{company}"
    rows = conn.execute("SELECT * FROM payroll_runs WHERE idempotency_key=? OR idempotency_key LIKE ? ORDER BY created_at, run_id",
                        (base, base + ":R%")).fetchall()
    live = [r for r in rows if r["status"] != "REVERSED"]
    if live:
        return live[0]["run_id"]
    n = len(rows)
    key, run_id = (base, f"PR-{start:%Y-%m}") if n == 0 else (f"{base}:R{n}", f"PR-{start:%Y-%m}-R{n}")
    conn.execute("INSERT INTO payroll_runs(run_id,period_start,period_end,pay_date,status,run_by,created_at,idempotency_key,calculation_version) "
                 "VALUES (?,?,?,?,?,?,?,?,?)",
                 (run_id, start.isoformat(), end.isoformat(), default_pay_date(end).isoformat(), "DRAFT", run_by,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S"), key, CALC_VERSION))
    conn.commit()
    return run_id


# ---------------- process ---------------------------------------------------------------------------
def _roster(source, start: date, end: date) -> set:
    """Employees employed at any time in the month (hire date on/before month end, exit on/after month start)."""
    e = pd.read_csv(f"{source.dir}/employees.csv", parse_dates=["hire_date", "exit_date"])
    ok = (e.hire_date <= pd.Timestamp(end)) & (e.exit_date.isna() | (e.exit_date >= pd.Timestamp(start)))
    return set(e[ok].employee_id)


def process_run(conn, source, run_id) -> dict:
    """DRAFT -> PROCESSED: run the engine for every employee and store the rows. All or nothing."""
    run = _run(conn, run_id)
    if run["status"] in ("PROCESSED", "APPROVED", "PAID"):      # repeat call: never rewrite stored payroll rows
        return {"run_id": run_id, "status": run["status"], "already": True}
    if run["status"] != "DRAFT":
        raise RunError(f"Only a DRAFT run can be processed; {run_id} is {run['status']}")
    start, end = _to_date(run["period_start"]), _to_date(run["period_end"])
    ctx = source.items[(source.items.period_start == pd.Timestamp(start))].set_index("employee_id")
    roster = _roster(source, start, end)
    missing = sorted(roster - set(ctx.index))
    if missing:
        raise RunError(f"No pay inputs (department, variable pay ...) for {len(missing)} employee(s), e.g. {missing[:3]}")
    results = []
    for emp in sorted(roster):                       # compute everything first: one failure writes nothing
        r = ctx.loc[emp]
        row = type("Row", (), {**r.to_dict(), "employee_id": emp})()
        results.append((row, source.calculate_row(row)))
    tot = {k: D("0") for k in ("gross", "ded", "net", "er", "cost")}
    try:
        for r, p in results:
            conn.execute("INSERT INTO payroll_items VALUES (" + ",".join("?" * 34) + ")", (
                next_id(conn, "payroll_items", "payroll_item_id", "PI-", 6), run_id, r.employee_id, start.isoformat(),
                end.isoformat(), r.department_id, r.role_id, int(r.calendar_days), int(r.days_employed), float(r.lop_days),
                float(r.payable_days), fmt(p.monthly_fixed_gross), fmt(p.basic), fmt(p.hra), fmt(p.conveyance), fmt(p.medical),
                fmt(p.special_allowance), fmt(p.earned_fixed_pay), float(p.overtime_hours_paid), fmt(p.overtime_pay),
                fmt(p.variable_pay), r.variable_pay_type if isinstance(r.variable_pay_type, str) else None, fmt(p.gross_pay),
                fmt(p.pf_employee), fmt(p.esi_employee), fmt(p.professional_tax), fmt(p.tds), fmt(p.other_deductions),
                fmt(p.total_deductions), fmt(p.net_pay), fmt(p.pf_employer), fmt(p.esi_employer), fmt(p.employer_cost),
                r.calculation_note if isinstance(getattr(r, "calculation_note", None), str) else None))
            tot["gross"] += p.gross_pay; tot["ded"] += p.total_deductions; tot["net"] += p.net_pay
            tot["er"] += p.pf_employer + p.esi_employer; tot["cost"] += p.employer_cost
        conn.execute("UPDATE payroll_runs SET status='PROCESSED', employees_paid=?, total_gross=?, total_deductions=?, total_net=?, "
                     "total_employer_contributions=?, total_employer_cost=?, error_message=NULL WHERE run_id=?",
                     (len(results), fmt(tot["gross"]), fmt(tot["ded"]), fmt(tot["net"]), fmt(tot["er"]), fmt(tot["cost"]), run_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"run_id": run_id, "status": "PROCESSED", "employees": len(results), "total_net": fmt(tot["net"])}


# ---------------- approve = post to the ledger -----------------------------------------------------------
def _posting_lines(conn, run_id):
    """Journal lines built from the STORED payroll rows (the numbers that were processed and approved)."""
    lines = []
    q = ("SELECT department_id, dsum(earned_fixed_pay) a, dsum(overtime_pay) b, dsum(variable_pay) c, dsum(pf_employer) d, "
         "dsum(esi_employer) e FROM payroll_items WHERE run_id=? GROUP BY department_id ORDER BY department_id")
    for r in conn.execute(q, (run_id,)):
        for code, name, col in ((5001, "Salaries & Wages", "a"), (5002, "Overtime Expense", "b"), (5003, "Incentives & Bonus", "c"),
                                (5004, "Employer PF Contribution", "d"), (5005, "Employer ESI Contribution", "e")):
            if dec(r[col]) > 0:
                lines.append({"account_code": code, "debit": dec(r[col]), "cost_center_department_id": r["department_id"],
                              "line_description": f"{name} - {r['department_id']}"})
    t = conn.execute("SELECT dsum(net_pay) net, dsum(pf_employee) pfe, dsum(pf_employer) pfr, dsum(esi_employee) ese, "
                     "dsum(esi_employer) esr, dsum(tds) tds, dsum(professional_tax) pt, dsum(other_deductions) oth "
                     "FROM payroll_items WHERE run_id=?", (run_id,)).fetchone()
    for code, amt, name in ((2100, dec(t["net"]), "Net salaries payable"), (2110, dec(t["pfe"]) + dec(t["pfr"]), "PF payable (employee + employer)"),
                            (2120, dec(t["ese"]) + dec(t["esr"]), "ESI payable (employee + employer)"),
                            (2130, dec(t["tds"]), "TDS on salary payable"), (2140, dec(t["pt"]), "Professional tax payable"),
                            (1300, dec(t["oth"]), "Recovery of employee advances")):
        if amt > 0:
            lines.append({"account_code": code, "credit": amt, "line_description": name})
    return lines


def approve_run(conn, run_id, approved_by) -> str:
    """PROCESSED -> APPROVED and post ONE journal entry. Safe to call twice: the second call returns the same entry."""
    run = _run(conn, run_id)
    if run["status"] in ("APPROVED", "PAID") and run["journal_entry_id"]:
        return run["journal_entry_id"]                           # double click: nothing posted again
    if run["status"] != "PROCESSED":
        raise RunError(f"Only a PROCESSED run can be approved; {run_id} is {run['status']}")
    if not approved_by:
        raise RunError("An approval must record who approved it")
    if approved_by == run["run_by"]:
        raise RunSeparationError(f"{approved_by} ran payroll {run_id} and cannot also approve it")
    try:
        je = create_journal_entry(conn, run["period_end"], f"Payroll posting {run_id}", _posting_lines(conn, run_id),
                                  source_type="PAYROLL_RUN", source_id=run_id, created_by=approved_by, commit=False)
        conn.execute("UPDATE payroll_runs SET status='APPROVED', approved_by=?, approved_at=?, journal_entry_id=?, error_message=NULL "
                     "WHERE run_id=?", (approved_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), je, run_id))
        conn.commit()
    except Exception as exc:                                    # roll EVERYTHING back, then record why
        conn.rollback()
        conn.execute("UPDATE payroll_runs SET error_message=? WHERE run_id=?", (str(exc)[:500], run_id))
        conn.commit()
        raise
    return je


# ---------------- pay ---------------------------------------------------------------------------------------
def pay_run(conn, run_id, paid_by=None, pay_date=None) -> str:
    """APPROVED -> PAID: salaries leave the bank. DR 2100 / CR 1001 for total net pay."""
    run = _run(conn, run_id)
    if run["status"] == "PAID":
        return run["payment_entry_id"]
    if run["status"] != "APPROVED":
        raise RunError(f"{run_id} must be approved before it can be paid (status: {run['status']})")
    d = _to_date(pay_date or run["pay_date"])
    net = dec(run["total_net"])
    try:
        je = create_journal_entry(conn, d, f"Salary payment {run_id}",
                                  [{"account_code": SALARIES_PAYABLE, "debit": net, "line_description": "Net salaries paid"},
                                   {"account_code": BANK, "credit": net, "line_description": "Bank - salary payout"}],
                                  source_type="SALARY_PAYMENT", source_id=run_id, created_by=paid_by, commit=False)
        conn.execute("UPDATE payroll_runs SET status='PAID', pay_date=?, payment_entry_id=? WHERE run_id=?", (d.isoformat(), je, run_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return je


# ---------------- reverse (the challenge) ---------------------------------------------------------------------------
def reverse_run(conn, run_id, reverse_date, reason, reversed_by=None) -> str:
    """Cancel an APPROVED run: post the mirror image of its journal entry and mark the run REVERSED.
    A PAID run is refused (money already left the bank: that needs a separate recovery process)."""
    run = _run(conn, run_id)
    if run["status"] == "REVERSED":
        raise RunError(f"{run_id} is already reversed")
    if run["status"] == "PAID":
        raise RunError(f"{run_id} is already paid: salaries have left the bank and cannot be reversed here")
    if run["status"] != "APPROVED":
        raise RunError(f"Only an APPROVED run has a posted entry to reverse; {run_id} is {run['status']}")
    if not reason:
        raise RunError("A reversal needs a reason")
    try:
        rev = reverse_entry(conn, run["journal_entry_id"], reverse_date, f"{run_id}: {reason}", reversed_by, commit=False)
        conn.execute("UPDATE payroll_runs SET status='REVERSED' WHERE run_id=?", (run_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return rev


# ---------------- all months -------------------------------------------------------------------------------------------
def months_between(first: str, last: str):
    y, m = map(int, first.split("-"))
    y2, m2 = map(int, last.split("-"))
    while (y, m) <= (y2, m2):
        yield date(y, m, 1)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def run_all_months(conn, source, first="2025-04", last="2026-09", run_by="U-0237", approver="U-0099", pay_through="2026-08"):
    """Create, process, approve (post) and pay every month. Calling it twice changes nothing."""
    out = []
    for start in months_between(first, last):
        rid = create_run(conn, start, run_by)
        process_run(conn, source, rid)
        approve_run(conn, rid, approver)
        if f"{start:%Y-%m}" <= pay_through:
            pay_run(conn, rid, approver)
        out.append(rid)
    return out
