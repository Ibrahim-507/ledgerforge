"""Task 15: trial balance, profit and loss, balance sheet.
Totals are built from DETAIL accounts only. Heading (group) accounts such as 1000 Assets or 5000 Expenses cannot be posted to, and are
shown as subtotals of their children, so nothing is ever counted twice."""
from datetime import date, datetime
from decimal import Decimal as D
from app.books_db import dec, fmt

ZERO = D("0")


def _d(x) -> str | None:
    if x is None:
        return None
    return x.isoformat() if isinstance(x, date) else str(x)[:10]


def _accounts(conn):
    return {r["account_code"]: dict(r) for r in conn.execute("SELECT * FROM chart_of_accounts ORDER BY account_code")}


def _totals(conn, date_from=None, date_to=None):
    """{account_code: (debit, credit)} of journal lines whose entry date is in [date_from, date_to]."""
    sql, args = "SELECT l.account_code a, dsum(l.debit) d, dsum(l.credit) c FROM journal_lines l JOIN journal_entries e ON e.entry_id=l.entry_id WHERE 1=1", []
    if date_from:
        sql += " AND e.entry_date >= ?"; args.append(_d(date_from))
    if date_to:
        sql += " AND e.entry_date <= ?"; args.append(_d(date_to))
    return {r["a"]: (dec(r["d"]), dec(r["c"])) for r in conn.execute(sql + " GROUP BY l.account_code", args)}


def _before(conn, day):
    """Totals strictly before a date."""
    r = {}
    for row in conn.execute("SELECT l.account_code a, dsum(l.debit) d, dsum(l.credit) c FROM journal_lines l JOIN journal_entries e "
                            "ON e.entry_id=l.entry_id WHERE e.entry_date < ? GROUP BY l.account_code", (_d(day),)):
        r[row["a"]] = (dec(row["d"]), dec(row["c"]))
    return r


# ---------------- trial balance ----------------
def trial_balance(conn, date_from=None, date_to=None) -> dict:
    """Every account with activity or a balance: opening balance, debits and credits in the period, closing balance.
    closing_debit and closing_credit are the closing NET balance shown on its natural side, so both columns add to the same total."""
    accts = _accounts(conn)
    opening = _before(conn, date_from) if date_from else {}
    period = _totals(conn, date_from, date_to)
    rows, td, tc = [], ZERO, ZERO
    for code, a in accts.items():
        if a["is_group"] == "Y":
            continue
        od, oc = opening.get(code, (ZERO, ZERO))
        pd_, pc = period.get(code, (ZERO, ZERO))
        net_open = od - oc
        closing = net_open + pd_ - pc                         # debit minus credit
        if not (od or oc or pd_ or pc):
            continue
        cd, cc = (closing, ZERO) if closing >= 0 else (ZERO, -closing)
        td += cd; tc += cc
        rows.append({"account_code": code, "account_name": a["account_name"], "account_type": a["account_type"],
                     "opening_balance": fmt(net_open), "period_debit": fmt(pd_), "period_credit": fmt(pc),
                     "closing_debit": fmt(cd), "closing_credit": fmt(cc), "balance": fmt(closing)})
    return {"from": _d(date_from), "to": _d(date_to), "rows": rows, "total_debit": fmt(td), "total_credit": fmt(tc),
            "difference": fmt(td - tc), "balanced": td == tc}


# ---------------- profit and loss ----------------
def _section(conn, accts, type_, totals, sign):
    """Rows for one type (INCOME or EXPENSE) with heading subtotals. amount = natural-side amount for the period."""
    rows, total = [], ZERO
    groups = {}
    for code, a in accts.items():
        if a["account_type"] != type_ or a["is_group"] == "Y":
            continue
        d, c = totals.get(code, (ZERO, ZERO))
        amount = (c - d) if sign == "credit" else (d - c)
        if amount != 0:
            rows.append({"account_code": code, "account_name": a["account_name"], "parent_code": a["parent_code"], "amount": fmt(amount)})
            total += amount
            groups[a["parent_code"]] = groups.get(a["parent_code"], ZERO) + amount
    heads = [{"account_code": int(k), "account_name": accts[int(k)]["account_name"], "subtotal": fmt(v)} for k, v in groups.items() if k is not None]
    return {"rows": rows, "headings": heads, "total": fmt(total)}, total


def profit_and_loss(conn, date_from=None, date_to=None) -> dict:
    accts, totals = _accounts(conn), _totals(conn, date_from, date_to)
    income, i = _section(conn, accts, "INCOME", totals, "credit")
    expenses, e = _section(conn, accts, "EXPENSE", totals, "debit")
    return {"from": _d(date_from), "to": _d(date_to), "income": income, "expenses": expenses,
            "total_income": fmt(i), "total_expenses": fmt(e), "net_profit": fmt(i - e)}


# ---------------- balance sheet ----------------
def balance_sheet(conn, as_of=None) -> dict:
    """Assets, liabilities and equity at a date. P&L accounts are not closed to equity here, so 'current profit' (income minus
    expenses from the beginning to the date) is shown as part of equity. Assets must equal liabilities + equity + current profit."""
    accts, totals = _accounts(conn), _totals(conn, None, as_of)
    out, sums = {}, {}
    for type_, key, sign in (("ASSET", "assets", "debit"), ("LIABILITY", "liabilities", "credit"), ("EQUITY", "equity", "credit")):
        sec, total = _section(conn, accts, type_, totals, sign)       # contra accounts (e.g. 1590) come out negative automatically
        out[key], sums[key] = sec, total
    pl = profit_and_loss(conn, None, as_of)
    profit = dec(pl["net_profit"])
    lhs, rhs = sums["assets"], sums["liabilities"] + sums["equity"] + profit
    out.update({"as_of": _d(as_of), "current_profit": fmt(profit), "total_assets": fmt(lhs), "total_liabilities": fmt(sums["liabilities"]),
                "total_equity": fmt(sums["equity"]), "total_liabilities_and_equity": fmt(rhs), "difference": fmt(lhs - rhs), "balanced": lhs == rhs})
    return out


def trial_balance_csv(tb: dict, path):
    """The file for `python verify_ledgerforge.py trial-balance`."""
    import csv
    cols = ["account_code", "account_name", "account_type", "opening_balance", "period_debit", "period_credit",
            "closing_debit", "closing_credit", "balance"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols + ["debit", "credit"])
        w.writeheader()
        for r in tb["rows"]:
            w.writerow({**r, "debit": r["closing_debit"], "credit": r["closing_credit"]})
    return path
