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
  WHERE source_type IN ('PAYROLL_RUN','SALARY_PAYMENT','INVOICE','INVOICE_PAYMENT','EXPENSE','EXPENSE_PAYMENT','REVERSAL');

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
CREATE TABLE IF NOT EXISTS vendors(
  vendor_id TEXT PRIMARY KEY, vendor_name TEXT NOT NULL, primary_expense_account INTEGER,
  payment_terms_days INTEGER NOT NULL DEFAULT 30, city TEXT, gst_registration TEXT, is_active TEXT NOT NULL DEFAULT 'Y');

CREATE TABLE IF NOT EXISTS expenses(
  expense_id TEXT PRIMARY KEY, expense_date TEXT NOT NULL, category_account INTEGER NOT NULL,
  vendor_id TEXT NOT NULL REFERENCES vendors(vendor_id), bill_reference TEXT, description TEXT,
  department_id TEXT, amount_excl_gst TEXT NOT NULL, gst_rate_percent TEXT NOT NULL, gst_amount TEXT NOT NULL,
  total_amount TEXT NOT NULL, due_date TEXT, paid_date TEXT,
  status TEXT NOT NULL DEFAULT 'SUBMITTED',          -- SUBMITTED -> APPROVED -> PAID   (or REJECTED)
  payment_mode TEXT, submitted_by TEXT NOT NULL, approved_by TEXT,
  ledger_entry_id TEXT, payment_ledger_entry_id TEXT, rejected_reason TEXT);
CREATE INDEX IF NOT EXISTS ix_exp_vendor ON expenses(vendor_id, expense_date);

CREATE TABLE IF NOT EXISTS payroll_runs(
  run_id TEXT PRIMARY KEY, period_start TEXT NOT NULL, period_end TEXT NOT NULL, pay_date TEXT,
  employees_paid INTEGER, total_gross TEXT, total_deductions TEXT, total_net TEXT,
  total_employer_contributions TEXT, total_employer_cost TEXT,
  status TEXT NOT NULL DEFAULT 'DRAFT',      -- DRAFT -> PROCESSED -> APPROVED (posted) -> PAID ; APPROVED -> REVERSED
  run_by TEXT, approved_by TEXT, created_at TEXT, approved_at TEXT,
  idempotency_key TEXT NOT NULL UNIQUE,       -- the same month can never create/post twice
  journal_entry_id TEXT, calculation_version TEXT, payment_entry_id TEXT, error_message TEXT);

CREATE TABLE IF NOT EXISTS payroll_items(
  payroll_item_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES payroll_runs(run_id),
  employee_id TEXT NOT NULL, period_start TEXT, period_end TEXT, department_id TEXT, role_id TEXT,
  calendar_days INTEGER, days_employed INTEGER, lop_days REAL, payable_days REAL, monthly_fixed_gross TEXT,
  basic TEXT, hra TEXT, conveyance TEXT, medical TEXT, special_allowance TEXT, earned_fixed_pay TEXT,
  overtime_hours_paid REAL, overtime_pay TEXT, variable_pay TEXT, variable_pay_type TEXT, gross_pay TEXT,
  pf_employee TEXT, esi_employee TEXT, professional_tax TEXT, tds TEXT, other_deductions TEXT,
  total_deductions TEXT, net_pay TEXT, pf_employer TEXT, esi_employer TEXT, employer_cost TEXT, calculation_note TEXT,
  UNIQUE(run_id, employee_id));
CREATE INDEX IF NOT EXISTS ix_pi_run ON payroll_items(run_id);

CREATE TABLE IF NOT EXISTS users(
  user_id TEXT PRIMARY KEY, employee_id TEXT, username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,                  -- scrypt hash with a random salt. Never the password itself.
  role TEXT NOT NULL CHECK (role IN ('ADMIN','HR','EMPLOYEE')),
  is_active TEXT NOT NULL DEFAULT 'Y', mfa_enabled TEXT DEFAULT 'N', last_login_at TEXT, created_at TEXT);

-- Task 14: tax and statutory rules live in DATA, not code. Every change is logged in rule_changes.
CREATE TABLE IF NOT EXISTS tax_slabs(
  slab_id TEXT PRIMARY KEY, regime TEXT NOT NULL DEFAULT 'NEW', financial_year TEXT NOT NULL,
  income_from TEXT NOT NULL, income_to TEXT, rate_percent TEXT NOT NULL, effective_from TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS tax_parameters(parameter TEXT PRIMARY KEY, value TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS statutory_rates(
  parameter TEXT PRIMARY KEY, value TEXT NOT NULL, unit TEXT, note TEXT, effective_from TEXT);
CREATE TABLE IF NOT EXISTS rule_changes(
  change_id INTEGER PRIMARY KEY AUTOINCREMENT, changed_at TEXT NOT NULL, changed_by TEXT NOT NULL,
  rule_type TEXT NOT NULL, rule_key TEXT NOT NULL, field TEXT NOT NULL, old_value TEXT, new_value TEXT, reason TEXT NOT NULL);
"""


def connect(path=":memory:", check_same_thread=True) -> sqlite3.Connection:
    """check_same_thread=False is needed when a web server hands one connection between worker threads."""
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_aggregate("dsum", 1, _DSum)
    conn.executescript(SCHEMA)
    return conn


def next_id(conn, table, column, prefix, width) -> str:
    row = conn.execute(f"SELECT MAX({column}) m FROM {table} WHERE {column} LIKE ?", (prefix + "%",)).fetchone()
    n = int(row["m"][len(prefix):]) + 1 if row["m"] else 1
    return f"{prefix}{n:0{width}d}"
