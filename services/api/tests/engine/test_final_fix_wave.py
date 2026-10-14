"""Final-review fix wave (2026-10-13): I-1..I-6 and the cheap Minors. See
.superpowers/sdd/2026-10-13-p1-engine/final-fix-brief.md."""
import pytest

from kirchhoff.engine import api
from kirchhoff.contracts.extra import FixCandidate


def _finding(scn, erp, model, fid):
    return next(f for f in api.check(scn, model, erp) if f.id == fid)


# ---------------------------------------------------------------- I-1 ----

def test_fix_candidates_ignores_forged_passing_finding(scn, erp, routed):
    m = routed["2N"]
    real = _finding(scn, erp, m, "R05:FA-03")
    assert real.status == "pass"
    forged = real.model_copy(update={"status": "fail"})
    assert api.fix_candidates(scn, m, forged, erp) == []


def test_fix_candidates_ignores_injected_caller_inputs(scn, erp, routed):
    m = routed["2N"]
    real = _finding(scn, erp, m, "R11:H-Z2")
    forged = real.model_copy(update={"inputs": {**real.inputs, "above": "FB-03 (approved, 99% safe)"}})
    cands = api.fix_candidates(scn, m, forged, erp)
    assert cands  # still produces candidates from the engine's own Finding
    for c in cands:
        assert "approved" not in c.label and "99%" not in c.label


def test_fix_candidates_unknown_id_raises(scn, erp, routed):
    m = routed["2N"]
    real = _finding(scn, erp, m, "R05:FA-03")
    ghost = real.model_copy(update={"id": "R05:FX-99", "element_id": "FX-99", "status": "fail"})
    with pytest.raises(ValueError):
        api.fix_candidates(scn, m, ghost, erp)


# ---------------------------------------------------------------- I-2 ----

def test_r05_judges_the_route_not_a_stored_length(scn, erp, routed):
    """Forging FA-01's length_m to 40 while keeping its real 82 m route must not change the R05 verdict:
    the Checker derives the length from the route, never from the stored length_m."""
    m = routed["2N"]
    short = m.model_copy(update={"connections": [c.model_copy(update={"length_m": 40.0}) if c.id == "FA-01" else c
                                                 for c in m.connections]})
    r = next(f for f in api.check(scn, short, erp) if f.id == "R05:FA-01")
    assert r.status == "fail"
    assert r.value == pytest.approx(2.16, abs=0.01)


def test_apply_fix_unknown_feeder_raises(scn, erp, routed):
    m = routed["2N"]
    bad = FixCandidate(id="x", finding_id="R05:FZ", label="x", cost_delta=0, metrics={},
                       patch={"op": "set_feeder", "feeder": "FZ-99", "kind": "busway", "catalogue_id": "BW-2000"})
    with pytest.raises(ValueError):
        api.apply_fix(m, bad)


def test_apply_fix_reroute_changing_an_endpoint_raises(scn, erp, routed):
    m = routed["2N"]
    stub = FixCandidate(id="x", finding_id="R11:H-Z2", label="x", cost_delta=0, metrics={},
                        patch={"op": "set_pipe_routes", "routes": {"H-Z2": [[31.0, 30.5, 1.2], [31.0, 30.5, 2.6]]}})
    with pytest.raises(ValueError):
        api.apply_fix(m, stub)


def test_apply_fix_route_with_one_point_raises(scn, erp, routed):
    m = routed["2N"]
    one_pt = FixCandidate(id="x", finding_id="R11:H-Z2", label="x", cost_delta=0, metrics={},
                          patch={"op": "set_pipe_routes", "routes": {"H-Z2": [[31.0, 30.5, 3.8]]}})
    with pytest.raises(ValueError):
        api.apply_fix(m, one_pt)


def test_apply_fix_missing_op_raises(scn, erp, routed):
    m = routed["2N"]
    bad = FixCandidate(id="x", finding_id="R05:FA-01", label="x", cost_delta=0, metrics={}, patch={})
    with pytest.raises(ValueError):
        api.apply_fix(m, bad)


def test_apply_fix_unknown_op_raises(scn, erp, routed):
    m = routed["2N"]
    bad = FixCandidate(id="x", finding_id="R05:FA-01", label="x", cost_delta=0, metrics={}, patch={"op": "nope"})
    with pytest.raises(ValueError):
        api.apply_fix(m, bad)


