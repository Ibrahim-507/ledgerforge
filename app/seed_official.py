"""Load the official ledger + invoicing CSVs into the SQLite schema (used to prove the checks work)."""
import pandas as pd
from app.books_db import fmt
from app.ledger import load_chart

MONEY = {"journal_entries": ["total_debit", "total_credit"], "journal_lines": ["debit", "credit"],
         "invoices": ["subtotal", "gst_amount", "total_amount", "amount_paid", "balance_due"],
         "invoice_items": ["amount"], "invoice_payments": ["amount"]}


def _insert(conn, table, df):
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
    df = df[[c for c in cols if c in df.columns]].copy()
    for c in MONEY.get(table, []):
        df[c] = df[c].map(fmt)
    df = df.astype(object).where(df.notna(), None)
    conn.executemany(f"INSERT INTO {table} ({','.join(df.columns)}) VALUES ({','.join('?' * len(df.columns))})",
                     [tuple(r) for r in df.itertuples(index=False)])


def import_official(conn, data_dir="data"):
    load_chart(conn, f"{data_dir}/chart_of_accounts.csv")
    for t in ["journal_entries", "journal_lines", "clients", "invoices", "invoice_items", "invoice_payments"]:
        _insert(conn, t, pd.read_csv(f"{data_dir}/{t}.csv"))
    conn.commit()
