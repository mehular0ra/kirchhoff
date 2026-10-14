import pytest

from kirchhoff.engine.solar import clear_sky_kwh_per_kwp, evaluate_solar, string_voltages


def test_string_voltages_against_inverter_limits():
    import yaml

    from kirchhoff.engine.scenario import scenarios_root

    cfg = yaml.safe_load((scenarios_root() / "solar" / "solar.yaml").read_text())
    voc28, vmp28 = string_voltages(cfg, 28)
    assert voc28 == pytest.approx(28 * 49.9 * (1 + 0.0028 * 17), rel=1e-6)
    assert voc28 < 1500 < string_voltages(cfg, 30)[0]
    assert vmp28 > 880


def test_solar_pack_recommends_longest_compliant_string():
    res = evaluate_solar()
    assert set(res) == {"options", "recommended", "findings", "geometry"}
    opts = {o["id"]: o for o in res["options"]}
    assert opts["STR-30"]["voc_ok"] is False
    assert res["recommended"] == "STR-28"
    assert opts["STR-28"]["dc_kwp"] == pytest.approx(5000, rel=0.05)
    assert len(res["geometry"]["tables"]) == opts["STR-28"]["strings"]
    assert all(f.status == "pass" for f in res["findings"])
    assert {f.rule_id for f in res["findings"]} == {"S01", "S02", "S03", "S04"}


def test_clear_sky_yield_is_plausible():
    y = clear_sky_kwh_per_kwp(17.4, 17.4, 0.2)
    assert 2000 < y < 3000  # clear-sky upper bound, kWh/kWp/yr before PR
