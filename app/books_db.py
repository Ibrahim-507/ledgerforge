"""Small SQLite layer for Tasks 9-10. Money is stored as exact decimal TEXT ('1234.50')
and summed with a Decimal aggregate - never floats. Column names equal the dataset's, so
exporting a table to CSV gives a file the checker understands."""
import sqlite3
from decimal import Decimal as D, ROUND_HALF_UP

CENT = D("0.01")


def dec(x) -> D:
    return D(str(x)) if x not in (None, "") else D("0")


def fmt(d) -> str:
    return f"{D(str(d)).quantize(CENT, rounding=ROUND_HALF_UP):.2f}"


class _DSum:
    def __init__(self): self.t = D("0")
    def step(self, v):
        if v not in (None, ""): self.t += D(str(v))
    def finalize(self): return fmt(self.t)


SCHEMA = """
CREATE TABLE IF NOT EXISTS chart_of_accounts(
  account_code INTEGER PRIMARY KEY, account_name TEXT NOT NULL, account_type TEXT NOT NULL,
  normal_balance TEXT NOT NULL, parent_code INTEGER, is_group TEXT NOT NULL,
  statement TEXT, is_active TEXT NOT NULL DEFAULT 'Y');

CREATE TABLE IF NOT EXISTS journal_entries(
  entry_id TEXT PRIMARY KEY, entry_date TEXT NOT NULL, posting_period TEXT NOT NULL,
  financial_year TEXT NOT NULL, description TEXT NOT NULL, source_type TEXT NOT NULL,
  source_id TEXT, status TEXT NOT NULL DEFAULT 'POSTED', total_debit TEXT NOT NULL,
  total_credit TEXT NOT NULL, reversal_of_source_id TEXT, created_by TEXT, created_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS ux_je_source ON journal_entries(source_type, source_id)
  WHERE source_type IN ('PAYROLL_RUN','INVOICE','INVOICE_PAYMENT','REVERSAL');

CREATE TABLE IF NOT EXISTS journal_lines(
  line_id TEXT PRIMARY KEY, entry_id TEXT NOT NULL REFERENCES journal_entries(entry_id),
  line_no INTEGER NOT NULL, account_code INTEGER NOT NULL REFERENCES chart_of_accounts(account_code),
  debit TEXT NOT NULL DEFAULT '0.00', credit TEXT NOT NULL DEFAULT '0.00',
  cost_center_department_id TEXT, line_description TEXT);
CREATE INDEX IF NOT EXISTS ix_jl_account ON journal_lines(account_code);

-- Posted entries are IMMUTABLE at database level: no UPDATE, no DELETE. Fix by reversing.
CREATE TRIGGER IF NOT EXISTS trg_je_no_update BEFORE UPDATE ON journal_entries
  BEGIN SELECT RAISE(ABORT,'posted journal entries are read-only: post a reversing entry'); END;
CREATE TRIGGER IF NOT EXISTS trg_je_no_delete BEFORE DELETE ON journal_entries
  BEGIN SELECT RAISE(ABORT,'posted journal entries cannot be deleted: post a reversing entry'); END;
CREATE TRIGGER IF NOT EXISTS trg_jl_no_update BEFORE UPDATE ON journal_lines
  BEGIN SELECT RAISE(ABORT,'journal lines are read-only: post a reversing entry'); END;
CREATE TRIGGER IF NOT EXISTS trg_jl_no_delete BEFORE DELETE ON journal_lines
  BEGIN SELECT RAISE(ABORT,'journal lines cannot be deleted: post a reversing entry'); END;

CREATE TABLE IF NOT EXISTS clients(
  client_id TEXT PRIMARY KEY, client_name TEXT NOT NULL, industry TEXT, city TEXT,
  state_or_region TEXT, country TEXT, client_type TEXT, gst_registration TEXT,
  payment_terms_days INTEGER NOT NULL DEFAULT 30, payment_behaviour TEXT,
  primary_service_line TEXT, contact_email TEXT, onboarded_on TEXT, is_active TEXT DEFAULT 'Y');

CREATE TABLE IF NOT EXISTS invoices(
  invoice_id TEXT PRIMARY KEY, invoice_number TEXT, client_id TEXT NOT NULL REFERENCES clients(client_id),
  invoice_date TEXT NOT NULL, due_date TEXT NOT NULL, service_line_account INTEGER, currency TEXT DEFAULT 'INR',
  subtotal TEXT NOT NULL, gst_rate_percent TEXT NOT NULL, gst_amount TEXT NOT NULL,
  total_amount TEXT NOT NULL, amount_paid TEXT NOT NULL DEFAULT '0.00', balance_due TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'DRAFT', last_payment_date TEXT, po_number TEXT,
  carried_in_from_prior_period TEXT DEFAULT 'N', created_by TEXT, created_at TEXT, ledger_entry_id TEXT);

CREATE TABLE IF NOT EXISTS invoice_items(
  invoice_item_id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
  line_no INTEGER NOT NULL, description TEXT, quantity TEXT NOT NULL, unit_price TEXT NOT NULL,
  amount TEXT NOT NULL, revenue_account INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS invoice_payments(
  payment_id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
  payment_date TEXT NOT NULL, amount TEXT NOT NULL, payment_mode TEXT, reference_no TEXT,
  received_by TEXT, ledger_entry_id TEXT);
"""


def connect(path=":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_aggregate("dsum", 1, _DSum)
    conn.executescript(SCHEMA)
    return conn


def next_id(conn, table, column, prefix, width) -> str:
    row = conn.execute(f"SELECT MAX({column}) m FROM {table} WHERE {column} LIKE ?", (prefix + "%",)).fetchone()
    n = int(row["m"][len(prefix):]) + 1 if row["m"] else 1
    return f"{prefix}{n:0{width}d}"
