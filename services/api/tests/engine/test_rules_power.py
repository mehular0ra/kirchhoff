import pytest

from kirchhoff.engine.checker import run_rules


def _by_id(findings):
    return {f.id: f for f in findings}


def _eq(model, eid, **update):
    return model.model_copy(update={"equipment": [e.model_copy(update=update) if e.id == eid else e
                                                  for e in model.equipment]})


def _param(model, eid, key, value):
    e = next(x for x in model.equipment if x.id == eid)
    return _eq(model, eid, params={**e.params, key: value})


@pytest.fixture(scope="module")
def m(models):
    return models[("2N", "TX-3150")]


def test_r01_pass_and_fail(scn, models, m):
    f = _by_id(run_rules(scn, m, None, only=["R01"]))["R01:T-A1"]
    assert f.status == "pass" and f.value == pytest.approx(76, abs=0.5) and f.limit == 100.0
    assert f.inputs["normal_pct"] == pytest.approx(38, abs=0.5)
    assert f.tender_refs[0].clause == "§4.3" and f.clause_refs[0].standard == "IEC 60076-12"
    bad = _by_id(run_rules(scn, models[("BLOCK", "TX-2500")], None, only=["R01"]))["R01:T-K1"]
    assert bad.status == "fail" and bad.value == pytest.approx(96, abs=0.5) and bad.limit == 80.0
    assert "{value}" in bad.explanation and "{limit}" in bad.explanation


def test_r02_pass_and_fail(scn, m):
    f = _by_id(run_rules(scn, m, None, only=["R02"]))
    assert len(f) == 24 and f["R02:A-01"].status == "pass" and f["R02:A-01"].value == pytest.approx(1546, rel=0.01)
    assert f["R02:FA-01"].status == "pass"
    bad = _by_id(run_rules(scn, _eq(m, "A-03", rating=1250.0), None, only=["R02"]))
    assert bad["R02:A-03"].status == "fail" and bad["R02:A-04"].status == "pass"


def test_r03_pass_and_fail(scn, m):
    f = _by_id(run_rules(scn, m, None, only=["R03"]))
    assert len(f) == 12 and all(x.status == "pass" for x in f.values())
    low = _by_id(run_rules(scn, _param(m, "CB-A1", "brk.FA-02.in_a", 1500.0), None, only=["R03"]))
    assert low["R03:FA-02"].status == "fail"
    high = _by_id(run_rules(scn, _param(m, "CB-B2", "brk.FB-04.in_a", 2000.0), None, only=["R03"]))
    assert high["R03:FB-04"].status == "fail"


def test_r04_and_r04b_pass_and_fail(scn, m):
    f = _by_id(run_rules(scn, m, None, only=["R04", "R04b"]))
    assert f["R04:A1"].status == "pass" and f["R04:A1"].value == pytest.approx(66, abs=8)
    assert f["R04:A1"].limit == 100.0 and f["R04b:FA-01"].limit == 85.0
    assert all(x.status == "pass" for x in f.values())
    bad = _by_id(run_rules(scn, _param(m, "T-B2", "uk_pct", 4.0), None, only=["R04", "R04b"]))
    assert bad["R04:B2"].status == "fail" and bad["R04b:FB-03"].status == "fail"
    assert bad["R04:A1"].status == "pass"


def test_r05_first_pass_feeders(scn, m):
    f = _by_id(run_rules(scn, m, None, only=["R05"]))
    assert f["R05:FA-01"].status == "fail" and 2.1 <= f["R05:FA-01"].value <= 2.4
    assert f["R05:FA-01"].value == pytest.approx(2.16, abs=0.02)
    assert f["R05:FA-02"].value == pytest.approx(1.73, abs=0.02) and f["R05:FA-02"].status == "pass"
    assert f["R05:FB-01"].value == pytest.approx(1.34, abs=0.02)
    assert f["R05:FB-03"].value == pytest.approx(0.78, abs=0.02)
    assert [x.id for x in f.values() if x.status == "fail"] == ["R05:FA-01"]


def test_r06_pass_and_fail(scn, m):
    assert _by_id(run_rules(scn, m, None, only=["R06"]))["R06:HALL"].status == "pass"
    racks = [r.model_copy(update={"feeds": ("A-02", "A-02")}) if r.id == "R2-03" else r for r in m.racks]
    bad = run_rules(scn, m.model_copy(update={"racks": racks}), None, only=["R06"])
    assert {x.element_id for x in bad if x.status == "fail"} >= {"A-02", "FA-02", "CB-A1", "T-A1"}


def test_r07_pass_and_fail(scn, m):
    f = _by_id(run_rules(scn, m, None, only=["R07"]))["R07:UPS-A1"]
    assert f.status == "pass" and f.value == pytest.approx(2157, abs=1) and f.limit == 2500.0
    assert f.inputs["autonomy_min"] >= 5
    ups = next(e for e in m.equipment if e.id == "UPS-B2")
    bad = _eq(m, "UPS-B2", rating=2000.0, params={**ups.params, "modules": 4.0})
    assert _by_id(run_rules(scn, bad, None, only=["R07"]))["R07:UPS-B2"].status == "fail"
    short = _param(m, "UPS-A3", "autonomy_min_full_load", 4.0)
    assert _by_id(run_rules(scn, short, None, only=["R07"]))["R07:UPS-A3"].status == "fail"
