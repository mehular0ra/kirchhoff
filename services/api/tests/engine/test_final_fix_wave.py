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


def test_apply_fix_bad_catalogue_id_caught_by_next_check(scn, erp, routed):
    """apply_fix's signature is frozen, so it cannot take a Scenario; a forged catalogue id that slips through
    apply_fix is still caught the moment the model next passes check() (via validate_model, I-5)."""
    m = routed["2N"]
    bad = FixCandidate(id="x", finding_id="R05:FA-01", label="x", cost_delta=0, metrics={},
                       patch={"op": "set_feeder", "feeder": "FA-01", "kind": "busway", "catalogue_id": "ACB-5000"})
    forged = api.apply_fix(m, bad)
    with pytest.raises(ValueError):
        api.check(scn, forged, erp)
