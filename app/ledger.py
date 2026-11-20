"""Task 9: double-entry ledger core.
Rules: (1) debits must equal credits, (2) posted entries are never edited or deleted -
you post a REVERSING entry, (3) balances are computed from lines, as of a date."""
from datetime import date, datetime
from decimal import Decimal as D
import pandas as pd
from app.books_db import dec, fmt, next_id

ZERO = D("0")


class LedgerError(Exception):
    pass


def financial_year(d: date) -> str:
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def _to_date(x) -> date:
    return x if isinstance(x, date) else datetime.strptime(str(x)[:10], "%Y-%m-%d").date()


def load_chart(conn, csv_path):
    df = pd.read_csv(csv_path)
    for r in df.itertuples():
        conn.execute("INSERT OR REPLACE INTO chart_of_accounts VALUES (?,?,?,?,?,?,?,?)",
                     (int(r.account_code), r.account_name, r.account_type, r.normal_balance,
                      None if pd.isna(r.parent_code) else int(r.parent_code), r.is_group, r.statement, r.is_active))
    conn.commit()


def _clean_lines(conn, lines):
    """Validate lines; return normalised list of dicts with Decimal debit/credit."""
    if not lines or len(lines) < 2:
        raise LedgerError("A journal entry needs at least two lines")
    out = []
    for i, ln in enumerate(lines, 1):
        dr, cr = dec(ln.get("debit", 0)), dec(ln.get("credit", 0))
        if dr != dr.quantize(D("0.01")) or cr != cr.quantize(D("0.01")):
            raise LedgerError(f"Line {i}: amounts must have at most 2 decimals")
        if dr < 0 or cr < 0:
            raise LedgerError(f"Line {i}: debit and credit cannot be negative")
        if (dr > 0) == (cr > 0):
            raise LedgerError(f"Line {i}: a line must have a debit OR a credit (exactly one, above zero)")
        acc = conn.execute("SELECT * FROM chart_of_accounts WHERE account_code=?", (ln["account_code"],)).fetchone()
        if acc is None:
            raise LedgerError(f"Line {i}: account {ln['account_code']} does not exist")
        if acc["is_group"] == "Y":
            raise LedgerError(f"Line {i}: account {acc['account_code']} ({acc['account_name']}) is a heading; post to a detail account")
        if acc["is_active"] != "Y":
            raise LedgerError(f"Line {i}: account {acc['account_code']} is inactive")
        out.append({"account_code": int(ln["account_code"]), "debit": dr, "credit": cr,
                    "cost_center_department_id": ln.get("cost_center_department_id"),
                    "line_description": ln.get("line_description")})
    return out


