import pytest

from kirchhoff.contracts import Point3
from kirchhoff.engine import api
from kirchhoff.engine.checker import run_rules
from kirchhoff.engine.spatial import column_clearance_m, pipe_crossings


def _by_id(findings):
    return {f.id: f for f in findings}


def _pipe(model, pid, **update):
    return model.model_copy(update={"pipes": [p.model_copy(update=update) if p.id == pid else p
                                              for p in model.pipes]})


def test_route_adds_feeder_routes_and_pipes(routed):
    m = routed["2N"]
    fa01 = next(c for c in m.connections if c.id == "FA-01")
    assert fa01.route[0] == Point3(x=66.0, y=4.0, z=3.2) and fa01.length_m == 82.0
    assert sorted(p.id for p in m.pipes) == ["BR-R1", "BR-R2", "BR-R3", "BR-R4", "BR-R5", "BR-R6",
                                            "H-Z1", "H-Z2", "H-Z3"]


def test_only_h_z2_crosses_electrical(routed):
    m = routed["2N"]
    crossings = {p.id: pipe_crossings(m, p) for p in m.pipes}
    assert {k: [c["run"] for c in v] for k, v in crossings.items() if v} == {"H-Z2": ["FB-03"]}
    assert crossings["H-Z2"][0]["at"] == [28.0, 24.0, 3.8]
    assert all(column_clearance_m(m, p) >= 0.3 for p in m.pipes)


def test_no_solid_clashes_in_default_routes(routed):
    for m in routed.values():
        assert api.detect_clashes(m).clashes == []


def test_solid_clash_when_pipe_on_busway_tier(routed):
    m = routed["2N"]
    low = [Point3(x=p.x, y=p.y, z=3.2 if p.z == 3.8 else p.z) for p in next(x for x in m.pipes if x.id == "H-Z2").route]
    clashes = api.detect_clashes(_pipe(m, "H-Z2", route=low)).clashes
    assert {(c["a"], c["b"], c["kind"]) for c in clashes} >= {("H-Z2", "FB-03", "solid")}


def test_cooling_rules_pass_and_fail(scn, routed):
    m = routed["2N"]
    f = _by_id(run_rules(scn, m, None, only=["R08", "R09", "R10", "R11", "R13", "R14"]))
    assert f["R08:Z1"].status == "pass" and f["R08:Z1"].value == pytest.approx(1689.6) and f["R08:Z1"].limit == 2400
    assert f["R09:M-R1"].value == pytest.approx(157, abs=0.5) and f["R09:M-R1"].status == "pass"
    assert f["R10:H-Z1"].value == pytest.approx(1.26, abs=0.01) and f["R10:BR-R1"].value == pytest.approx(1.13, abs=0.01)
    assert f["R11:H-Z2"].status == "fail" and f["R11:H-Z2"].inputs["above"] == "FB-03"
    assert f["R11:H-Z2"].tender_refs[0].clause == "§6.3.4"
    assert [x.id for x in f.values() if x.status == "fail"] == ["R11:H-Z2"]
    assert f["R13:CDU-1"].status == "pass" and f["R13:CDU-1"].inputs["systems"] == "A1, B1"
    assert f["R14:H-Z1"].value == pytest.approx(70, abs=3) and f["R14:H-Z1"].limit == 150.0
    # failing fixtures
    slow = _pipe(m, "BR-R2", flow_lps=next(p.flow_lps for p in m.pipes if p.id == "BR-R2") * 0.8)
    assert _by_id(run_rules(scn, slow, None, only=["R09"]))["R09:M-R2"].status == "fail"
    narrow = _pipe(m, "BR-R5", dn=100)
    assert _by_id(run_rules(scn, narrow, None, only=["R10"]))["R10:BR-R5"].status == "fail"
    near_col = _pipe(m, "BR-R4", route=[Point3(x=31.0, y=24.0, z=3.8), Point3(x=31.0, y=24.0, z=2.6),
                                        Point3(x=35.65, y=24.0, z=2.6), Point3(x=34.0, y=15.6, z=2.6)])
    assert _by_id(run_rules(scn, near_col, None, only=["R11"]))["R11:BR-R4"].status == "fail"
    nodes = [n.model_copy(update={"capacity_kw": 800.0}) if n.zone == "Z3" and n.kind == "cdu" else n
             for n in m.cooling_nodes]
    assert _by_id(run_rules(scn, m.model_copy(update={"cooling_nodes": nodes}), None, only=["R08"]))[
        "R08:Z3"].status == "fail"
    conns = [c.model_copy(update={"src": "CB-A1"}) if c.id == "PF-CDU-2-2" else c for c in m.connections]
    assert _by_id(run_rules(scn, m.model_copy(update={"connections": conns}), None, only=["R13"]))[
        "R13:CDU-2"].status == "fail"


def test_check_facade_counts_every_rule(scn, erp, routed):
    findings = api.check(scn, routed["2N"], erp)
    assert {f.rule_id for f in findings} == {"R01", "R02", "R03", "R04", "R04b", "R05", "R06", "R07", "R08", "R09",
                                            "R10", "R11", "R12", "R13", "R14", "R15"}
    assert len({f.id for f in findings}) == len(findings)
    assert all(f.status in ("pass", "fail") for f in findings)


def test_r13_explanation_reads_cleanly_once_filled(scn, routed):
    """P2 final fix wave (ruling P2-R19): the unit "systems" follows {value}, so filling never doubles it
    (it used to read "fed from 2 systems independent UPS-backed systems"). Bundled into the static demo."""
    from kirchhoff.agents.trust import fill_finding

    f = _by_id(run_rules(scn, routed["2N"], None, only=["R13"]))["R13:CDU-1"]
    assert fill_finding(f.explanation, f.value, f.limit, f.unit) == (
        "CDU-1 pumps have independent UPS-backed supplies from 2 systems; at least 2 systems are required.")