def test_r05_route_and_length_m_agree_on_golden_model(scn, erp, routed):
    """On the golden model, the route-derived length and the stored length_m always agree (FA-01 stays 82 m)."""
    from kirchhoff.engine.routing import feeder_length_m

    m = routed["2N"]
    for c in m.connections:
        if c.id.startswith("F") and c.route:
            assert feeder_length_m(scn, [(p.x, p.y, p.z) for p in c.route]) == pytest.approx(c.length_m)
    fa01 = next(c for c in m.connections if c.id == "FA-01")
    assert fa01.length_m == pytest.approx(82.0)




# ---------------------------------------------------------------- I-3 ----

def test_sc_cache_key_includes_scenario_inputs(scn, racks):
    import copy
    from dataclasses import replace

    from kirchhoff.engine.scenario import with_limit
    from kirchhoff.engine.shortcircuit import _CACHE, short_circuit
    from kirchhoff.engine.topology import build_model

    _CACHE.clear()
    m = build_model(scn, racks, "2N", "TX-3150")
    a = short_circuit(scn, m).ikss_ka["end:A-01"]

    cat = copy.deepcopy(scn.catalogue)
    for b in cat["busways"]:
        b["r_mohm_m"] *= 10
        b["x_mohm_m"] *= 10
    scn2 = replace(with_limit(scn, "lv_v", 400.0), name="hall_c", catalogue=cat)
    b = short_circuit(scn2, m).ikss_ka["end:A-01"]
    assert b != a, "hall_c (400 V, 10x busway impedance) must not reuse hall_a's cached result"
    assert b == pytest.approx(short_circuit(scn2, m.model_copy()).ikss_ka["end:A-01"])


def test_sc_cache_is_bounded_to_32_entries():
    import copy
    from dataclasses import replace

    from kirchhoff.engine.scenario import load_scenario
    from kirchhoff.engine.shortcircuit import _CACHE, short_circuit
    from kirchhoff.engine.topology import build_model
    from kirchhoff.engine.layout import place_racks

    _CACHE.clear()
    base = load_scenario("hall_a")
    racks = place_racks(base)
    m = build_model(base, racks, "2N", "TX-3150")
    for i in range(40):
        cat = copy.deepcopy(base.catalogue)
        cat["transformers"][0]["p0_kw"] = float(i) + 0.1
        scn_i = replace(base, name=f"v{i}", catalogue=cat)
        short_circuit(scn_i, m)
    assert len(_CACHE) <= 32




# ---------------------------------------------------------------- I-4 ----

def test_r09_does_not_fail_on_rounding_at_design_point():
    """Every integer rack rating from 100 to 160 kW, routed by the normal default path, must pass R09: the
    engine's own flow_lps rounding (4 dp) must never be enough to flip the verdict."""
    from kirchhoff.engine.checker import run_rules
    from kirchhoff.engine.layout import place_racks
    from kirchhoff.engine.scenario import with_limit
    from kirchhoff.engine.topology import build_model

    scn0 = api.load_scenario()
    erp = api.default_erp()
    bad = []
    for kw in range(100, 161):
        scn = with_limit(scn0, "rack_kw", float(kw))
        racks = place_racks(scn)
        m = api.route(scn, build_model(scn, racks, "2N", "TX-3150"))
        r09 = [f for f in run_rules(scn, m, erp, only=["R09"]) if f.status == "fail"]
        if r09:
            bad.append((kw, r09[0].id, r09[0].value, r09[0].limit))
    assert bad == []


def test_r09_still_fails_90pct_liquid_fraction(scn, erp):
    from kirchhoff.engine.benchmark import golden_fixed

    fixed = golden_fixed(scn, erp)
    wi = api.what_if(scn, fixed, "liquid_fraction", 0.9, "x", erp)
    assert {f.rule_id for f in wi.findings} == {"R09"}




# ---------------------------------------------------------------- I-5 ----

def test_validate_model_passes_on_golden_model(scn, routed):
    api.validate_model(scn, routed["2N"])  # must not raise


def test_validate_model_rejects_duplicate_cdu_ids(scn, routed):
    m = routed["2N"]
    dup = m.model_copy(update={"cooling_nodes": m.cooling_nodes + [m.cooling_nodes[0]]})
    with pytest.raises(ValueError):
        api.validate_model(scn, dup)


