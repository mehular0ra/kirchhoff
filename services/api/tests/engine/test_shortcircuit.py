import pytest

from kirchhoff.engine.shortcircuit import short_circuit


def test_fault_level_2500_kva(scn, models):
    res = short_circuit(scn, models[("2N", "TX-2500")])
    assert res.ikss_ka["A1"] == pytest.approx(61, abs=8)  # hand estimate ≈ 61 kA; pandapower is authoritative
    assert res.ikss_ka["CB-A1"] == pytest.approx(res.ikss_ka["A1"])  # UPS bypass closed (worst case)


def test_fault_level_3150_kva(scn, models):
    res = short_circuit(scn, models[("2N", "TX-3150")])
    assert res.ikss_ka["A1"] == pytest.approx(66, abs=8)
    assert res.ikss_ka["A1"] > short_circuit(scn, models[("2N", "TX-2500")]).ikss_ka["A1"]
    assert res.ip_ka["CB-A1"] <= 187.0  # busway ipk
    assert res.ikss_ka["CB-A1"] <= 85.0  # busway Icw
    assert res.ikss_ka["end:A-01"] < res.ikss_ka["CB-A1"]  # 82 m of busway limits the far end


def test_block_sts_buses_and_cache(scn, models):
    m = models[("BLOCK", "TX-3150")]
    first = short_circuit(scn, m)
    assert first.ikss_ka["STS-01"] == pytest.approx(first.ikss_ka["CB-KR"])
    assert short_circuit(scn, m) is first  # cached by equipment + connections
