import pytest

from kirchhoff.engine import api
from kirchhoff.engine.fixes import local_drop_route


def _finding(scn, erp, model, fid):
    return next(f for f in api.check(scn, model, erp) if f.id == fid)


def test_fa01_candidates_match_spec(scn, erp, routed):
    m = routed["2N"]
    cands = api.fix_candidates(scn, m, _finding(scn, erp, m, "R05:FA-01"), erp)
    by_id = {c.id: c for c in cands}
    assert set(by_id) == {"FA-01:upsize-BW-2000", "FA-01:cable-CBL-240-8P"}
    assert by_id["FA-01:upsize-BW-2000"].metrics["dv_pct"] == pytest.approx(1.66, abs=0.02)
    assert by_id["FA-01:cable-CBL-240-8P"].metrics["dv_pct"] == pytest.approx(0.84, abs=0.02)
    assert by_id["FA-01:upsize-BW-2000"].cost_delta == pytest.approx(82 * (560 - 420), abs=1)
    assert by_id["FA-01:upsize-BW-2000"].label == "Upsize FA-01 to 2,000 A busway"
    assert [c.id for c in cands] == sorted(by_id, key=lambda k: (by_id[k].cost_delta, k))


def test_h_z2_candidates_clear_r11(scn, erp, routed):
    m = routed["2N"]
    cands = {c.id: c for c in api.fix_candidates(scn, m, _finding(scn, erp, m, "R11:H-Z2"), erp)}
    assert set(cands) == {"H-Z2:local-drop", "H-Z2:reroute"}
    drop = cands["H-Z2:local-drop"]
    assert drop.metrics["crossings"] == 0 and drop.metrics["added_pipe_m"] == pytest.approx(2.4)
    assert drop.metrics["changed_pipes"] == 1 and cands["H-Z2:reroute"].metrics["changed_pipes"] == 2
    assert drop.patch["routes"]["H-Z2"][3:7] == [[28.7, 24.0, 3.8], [28.7, 24.0, 2.6], [27.3, 24.0, 2.6],
                                                 [27.3, 24.0, 3.8]]


def test_every_candidate_clears_target_without_new_failures(scn, erp, routed):
    m = routed["2N"]
    base = {f.id for f in api.check(scn, m, erp) if f.status == "fail"}
    assert base == {"R05:FA-01", "R11:H-Z2"}
    for fid in sorted(base):
        for cand in api.fix_candidates(scn, m, _finding(scn, erp, m, fid), erp):
            after = {f.id for f in api.check(scn, api.apply_fix(m, cand), erp) if f.status == "fail"}
            assert after == base - {fid}, cand.id


def test_apply_fix_is_pure_and_detect_clashes_stays_clean(scn, erp, routed):
    m = routed["2N"]
    before = api.model_hash(m)
    cand = next(c for c in api.fix_candidates(scn, m, _finding(scn, erp, m, "R11:H-Z2"), erp)
                if c.id == "H-Z2:local-drop")
    fixed = api.apply_fix(m, cand)
    assert api.model_hash(m) == before and api.model_hash(fixed) != before
    assert api.detect_clashes(fixed).clashes == []
    assert local_drop_route(fixed, "H-Z2") == [[p.x, p.y, p.z] for p in
                                               next(x for x in fixed.pipes if x.id == "H-Z2").route]


def test_no_candidates_for_other_rules(scn, erp, routed):
    m = routed["2N"]
    assert api.fix_candidates(scn, m, _finding(scn, erp, m, "R01:T-A1"), erp) == []
