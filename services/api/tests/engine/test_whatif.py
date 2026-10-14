import time

import pytest

from kirchhoff.engine import api
from kirchhoff.engine.benchmark import golden_fixed


@pytest.fixture(scope="module")
def signed(scn, erp):
    return golden_fixed(scn, erp)


def test_what_if_200_kw(scn, erp, signed):
    t = time.perf_counter()
    res = api.what_if(scn, signed, "rack_kw", 200.0, "seed:hall-a@r2", erp)
    assert time.perf_counter() - t < 3.0
    assert res.revision_ref == "seed:hall-a@r2" and res.param == "rack_kw" and res.value == 200.0
    rules = {f.rule_id for f in res.findings}
    assert {"R01", "R02", "R08"} <= rules
    assert all(f.status in ("fail", "warn") for f in res.findings)
    assert ["R1-01", "A-01", "FA-01", "CB-A1", "UPS-A1", "A1", "T-A1"] in res.impact_chain
    assert ["R1-01", "M-R1", "BR-R1", "H-Z1", "Z1", "CDU-1", "CDU-2", "CDU-3"] in res.impact_chain


def test_what_if_freezes_equipment_and_does_not_mutate(scn, erp, signed):
    before = api.model_hash(signed)
    api.what_if(scn, signed, "liquid_fraction", 0.9, "ws:r2", erp)
    assert api.model_hash(signed) == before
    res = api.what_if(scn, signed, "liquid_fraction", 0.9, "ws:r2", erp)
    assert {f.rule_id for f in res.findings} == {"R09"}  # frozen flows no longer meet ΔT at 90% liquid
    assert ["R1-01", "M-R1"] in res.impact_chain


def test_limit_what_ifs(scn, erp, signed):
    dv = api.what_if(scn, signed, "dv_limit_pct", 1.5, "ws:r2", erp)
    assert {f.id for f in dv.findings} == {"R05:FA-01", "R05:FA-02", "R05:FA-03"}
    cap = api.what_if(scn, signed, "tx_loading_cap_pct", 35.0, "ws:r2", erp)
    assert {f.rule_id for f in cap.findings} == {"R01"} and len(cap.findings) == 6
    assert api.what_if(scn, signed, "rack_kw", 132.0, "ws:r2", erp).findings == []


def test_what_if_rejects_bad_input(scn, erp, signed):
    with pytest.raises(ValueError):
        api.what_if(scn, signed, "rack_height", 2.0, "ws:r2", erp)
    with pytest.raises(ValueError):
        api.what_if(scn, signed, "liquid_fraction", 1.5, "ws:r2", erp)


def test_chip_what_ifs_precomputed(scn, erp, signed):
    results = api.chip_what_ifs(scn, signed, erp, "seed:hall-a@r2")
    assert [(r.param, r.value) for r in results] == api.CHIP_WHAT_IFS
    assert results[0].param == "rack_kw" and results[0].value == 200.0
    assert all(r.revision_ref == "seed:hall-a@r2" for r in results)
