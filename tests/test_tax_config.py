from decimal import Decimal as D
from pathlib import Path
import pandas as pd
import pytest
from app.books_db import connect
from app.ledger import load_chart
from app.payroll_data import PayrollSource
from app.payroll_engine import load_rates
from app.payroll_runs import approve_run, create_run, process_run
from app.tax_config import (RuleError, list_changes, list_slabs, load_rules, rules_version, seed_rules, update_parameter,
                            update_slab, update_statutory_rate)
from app.tax_explain import explain_tds
from app import payroll_rules as R

DATA = Path(__file__).resolve().parent.parent / "data"
official = pd.read_csv(DATA / "payroll_items.csv")
ADMIN = "U-0099"


def books():
    c = connect()
    load_chart(c, DATA / "chart_of_accounts.csv")
    seed_rules(c, str(DATA))
    return c


def month_tds(c, src, month):
    rid = create_run(c, f"{month}-01", "U-0237")
    process_run(c, src, rid)
    return D(c.execute("SELECT dsum(tds) t FROM payroll_items WHERE run_id=?", (rid,)).fetchone()["t"]), rid


def official_tds(run_id):
    return round(official[official.run_id == run_id].tds.sum(), 2)


def test_rules_in_the_database_equal_the_csv_rules():
    c = books()
    assert load_rules(c) == load_rates(str(DATA))
    assert seed_rules(c, str(DATA)) is False                  # seeding twice does nothing
    assert len(list_slabs(c, "FY2025-26")) == 7 and rules_version(c) == 0


def test_tax_steps_add_up_to_the_engine_result():
    rates, params, slabs = load_rules(books())
    s = explain_tds(144460, "34670.40", 30, 30, slabs["FY2025-26"], params)
    assert s["annual_taxable_income"] == D("1658520") and s["slab_tax"] == D("131704") and s["rebate_or_marginal_relief"] == 0
    assert s["annual_tax_with_cess"] == D("136972.16") and s["fixed_part"] == D("11414.35")
    assert s["extra_tax_on_variable_pay_with_cess"] == D("7211.44") and s["monthly_tds"] == D("18625.79")
    assert s["monthly_tds"] == R.monthly_tds(144460, "34670.40", 30, 30, slabs["FY2025-26"], params)


def test_changing_a_slab_changes_the_tax_and_changing_it_back_restores_it():
    c, src = books(), PayrollSource(str(DATA))
    before, _ = month_tds(c, src, "2025-04")
    assert before == D(str(official_tds("PR-2025-04")))                       # starts equal to the official data
    update_slab(c, "TS-005", ADMIN, "test: raise the 20% slab to 25%", rate_percent=25)
    after, _ = month_tds(c, src, "2025-05")
    assert after > D(str(official_tds("PR-2025-05")))                         # tax went UP after the change
    update_slab(c, "TS-005", ADMIN, "test: change it back", rate_percent=20)
    restored, _ = month_tds(c, src, "2025-06")
    assert restored == D(str(official_tds("PR-2025-06")))                     # back to the official figure
    assert rules_version(c) == 2


def test_past_months_are_not_altered_by_a_rule_change():
    c, src = books(), PayrollSource(str(DATA))
    _, rid = month_tds(c, src, "2025-04")
    approve_run(c, rid, "U-0099")
    snap = lambda: (c.execute("SELECT dsum(tds) a, dsum(net_pay) b FROM payroll_items WHERE run_id=?", (rid,)).fetchone()[:],
                    c.execute("SELECT dsum(credit) x FROM journal_lines WHERE account_code=2130").fetchone()[0])
    frozen = snap()
    update_slab(c, "TS-005", ADMIN, "test", rate_percent=30)
    update_parameter(c, "standard_deduction", 50000, ADMIN, "test")
    month_tds(c, src, "2025-05")                                              # a later month uses the new rules
    assert snap() == frozen                                                    # April rows and its ledger entry are untouched
    assert process_run(c, src, rid)["already"] is True                        # re-processing an approved run changes nothing
    v = {r["run_id"]: r["calculation_version"] for r in c.execute("SELECT run_id, calculation_version FROM payroll_runs")}
    assert v["PR-2025-04"].endswith("rules-v0") and v["PR-2025-05"].endswith("rules-v2")   # each run records its rules version


def test_a_new_tax_year_is_not_changed_by_editing_the_old_year():
    c, src = books(), PayrollSource(str(DATA))
    update_slab(c, "TS-005", ADMIN, "FY2025-26 only", rate_percent=40)        # TS-005 belongs to FY2025-26
    tds, _ = month_tds(c, src, "2026-04")                                     # first month of FY2026-27
    assert tds == D(str(official_tds("PR-2026-04")))


def test_slab_limits_can_be_moved_and_stay_joined():
    c = books()
    update_slab(c, "TS-002", ADMIN, "raise the 5% limit", income_to=900000)
    s = {r["slab_id"]: r for r in list_slabs(c, "FY2025-26")}
    assert s["TS-002"]["income_to"] == "900000" and s["TS-003"]["income_from"] == "900000"
    assert len(list_changes(c)) == 2                                          # both edges are logged


def test_bad_rule_changes_are_refused_and_every_change_is_logged():
    c = books()
    for kwargs, msg in [(dict(rate_percent=150, reason="x"), "between 0 and 100"), (dict(rate_percent=-1, reason="x"), "between 0 and 100"),
                        (dict(rate_percent=10, reason=""), "needs a reason"), (dict(reason="x"), "Nothing to change"),
                        (dict(income_to=100, reason="x"), "must be between")]:
        with pytest.raises(RuleError, match=msg):
            update_slab(c, "TS-002", ADMIN, kwargs.pop("reason"), **kwargs)
    with pytest.raises(RuleError, match="top slab"):
        update_slab(c, "TS-007", ADMIN, "x", income_to=3000000)
    with pytest.raises(RuleError, match="who made it"):
        update_slab(c, "TS-002", "", "x", rate_percent=6)
    with pytest.raises(RuleError, match="not found"):
        update_slab(c, "TS-999", ADMIN, "x", rate_percent=6)
    assert list_changes(c) == [] and rules_version(c) == 0                    # refused changes leave no trace
    update_statutory_rate(c, "PT_MONTHLY", 250, ADMIN, "state change")
    update_parameter(c, "health_education_cess_percent", 5, ADMIN, "budget")
    with pytest.raises(RuleError):
        update_parameter(c, "health_education_cess_percent", 500, ADMIN, "typo")
    log = list_changes(c)
    assert [(x["rule_key"], x["old_value"], x["new_value"], x["changed_by"]) for x in log] == [
        ("PT_MONTHLY", "200", "250", ADMIN), ("health_education_cess_percent", "4", "5", ADMIN)]