def create_journal_entry(conn, entry_date, description, lines, *, source_type="MANUAL", source_id=None,
                         created_by=None, reversal_of_source_id=None, commit=True) -> str:
    """Post one entry. Refuses it (and writes nothing) when debits != credits."""
    d = _to_date(entry_date)
    clean = _clean_lines(conn, lines)
    td = sum((l["debit"] for l in clean), ZERO)
    tc = sum((l["credit"] for l in clean), ZERO)
    if td != tc:
        raise LedgerError(f"Entry is not balanced: total debits {fmt(td)} != total credits {fmt(tc)} "
                          f"(difference {fmt(abs(td - tc))})")
    try:
        entry_id = next_id(conn, "journal_entries", "entry_id", "JE-", 6)
        conn.execute("INSERT INTO journal_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (entry_id, d.isoformat(), d.strftime("%Y-%m"), financial_year(d), description, source_type,
                      source_id, "POSTED", fmt(td), fmt(tc), reversal_of_source_id, created_by,
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        n0 = conn.execute("SELECT COUNT(*) c FROM journal_lines").fetchone()["c"]
        for no, l in enumerate(clean, 1):
            conn.execute("INSERT INTO journal_lines VALUES (?,?,?,?,?,?,?,?)",
                         (f"JL-{n0 + no:06d}", entry_id, no, l["account_code"], fmt(l["debit"]), fmt(l["credit"]),
                          l["cost_center_department_id"], l["line_description"]))
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        if "UNIQUE" in str(e):
            raise LedgerError(f"{source_type} {source_id} is already posted") from e
        raise
    return entry_id


def update_entry(conn, entry_id, **changes):
    """Editing a posted entry is not allowed. Always refuses and says what to do instead."""
    raise LedgerError(f"{entry_id} is posted and read-only. Post a reversing entry with reverse_entry() "
                      f"and then post the corrected entry.")


def reverse_entry(conn, entry_id, entry_date, reason="", created_by=None, commit=True) -> str:
    """Correct a posted entry by posting its mirror image (debits and credits swapped)."""
    e = conn.execute("SELECT * FROM journal_entries WHERE entry_id=?", (entry_id,)).fetchone()
    if e is None:
        raise LedgerError(f"Entry {entry_id} not found")
    if e["source_type"] == "REVERSAL":
        raise LedgerError("A reversal cannot itself be reversed; post a new entry instead")
    lines = conn.execute("SELECT * FROM journal_lines WHERE entry_id=? ORDER BY line_no", (entry_id,)).fetchall()
    mirror = [{"account_code": l["account_code"], "debit": l["credit"], "credit": l["debit"],
               "cost_center_department_id": l["cost_center_department_id"],
               "line_description": f"Reversal: {l['line_description'] or ''}".strip()} for l in lines]
    return create_journal_entry(conn, entry_date, f"Reversal of {entry_id}: {reason}".strip(": "), mirror,
                                source_type="REVERSAL", source_id=f"REV-{entry_id}", created_by=created_by,
                                reversal_of_source_id=e["source_id"], commit=commit)


def account_balance(conn, account_code, as_of=None, include_children=True) -> D:
    """Balance on a date, shown in the account's normal direction (assets/expenses: debit-credit;
    liabilities/equity/income: credit-debit). Headings add up their detail accounts."""
    acc = conn.execute("SELECT * FROM chart_of_accounts WHERE account_code=?", (account_code,)).fetchone()
    if acc is None:
        raise LedgerError(f"Account {account_code} does not exist")
    codes = [account_code]
    if include_children and acc["is_group"] == "Y":
        codes = [r["account_code"] for r in conn.execute(
            "SELECT account_code FROM chart_of_accounts WHERE parent_code=?", (account_code,))]
    q = ",".join("?" * len(codes))
    sql = (f"SELECT dsum(l.debit) d, dsum(l.credit) c FROM journal_lines l JOIN journal_entries e "
           f"ON e.entry_id=l.entry_id WHERE l.account_code IN ({q})")
    args = list(codes)
    if as_of is not None:
        sql += " AND e.entry_date <= ?"
        args.append(_to_date(as_of).isoformat())
    r = conn.execute(sql, args).fetchone()
    net = dec(r["d"]) - dec(r["c"])
    return net if acc["normal_balance"] == "DEBIT" else -net


def entry_as_table(conn, entry_id) -> str:
    """Printable journal entry (evidence for the report)."""
    e = conn.execute("SELECT * FROM journal_entries WHERE entry_id=?", (entry_id,)).fetchone()
    ls = conn.execute("SELECT l.*, a.account_name FROM journal_lines l JOIN chart_of_accounts a "
                      "ON a.account_code=l.account_code WHERE entry_id=? ORDER BY line_no", (entry_id,)).fetchall()
    w = f"{entry_id} | {e['entry_date']} | {e['description']}\n"
    w += f"{'Acct':<6}{'Account name':<34}{'Debit':>16}{'Credit':>16}\n" + "-" * 72 + "\n"
    for l in ls[:30]:
        w += f"{l['account_code']:<6}{l['account_name'][:33]:<34}{l['debit']:>16}{l['credit']:>16}\n"
    if len(ls) > 30:
        w += f"... {len(ls) - 30} more lines\n"
    w += "-" * 72 + f"\n{'TOTAL':<40}{e['total_debit']:>16}{e['total_credit']:>16}\n"
    return w
