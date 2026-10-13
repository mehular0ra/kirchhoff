"""Scenario regression lock (spec §16, Tue 14 Oct). Hall B has identical inputs, so this also covers Hall B."""
import pytest

from kirchhoff.engine import api
from kirchhoff.engine.checker import failing


def _fix_loop(scn, erp, model, max_iter=2):
    """Each iteration fixes every failing finding with its first (cheapest) candidate (spec §6.1)."""
    for _ in range(max_iter):
        fails = failing(api.check(scn, model, erp))
        if not fails:
            break
        for f in fails:
            current = {x.id: x for x in api.check(scn, model, erp)}[f.id]
            if current.status == "fail":
                cands = api.fix_candidates(scn, model, current, erp)
                assert cands, f"no candidate for {f.id}"
                model = api.apply_fix(model, cands[0])
    return model


@pytest.fixture(scope="module")
def golden(scn, erp):
    racks = api.place_racks(scn)
    return {o.id: (o, m) for o, m in api.annotate_options(scn, api.power_options(scn, racks), erp)}


def test_facade_is_complete():
    for name in ["load_scenario", "place_racks", "size_cooling", "power_options", "annotate_options", "route",
                 "detect_clashes", "check", "fix_candidates", "apply_fix", "derive_pr_lines", "model_hash",
                 "ledger_not_checked", "power_recheck", "derive_boq", "default_erp", "Scenario", "ErpView"]:
        assert hasattr(api, name), name


def test_r15_swap_and_only_transformers_fail_before(scn, erp):
    racks = api.place_racks(scn)
    for opt, model in api.power_options(scn, racks):
        fails = [f.element_id for f in api.check(scn, model, erp) if f.rule_id == "R15" and f.status == "fail"]
        assert fails == (["TX-2500"] if opt.id in ("2N", "DR") else []), opt.id


def test_golden_2n_first_pass_is_exactly_r05_fa01_and_r11_hz2(scn, erp, golden):
    opt, model = golden["2N"]
    assert [s["to"] for s in opt.swaps] == ["TX-3150"]
    assert (opt.normal_loading_pct, opt.failover_loading_pct) == pytest.approx((38.0, 76.0), abs=0.5)
    routed = api.route(scn, model)
    assert api.detect_clashes(routed).clashes == []
    findings = api.check(scn, routed, erp, api.derive_pr_lines(scn, routed, erp))
    fails = failing(findings)
    assert [f.id for f in fails] == ["R05:FA-01", "R11:H-Z2"]
    assert 2.1 <= fails[0].value <= 2.4
    assert fails[1].inputs["above"] == "FB-03" and fails[1].inputs["at_y"] == pytest.approx(24.0, abs=1.0)
    assert len(findings) >= 140


def test_golden_2n_reaches_all_pass_with_either_candidate(scn, erp, golden):
    routed = api.route(scn, golden["2N"][1])
    for i in range(2):
        r05 = next(f for f in api.check(scn, routed, erp) if f.id == "R05:FA-01")
        r11 = next(f for f in api.check(scn, routed, erp) if f.id == "R11:H-Z2")
        c05 = api.fix_candidates(scn, routed, r05, erp)
        c11 = api.fix_candidates(scn, routed, r11, erp)
        assert len(c05) == 2 and len(c11) == 2
        fixed = api.apply_fix(api.apply_fix(routed, c05[i]), c11[i])
        assert failing(api.check(scn, fixed, erp)) == []


@pytest.mark.parametrize("topo,first_fails", [("DR", ["R05:FA-01", "R05:FB-01", "R11:H-Z2"]),
                                              ("BLOCK", ["R05:FA-01", "R11:H-Z2"])])
def test_dr_and_block_reach_all_pass_within_two_iterations(scn, erp, golden, topo, first_fails):
    routed = api.route(scn, golden[topo][1])
    assert [f.id for f in failing(api.check(scn, routed, erp))] == first_fails
    fixed = _fix_loop(scn, erp, routed)
    assert failing(api.check(scn, fixed, erp)) == []


def test_200_kw_on_signed_model_fails_r01_r02_r08(scn, erp, golden):
    fixed = _fix_loop(scn, erp, api.route(scn, golden["2N"][1]))
    hot = fixed.model_copy(update={"racks": [r.model_copy(update={"kw": 200.0}) for r in fixed.racks],
                                   "loads": {**fixed.loads, "rack_kw": 200.0}})
    findings = {f.id: f for f in api.check(scn, hot, erp)}
    rules = {f.rule_id for f in findings.values() if f.status == "fail"}
    assert {"R01", "R02", "R08"} <= rules
    assert {"R03", "R05", "R07", "R09"} <= rules
    assert findings["R02:A-01"].value == pytest.approx(2343, rel=0.01)
    assert findings["R01:T-A1"].value == pytest.approx(114, abs=1)
    assert findings["R08:Z2"].value == pytest.approx(2560, abs=1) and findings["R08:Z2"].limit == 2400


def test_model_hash_is_deterministic_across_runs(scn, erp):
    racks = api.place_racks(scn)
    a = api.route(scn, api.annotate_options(scn, api.power_options(scn, racks), erp)[0][1])
    b = api.route(scn, api.annotate_options(scn, api.power_options(scn, racks), erp)[0][1])
    assert api.model_hash(a) == api.model_hash(b)
