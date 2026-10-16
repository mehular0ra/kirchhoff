"""The D1 fix line for voice's "why" answers, ported from the web co-pilot (apps/web/src/lib/format.ts
fmtKeyValue, src/workspace/finding/fixView.ts readFix, src/workspace/copilot/tools.ts fixLine). The expected
strings are format.test.ts's own, so the two co-pilots word a fix the same way."""
import json
import re

import pytest

from kirchhoff.agents.fix_text import fix_line, fmt_key_value, read_fix
from kirchhoff.contracts import Finding
from kirchhoff.enterprise.paths import repo_root


def test_engine_keys_read_as_the_web_writes_them():
    assert fmt_key_value("dv_pct", 0.84) == "ΔV 0.84%"
    assert fmt_key_value("dv_pct", 0.8362) == "ΔV 0.84%"
    assert fmt_key_value("cost_delta", 18000) == "Cost Δ +$18,000"
    assert fmt_key_value("cost_delta", -500.0) == "Cost Δ -$500"
    assert fmt_key_value("cost_usd", 4200000) == "Cost $4,200,000"
    assert fmt_key_value("rating_a", 2500.0) == "Rating 2,500 A"
    assert fmt_key_value("added_pipe_m", 2.4) == "Added pipe 2.4 m"
    assert fmt_key_value("changed_pipes", 1.0) == "1 changed pipe"
    assert fmt_key_value("changed_pipes", 2.0) == "2 changed pipes"
    assert fmt_key_value("crossings", 0.0) == "0 crossings"
    assert fmt_key_value("crossings", 1.0) == "1 crossing"
    assert fmt_key_value("lines", 12) == "12 lines"
    assert fmt_key_value("ampacity_a", 1546.4347) == "Ampacity 1,546.43 A"
    assert fmt_key_value("lead_time_weeks", 1) == "Lead time 1 week"
    assert fmt_key_value("options", [{"id": "2N"}, {"id": "DR"}, {"id": "N+1"}]) == "3 options"
    assert fmt_key_value("pipes", {"H-Z1": "pipe_high", "H-Z2": "pipe_low"}) == "2 pipes"
    assert fmt_key_value("clashes", [{"a": "H-Z2", "b": "FB-03"}]) == "1 clash"
    assert fmt_key_value("candidates", []) == "0 candidates"
    assert fmt_key_value("finding_id", "R05:FA-01") == "Finding R05:FA-01"
    assert fmt_key_value("ok", True) == "OK ✓" and fmt_key_value("ok", False) == "OK ✗"
    assert fmt_key_value("fail_ids", ["R05:FA-01", "R11:H-Z2"]) == "Fail ids R05:FA-01, R11:H-Z2"
    assert fmt_key_value("changed", ["a", "b", "c", "d", "e", "f"]) == "Changed a, b, c, d +2 more"
    assert fmt_key_value("reason", None) == "Reason —"


def _finding(fix, fid="R05:FA-01", status="fail"):
    return Finding(id=fid, rule_id=fid.split(":")[0], element_id=fid.split(":")[1], status=status,
                   title="Voltage drop", fix=fix)


FIX = {"label": "Drop H-Z2 to pipe_low where it crosses FB-03", "cost_delta": 420.0,
       "deltas": {"crossings": 0.0, "added_pipe_m": 2.4, "changed_pipes": 1.0}}


def test_fix_line_leads_with_cost_then_the_rules_resulting_metric_and_tidies_tier_tokens():
    child = [_finding(None, "R11:H-Z2", "pass")]
    assert fix_line(_finding(FIX, "R11:H-Z2"), "r2", child) == (
        " Fixed in r2: Drop H-Z2 to the low pipe tier where it crosses FB-03 · Cost Δ +$420 · 0 crossings.")


def test_fix_line_picks_deltas_by_key_not_position():
    """A recorded fix stores its deltas key-sorted with the cost inside: the limit and the side metrics come
    first, and none of them is the result the rule is judged on."""
    sorted_fix = {"label": "Parallel cable", "cost_delta": 10.0,
                  "deltas": {"cost_delta": 10.0, "dv_limit_pct": 2.0, "dv_pct": 0.8362, "rating_a": 2500.0}}
    assert fix_line(_finding(sorted_fix), "r2", []) == " Chosen fix: Parallel cable · Cost Δ +$10 · ΔV 0.84%."
    # A rule with no listed metric falls back to the first delta that is neither a cost nor a limit.
    other = {"label": "X", "deltas": {"a_limit_pct": 5.0, "loading_pct": 71.0, "cost_delta": -3.0}}
    assert fix_line(_finding(other, "R99:T-1"), None, []) == " Chosen fix: X · Cost Δ -$3 · Loading 71%."


