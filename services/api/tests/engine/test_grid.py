import pytest

from kirchhoff.engine.grid import evaluate_grid


def test_grid_pack_compares_three_conductors():
    res = evaluate_grid()
    assert set(res) == {"options", "recommended", "findings", "geometry"}
    opts = {o["id"]: o for o in res["options"]}
    assert set(opts) == {"ACSR-DOG", "ACSR-PANTHER", "ACSR-ZEBRA"}
    assert opts["ACSR-DOG"]["ampacity_ok"] is False  # 437 A on one circuit > 300 A
    assert opts["ACSR-PANTHER"]["passes"] and opts["ACSR-ZEBRA"]["passes"]
    assert opts["ACSR-PANTHER"]["capex_usd"] < opts["ACSR-ZEBRA"]["capex_usd"]
    assert res["recommended"] == "ACSR-ZEBRA"  # lower losses win on 10-year lifecycle cost
    assert res["geometry"]["length_km"] == pytest.approx(18.1, abs=0.2)


def test_grid_findings_and_fault_levels():
    res = evaluate_grid()
    f = {x.id: x for x in res["findings"]}
    assert set(f) == {"G01:L-132", "G02:L-132", "G03:SS-132", "G04:SS-33"}
    assert all(x.status == "pass" for x in f.values())
    assert f["G01:L-132"].value == pytest.approx(437.4, abs=0.5)
    assert 5.0 < f["G03:SS-132"].value < 31.5 and 5.0 < f["G04:SS-33"].value < 25.0
    assert f["G03:SS-132"].clause_refs[0].standard == "IEC 60909-0"
