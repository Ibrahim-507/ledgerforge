"""Your OLD API tests (Tasks 2 to 6) call paths like /employees. After /api/v1 they must call /api/v1/employees.
This rewrites those calls in tests/*.py.  See what it would change first:   python -m scripts.fix_test_paths
Then do it:                                                                   python -m scripts.fix_test_paths --apply
Undo it (if those tests use their own small app without /api/v1):             python -m scripts.fix_test_paths --revert"""
import re
import sys
from pathlib import Path

SKIP = {"test_security.py", "test_api_security.py", "test_api_reports.py", "test_api_jobs.py", "test_tax_config.py",
        "test_statutory_reports.py", "test_financials.py", "test_payroll_engine.py", "test_payroll_rules.py", "test_payroll_runs.py",
        "test_ledger.py", "test_invoicing.py", "test_expenses.py", "test_payslip.py", "test_jobs.py", "test_versioning.py",
        "test_release_files.py", "conftest.py"}
PATTERN = re.compile(r"""(\.(?:get|post|put|patch|delete|options|head|request)\(\s*(?:["'][A-Z]+["']\s*,\s*)?f?)(["'])(/(?:departments|employees|payslips|attendance|leave|leaves|holidays|vendors|expenses|salary|auth|payroll-runs|bills|reports|tax|jobs)\b)""")


REVERT = re.compile(r"""(\.(?:get|post|put|patch|delete|options|head|request)\(\s*(?:["'][A-Z]+["']\s*,\s*)?f?)(["'])/api/v1(/(?:departments|employees|payslips|attendance|leave|leaves|holidays|vendors|expenses|salary|auth|payroll-runs|bills|reports|tax|jobs)\b)""")


def rewrite(text: str, revert: bool = False) -> str:
    if revert:
        return REVERT.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}", text)
    return PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}/api/v1{m.group(3)}", text)


if __name__ == "__main__":
    revert = "--revert" in sys.argv
    apply = "--apply" in sys.argv or revert
    changed = 0
    for f in sorted(Path("tests").glob("*.py")):
        if f.name in SKIP:
            continue
        old = f.read_text(encoding="utf-8")
        new = rewrite(old, revert)
        if new != old:
            changed += 1
            n = sum(1 for a, b in zip(old.splitlines(), new.splitlines()) if a != b)
            print(f"{'rewrote' if apply else 'would rewrite'} {f}  ({n} lines)")
            if apply:
                f.write_text(new, encoding="utf-8")
    print(f"{changed} file(s) {'changed' if apply else 'would change'}." + ("" if apply else "  Run again with --apply to do it."))