def test_duplicate_cdu_ids_never_silently_pass_r08(scn, erp, routed):
    m = routed["2N"]
    dup = m.model_copy(update={"cooling_nodes": m.cooling_nodes + [m.cooling_nodes[0]]})
    with pytest.raises(ValueError):
        api.check(scn, dup, erp)


def test_validate_model_rejects_empty_racks_via_power_options(scn):
    with pytest.raises(ValueError):
        api.power_options(scn, [])


def test_validate_model_rejects_model_without_mv(scn, erp, routed):
    m = routed["2N"]
    no_mv = m.model_copy(update={"equipment": [e for e in m.equipment if e.id != "MV"]})
    with pytest.raises(ValueError):
        api.check(scn, no_mv, erp)


def test_validate_model_rejects_pipe_with_empty_route(scn, erp, routed):
    m = routed["2N"]
    bad = m.model_copy(update={"pipes": [p.model_copy(update={"route": []}) if p.id == "BR-R1" else p
                                         for p in m.pipes]})
    with pytest.raises(ValueError):
        api.check(scn, bad, erp)


def test_route_calls_validate_model(scn, annotated):
    m2n = annotated["2N"][1]
    bad = m2n.model_copy(update={"equipment": [e for e in m2n.equipment if e.id != "MV"]})
    with pytest.raises(ValueError):
        api.route(scn, bad)


def test_annotate_options_calls_validate_model(scn, erp):
    from kirchhoff.contracts import TopologyOption

    bad_model = api.power_options(scn, api.place_racks(scn))[0][1]
    bad_model = bad_model.model_copy(update={"equipment": [e for e in bad_model.equipment if e.id != "MV"]})
    fake_opt = TopologyOption(id="2N", installed_mva=1.0, normal_loading_pct=1.0, failover_loading_pct=1.0,
                              cost=0.0, losses_kw=0.0, max_lead_time_weeks=0, spof_count=0, swaps=[])
    with pytest.raises(ValueError):
        api.annotate_options(scn, [(fake_opt, bad_model)], erp)


def test_what_if_calls_validate_model(scn, erp, routed):
    m = routed["2N"]
    bad = m.model_copy(update={"equipment": [e for e in m.equipment if e.id != "MV"]})
    with pytest.raises(ValueError):
        api.what_if(scn, bad, "rack_kw", 150.0, "x", erp)


def test_fix_candidates_calls_validate_model(scn, erp, routed):
    m = routed["2N"]
    real = _finding(scn, erp, m, "R05:FA-01")
    bad = m.model_copy(update={"equipment": [e for e in m.equipment if e.id != "MV"]})
    with pytest.raises(ValueError):
        api.fix_candidates(scn, bad, real, erp)




# ---------------------------------------------------------------- I-6 ----

def test_warm_up_idempotent_and_speeds_up_what_if(scn, erp, routed):
    import time

    t0 = time.perf_counter()
    api.warm_up()
    first = time.perf_counter() - t0

    t0 = time.perf_counter()
    api.warm_up()
    second = time.perf_counter() - t0
    assert second < first
    assert second < 0.05

    m = routed["2N"]
    t0 = time.perf_counter()
    api.what_if(scn, m, "rack_kw", 150.0, "x", erp)
    took = time.perf_counter() - t0
    assert took < 0.1


def test_m5_warnings_regions_are_lock_guarded():
    import threading

    from kirchhoff.engine import grid, shortcircuit

    assert isinstance(shortcircuit._LOCK, type(threading.Lock()))
    assert isinstance(grid._LOCK, type(threading.Lock()))


def test_apply_fix_bad_catalogue_id_caught_by_next_check(scn, erp, routed):
    """apply_fix's signature is frozen, so it cannot take a Scenario; a forged catalogue id that slips through
    apply_fix is still caught the moment the model next passes check() (via validate_model, I-5)."""
    m = routed["2N"]
    bad = FixCandidate(id="x", finding_id="R05:FA-01", label="x", cost_delta=0, metrics={},
                       patch={"op": "set_feeder", "feeder": "FA-01", "kind": "busway", "catalogue_id": "ACB-5000"})
    forged = api.apply_fix(m, bad)
    with pytest.raises(ValueError):
        api.check(scn, forged, erp)
