import math

import pytest

from kirchhoff.contracts.extra import ClashReport, FixCandidate
from kirchhoff.engine.erp import YamlErp, default_erp, effective_lead_weeks
from kirchhoff.engine.scenario import (LABEL, cat_item, clause, limit, load_scenario, scenarios_root,
                                       with_limit)


def test_tender_has_numbered_clauses_and_limits(scn):
    ids = [c["id"] for c in scn.tender["clauses"]]
    for cid in ["§2.3", "§3.1", "§4.2", "§4.3", "§4.5", "§4.6", "§6.1", "§6.2", "§6.3.4", "§6.4", "§6.5", "App. B"]:
        assert cid in ids, cid
    assert limit(scn, "max_lead_time_weeks") == 26
    assert limit(scn, "dv_max_pct") == 2.0
    assert (limit(scn, "tx_normal_max_pct"), limit(scn, "tx_n1_max_pct")) == (80, 100)
    assert clause(scn, "§4.6")["page"] == 4


def test_tender_contradiction_is_present(scn):
    assert "2N" in clause(scn, "§4.2")["text"]
    assert "Block or distributed redundancy acceptable" in clause(scn, "App. B")["text"]


def test_every_quote_is_verbatim(scn):
    for c in scn.tender["clauses"]:
        assert c["quote"] in " ".join(c["text"].split()), c["id"]
    assert "26 weeks" in clause(scn, "§2.3")["quote"]
    assert "2.0%" in clause(scn, "§4.6")["quote"]


def test_labels(scn):
    assert LABEL == "IEC-based, illustrative, not for construction"
    assert scn.catalogue["label"] == LABEL and scn.geometry["label"] == LABEL
    assert LABEL in scn.tender["notice"]


def test_geometry_pins(scn):
    g = scn.geometry
    assert g["hall"] == [0.0, 0.0, 60.0, 36.0]
    assert len(g["columns"]["xs"]) * len(g["columns"]["ys"]) == 24
    assert [r["x"] for r in g["rows"]] == [6.0, 22.0, 28.0, 34.0, 40.0, 46.0]
    assert g["keepouts"][0]["rect"] == [10.0, 10.0, 18.0, 26.0]
    assert g["rooms"]["A"]["exit"] == [66.0, 4.0] and g["rooms"]["B"]["exit"] == [30.0, 40.0]
    assert (g["busways"]["offset_a"], g["busways"]["offset_b"]) == (-0.3, 0.3)
    assert g["corridors"]["south"]["y_outer"] == 2.0 and g["corridors"]["north"]["y_outer"] == 35.0
    assert g["zones"]["Z2"]["bay"] == [28.6, 28.0, 33.4, 33.0]
    assert g["tiers"] == {"pipe_low": 2.6, "busway": 3.2, "pipe_high": 3.8}
    assert set(g["pipes"]["headers"]) == {"H-Z1", "H-Z2", "H-Z3"}
    assert "reroutes" in g and "H-Z2" in g["reroutes"]


def test_catalogue_values(scn):
    pf, sin = 0.95, math.sqrt(1 - 0.95 ** 2)
    bw16, bw20 = cat_item(scn, "BW-1600"), cat_item(scn, "BW-2000")
    assert bw16["r_mohm_m"] * pf + bw16["x_mohm_m"] * sin == pytest.approx(0.0395, abs=0.0005)
    assert bw20["r_mohm_m"] * pf + bw20["x_mohm_m"] * sin == pytest.approx(0.030, abs=0.0005)
    assert (cat_item(scn, "TX-2500")["uk_pct"], cat_item(scn, "TX-3150")["uk_pct"]) == (6.0, 7.0)
    assert cat_item(scn, "CBL-240-8P")["conductors_per_phase"] == 8
    assert cat_item(scn, "CDU-1200")["head_kpa"] == 150
    assert (cat_item(scn, "PIPE-DN150")["id_mm"], cat_item(scn, "PIPE-DN200")["id_mm"]) == (154.0, 206.0)


def test_erp_seed_generator_constraint(scn, erp):
    assert (erp.get("TX-2500").stock, erp.get("TX-2500").lead_time_weeks) == (0, 98)
    assert erp.get("TX-3150").stock == 6
    for m in erp.all():
        if m.id != "TX-2500":
            assert m.lead_time_weeks <= 26, m.id
        assert cat_item(scn, m.id)["unit_price"] == m.unit_price, m.id
    assert all(m.stock > 0 for m in erp.search("breaker"))
    assert effective_lead_weeks(erp.get("TX-3150"), 6) == 0
    assert effective_lead_weeks(erp.get("TX-3150"), 7) == 12


def test_scenarios_root_env(monkeypatch, tmp_path):
    monkeypatch.setenv("KIRCHHOFF_SCENARIOS_DIR", str(tmp_path))
    assert scenarios_root() == tmp_path
    monkeypatch.delenv("KIRCHHOFF_SCENARIOS_DIR")
    assert (scenarios_root() / "hall_a" / "tender.yaml").exists()
    assert isinstance(default_erp(), YamlErp)


def test_with_limit_copies(scn):
    s2 = with_limit(scn, "dv_max_pct", 1.5)
    assert limit(s2, "dv_max_pct") == 1.5 and limit(scn, "dv_max_pct") == 2.0
    assert load_scenario().tender == scn.tender


def test_extra_contracts_round_trip():
    c = FixCandidate(id="FA-01:upsize-BW-2000", finding_id="R05:FA-01", label="Upsize FA-01 to 2,000 A busway",
                     cost_delta=11480.0, metrics={"dv_pct": 1.66}, patch={"op": "set_feeder"})
    assert FixCandidate.model_validate_json(c.model_dump_json()) == c
    r = ClashReport(clashes=[{"a": "H-Z2", "b": "FB-03", "kind": "solid", "at": [28.0, 24.0, 3.8]}])
    assert ClashReport.model_validate_json(r.model_dump_json()) == r