def _captured_r1():
    root = repo_root()
    assert root is not None
    bundle = json.loads((root / "apps/web/public/demo/projects/hall-a.json").read_text(encoding="utf-8"))
    return [f for f in bundle["findings"]["r1"] if f.get("fix")]


PRIMARY = {"R05": "dv_pct", "R11": "crossings"}


@pytest.mark.parametrize("which", ["fix", "rejected_fix"])
def test_captured_fix_records_lead_with_the_cost_then_the_resulting_metric(which):
    """The golden capture (Hall A r1): every fix record reads cost first, then the rule's resulting metric, then
    its limit and the rest; every entry is the record's own (nothing dropped, added or changed)."""
    records = [f for f in _captured_r1() if f.get(which)]
    assert {f["rule_id"] for f in records} >= {"R05", "R11"}
    for f in records:
        rec = f[which]
        view = read_fix(rec, f["rule_id"])
        recorded = {**({"cost_delta": rec["cost_delta"]} if "cost_delta" in rec else {}), **rec["deltas"]}
        assert dict(view["deltas"]) == recorded and len(view["deltas"]) == len(recorded)
        keys = [k for k, _ in view["deltas"]]
        assert keys[:2] == ["cost_delta", PRIMARY[f["rule_id"]]]
        assert view["headline"] == view["deltas"][:2]
        limits = [i for i, k in enumerate(keys) if "limit" in k]
        assert all(i == 2 + n for n, i in enumerate(limits))  # a limit sits right after the result it bounds
        assert not re.search(r"\b[a-z]+_[a-z_]+\b", view["label"])


def test_fix_line_says_chosen_fix_when_the_next_revision_does_not_show_it_fixed():
    assert fix_line(_finding(FIX, "R11:H-Z2"), "r2", []).startswith(" Chosen fix: Drop H-Z2")
    still = [_finding(None, "R11:H-Z2", "fail")]
    assert fix_line(_finding(FIX, "R11:H-Z2"), "r2", still).startswith(" Chosen fix: ")


def test_fix_line_is_empty_without_a_fix_record_and_falls_back_to_the_candidate_id():
    assert fix_line(_finding(None), "r2", []) == ""
    assert fix_line(_finding({"candidate": "FA-01:cable", "deltas": {"cost_delta": 10.0}}), "r2", []) == (
        " Chosen fix: FA-01:cable · Cost Δ +$10.")


def test_rounding_matches_node_intl_on_decimal_ties():
    """Expected strings are Node's own Intl.NumberFormat output (en-US, maximumFractionDigits 2 / USD with 0):
    ties round half away from zero on the shortest decimal (repr), not on the binary value (2.675 -> 2.67)."""
    from kirchhoff.agents.fix_text import fmt_num, fmt_usd

    assert [fmt_num(v) for v in (2.675, 1.005, 0.835, -1.005, 0.125)] == ["2.68", "1.01", "0.84", "-1.01", "0.13"]
    assert [fmt_usd(v) for v in (2.5, -2.5, 15580.0)] == ["$3", "-$3", "$15,580"]
    assert fmt_usd(-0.4) == "-$0" and fmt_usd(-0.0) == "-$0"
    assert fmt_num(-0.004) == "-0" and fmt_num(1e21) == "1,000,000,000,000,000,000,000"


def test_non_finite_values_format_as_the_web_shows_them_instead_of_raising():
    from kirchhoff.agents.fix_text import fmt_num, fmt_usd

    assert (fmt_num(float("inf")), fmt_num(float("-inf")), fmt_num(float("nan"))) == ("∞", "-∞", "—")
    assert (fmt_usd(float("inf")), fmt_usd(float("-inf"))) == ("$∞", "-$∞")
    assert fmt_key_value("cost_delta", float("inf")) == "Cost Δ +$∞"
