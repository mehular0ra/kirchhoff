"""The D1 fix line for voice's "why" answers, ported from the web co-pilot (apps/web/src/lib/format.ts
fmtKeyValue, src/workspace/finding/fixView.ts readFix, src/workspace/copilot/tools.ts fixLine). The expected
strings are format.test.ts's own, so the two co-pilots word a fix the same way."""
from kirchhoff.agents.fix_text import fix_line, fmt_key_value
from kirchhoff.contracts import Finding


def test_engine_keys_read_as_the_web_writes_them():
    assert fmt_key_value("dv_pct", 0.84) == "ΔV 0.84%"
    assert fmt_key_value("dv_pct", 0.8362) == "ΔV 0.84%"
    assert fmt_key_value("cost_delta", 18000) == "Cost Δ +$18,000"
    assert fmt_key_value("cost_delta", -500.0) == "Cost Δ -$500"
    assert fmt_key_value("cost_usd", 4200000) == "Cost $4,200,000"
    assert fmt_key_value("rating_a", 2500.0) == "Rating 2,500 A"
    assert fmt_key_value("added_pipe_m", 2.4) == "Added pipe 2.4 m"
    assert fmt_key_value("changed_pipes", 1.0) == "Changed pipes 1"
    assert fmt_key_value("crossings", 0.0) == "Crossings 0"
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


def test_fix_line_leads_with_cost_then_the_first_delta_and_tidies_tier_tokens():
    child = [_finding(None, "R11:H-Z2", "pass")]
    assert fix_line(_finding(FIX, "R11:H-Z2"), "r2", child) == (
        " Fixed in r2: Drop H-Z2 to the low pipe tier where it crosses FB-03 · Cost Δ +$420 · Crossings 0.")


def test_fix_line_says_chosen_fix_when_the_next_revision_does_not_show_it_fixed():
    assert fix_line(_finding(FIX, "R11:H-Z2"), "r2", []).startswith(" Chosen fix: Drop H-Z2")
    still = [_finding(None, "R11:H-Z2", "fail")]
    assert fix_line(_finding(FIX, "R11:H-Z2"), "r2", still).startswith(" Chosen fix: ")


def test_fix_line_is_empty_without_a_fix_record_and_falls_back_to_the_candidate_id():
    assert fix_line(_finding(None), "r2", []) == ""
    assert fix_line(_finding({"candidate": "FA-01:cable", "deltas": {"cost_delta": 10.0}}), "r2", []) == (
        " Chosen fix: FA-01:cable · Cost Δ +$10.")
