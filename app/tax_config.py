"""Task 14: tax slabs, tax parameters and statutory rates stored as DATA, with a change log.
The payroll engine reads these tables (through load_rules), so changing a rule changes the next calculation without a code release.
Past months are safe: processed runs keep their stored rows and ledger entries, and every run records the rules version it used."""
from datetime import datetime
from decimal import Decimal as D
import pandas as pd
from app.books_db import dec


class RuleError(Exception):
    pass


def _fmt(x):
    """CSV value -> clean text: 200.0 -> '200', 0.75 -> '0.75', NaN -> None."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    if isinstance(x, (int, float)):
        return format(D(repr(x)).normalize(), "f")
    return str(x)


def seed_rules(conn, data_dir="data") -> bool:
    """Load the three rule CSVs into the database the first time. Returns True if it loaded anything."""
    if conn.execute("SELECT COUNT(*) n FROM tax_slabs").fetchone()["n"]:
        return False
    for r in pd.read_csv(f"{data_dir}/tax_slabs.csv").itertuples():
        conn.execute("INSERT INTO tax_slabs VALUES (?,?,?,?,?,?,?,?)", (r.slab_id, r.regime, r.financial_year, _fmt(r.income_from),
                     _fmt(r.income_to), _fmt(r.rate_percent), _fmt(r.effective_from), _fmt(r.note)))
    for r in pd.read_csv(f"{data_dir}/tax_parameters.csv").itertuples():
        conn.execute("INSERT INTO tax_parameters VALUES (?,?,?)", (r.parameter, _fmt(r.value), _fmt(r.note)))
    for r in pd.read_csv(f"{data_dir}/statutory_rates.csv").itertuples():
        conn.execute("INSERT INTO statutory_rates VALUES (?,?,?,?,?)", (r.parameter, _fmt(r.value), _fmt(r.unit), _fmt(r.note), _fmt(r.effective_from)))
    conn.commit()
    return True


def load_rules(conn, regime="NEW"):
    """-> (rates, params, slabs) in the same shape the payroll engine already uses, or None if the tables are empty."""
    if not conn.execute("SELECT COUNT(*) n FROM tax_slabs").fetchone()["n"]:
        return None
    rates = {r["parameter"]: dec(r["value"]) for r in conn.execute("SELECT * FROM statutory_rates")}
    params = {r["parameter"]: dec(r["value"]) for r in conn.execute("SELECT * FROM tax_parameters")}
    slabs = {}
    for r in conn.execute("SELECT * FROM tax_slabs WHERE regime=? ORDER BY financial_year, CAST(income_from AS REAL)", (regime,)):
        slabs.setdefault(r["financial_year"], []).append(
            (dec(r["income_from"]), None if r["income_to"] in (None, "") else dec(r["income_to"]), dec(r["rate_percent"]) / 100))
    return rates, params, slabs


def rules_version(conn) -> int:
    """Goes up by one on every rule change. Each payroll run stores the version it was calculated with."""
    return conn.execute("SELECT COUNT(*) n FROM rule_changes").fetchone()["n"]


def _log(conn, by, rule_type, key, field, old, new, reason):
    conn.execute("INSERT INTO rule_changes(changed_at, changed_by, rule_type, rule_key, field, old_value, new_value, reason) VALUES (?,?,?,?,?,?,?,?)",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), by, rule_type, key, field, old, new, reason))


def _need(by, reason):
    if not by:
        raise RuleError("A rule change must record who made it")
    if not reason or not reason.strip():
        raise RuleError("A rule change needs a reason")


def list_slabs(conn, financial_year=None):
    sql, args = "SELECT * FROM tax_slabs", ()
    if financial_year:
        sql, args = sql + " WHERE financial_year=?", (financial_year,)
    return [dict(r) for r in conn.execute(sql + " ORDER BY financial_year, CAST(income_from AS REAL)", args)]


def update_slab(conn, slab_id, changed_by, reason, rate_percent=None, income_to=None) -> dict:
    """Change one slab's rate and/or its upper limit (the next slab's start moves with it, so slabs stay joined)."""
    _need(changed_by, reason)
    if rate_percent is None and income_to is None:
        raise RuleError("Nothing to change: give rate_percent and/or income_to")
    slab = conn.execute("SELECT * FROM tax_slabs WHERE slab_id=?", (slab_id,)).fetchone()
    if slab is None:
        raise RuleError(f"Slab {slab_id} not found")
    peers = conn.execute("SELECT * FROM tax_slabs WHERE financial_year=? AND regime=? ORDER BY CAST(income_from AS REAL)",
                         (slab["financial_year"], slab["regime"])).fetchall()
    idx = [p["slab_id"] for p in peers].index(slab_id)
    try:
        if rate_percent is not None:
            new = dec(rate_percent)
            if not (D(0) <= new <= D(100)):
                raise RuleError("A tax rate must be between 0 and 100 percent")
            _log(conn, changed_by, "tax_slab", slab_id, "rate_percent", slab["rate_percent"], str(new), reason)
            conn.execute("UPDATE tax_slabs SET rate_percent=? WHERE slab_id=?", (str(new), slab_id))
        if income_to is not None:
            if idx == len(peers) - 1:
                raise RuleError("The top slab has no upper limit to change")
            nxt = peers[idx + 1]
            new = dec(income_to)
            lo = dec(slab["income_from"])
            hi = None if nxt["income_to"] in (None, "") else dec(nxt["income_to"])
            if new <= lo or (hi is not None and new >= hi):
                raise RuleError(f"The new limit must be between {lo} and {hi if hi is not None else 'infinity'}")
            _log(conn, changed_by, "tax_slab", slab_id, "income_to", slab["income_to"], str(new), reason)
            _log(conn, changed_by, "tax_slab", nxt["slab_id"], "income_from", nxt["income_from"], str(new), reason)
            conn.execute("UPDATE tax_slabs SET income_to=? WHERE slab_id=?", (str(new), slab_id))
            conn.execute("UPDATE tax_slabs SET income_from=? WHERE slab_id=?", (str(new), nxt["slab_id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return dict(conn.execute("SELECT * FROM tax_slabs WHERE slab_id=?", (slab_id,)).fetchone())


def _update_value(conn, table, rule_type, name, value, changed_by, reason, upper=None):
    _need(changed_by, reason)
    row = conn.execute(f"SELECT * FROM {table} WHERE parameter=?", (name,)).fetchone()
    if row is None:
        raise RuleError(f"{rule_type} {name} not found")
    new = dec(value)
    if new < 0 or (upper is not None and new > upper):
        raise RuleError(f"{name} must be between 0 and {upper if upper is not None else 'a larger number'}")
    _log(conn, changed_by, rule_type, name, "value", row["value"], str(new), reason)
    conn.execute(f"UPDATE {table} SET value=? WHERE parameter=?", (str(new), name))
    conn.commit()
    return dict(conn.execute(f"SELECT * FROM {table} WHERE parameter=?", (name,)).fetchone())


def update_parameter(conn, name, value, changed_by, reason):
    return _update_value(conn, "tax_parameters", "tax_parameter", name, value, changed_by, reason,
                         upper=D(100) if name.endswith("_percent") else None)


def update_statutory_rate(conn, name, value, changed_by, reason):
    return _update_value(conn, "statutory_rates", "statutory_rate", name, value, changed_by, reason,
                         upper=D(100) if name.endswith("_RATE") else None)


def list_changes(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM rule_changes ORDER BY change_id")]
