import pytest

from kirchhoff.engine.redundancy import build_graph, study
from kirchhoff.engine.topology import busway_sources, systems

ROWS = ["R1", "R2", "R3", "R4", "R5", "R6"]


def test_busway_mappings():
    two_n = busway_sources("2N", ROWS)
    assert (two_n["A-01"], two_n["A-02"], two_n["A-03"], two_n["B-06"]) == ("A1", "A1", "A2", "B3")
    dr = busway_sources("DR", ROWS)
    assert [(dr[f"A-0{n}"], dr[f"B-0{n}"]) for n in range(1, 7)] == [
        ("S1", "S2"), ("S1", "S3"), ("S1", "S4"), ("S2", "S3"), ("S2", "S4"), ("S3", "S4")]
    blk = busway_sources("BLOCK", ROWS)
    assert blk["A-05"] == "K3" and {blk[f"B-0{n}"] for n in range(1, 7)} == {"KR"}
    assert systems("DR") == [("S1", "A"), ("S2", "A"), ("S3", "B"), ("S4", "B")]


def test_2n_structure(models):
    m = models[("2N", "TX-3150")]
    kinds = [e.kind for e in m.equipment]
    assert kinds.count("transformer") == 6 and kinds.count("busway") == 12 and kinds.count("critical_board") == 6
    eq = {e.id: e for e in m.equipment}
    assert eq["T-A1"].params["uk_pct"] == 7.0 and eq["A1"].params["brk.incomer"] == "ACB-5000"
    assert eq["UPS-A1"].params["modules"] == 5.0 and eq["UPS-A1"].rating == 2500.0
    assert eq["CB-A1"].params["brk.FA-01"] == "ACB-1600" and eq["CB-A1"].params["brk.FA-01.in_a"] == 1600.0
    assert eq["A-01"].params["x0"] == 5.7 and eq["B-01"].params["x0"] == 6.3
    feeders = {c.id: c for c in m.connections if c.id.startswith("F")}
    assert len(feeders) == 12 and feeders["FA-01"].length_m == 82.0 and feeders["FA-01"].src == "CB-A1"
    pumps = sorted((c.dst, c.src) for c in m.connections if c.id.startswith("PF-CDU-1-"))
    assert pumps == [("CDU-1", "CB-A1"), ("CDU-1", "CB-B1")]
    assert m.loads == {"rack_kw": 132.0, "liquid_fraction": 0.8, "aux_mw": 0.3, "pumps_kw": 135.0}
    lv_a1_on_2500 = next(e for e in models[("2N", "TX-2500")].equipment if e.id == "A1")
    assert lv_a1_on_2500.params["brk.incomer"] == "ACB-4000"


def test_block_uses_sts(models):
    m = models[("BLOCK", "TX-3150")]
    sts = [e for e in m.equipment if e.kind == "sts"]
    assert len(sts) == 6 and all(e.system == "KR" for e in sts)
    fb = next(c for c in m.connections if c.id == "FB-03")
    assert fb.src == "STS-03" and "CB-KR" in build_graph(m).predecessors("STS-03")


@pytest.mark.parametrize("topo,tx,normal,failover", [
    ("2N", "TX-2500", 48, 96), ("2N", "TX-3150", 38, 76), ("DR", "TX-2500", 72, 96), ("DR", "TX-3150", 57, 76),
    ("BLOCK", "TX-2500", 96, 96), ("BLOCK", "TX-3150", 76, 76)])
def test_transformer_loading_matches_spec(scn, models, topo, tx, normal, failover):
    m = models[(topo, tx)]
    st = study(scn, m)
    rating = 2500.0 if tx == "TX-2500" else 3150.0
    worst_normal = max(st.kva_normal(s) for s in st.systems) / rating * 100
    worst_n1 = max(st.kva_n1(s) for s in st.systems) / rating * 100
    assert worst_normal == pytest.approx(normal, abs=0.6)
    assert worst_n1 == pytest.approx(failover, abs=0.6)


def test_2n_board_failover_and_busway_currents(scn, models):
    st = study(scn, models[("2N", "TX-3150")])
    assert st.kva_n1("A1") == pytest.approx(2399, abs=1)
    assert st.normal.busway_a["A-01"] == pytest.approx(773, rel=0.01)
    assert st.worst_busway_a("A-01") == pytest.approx(1546, rel=0.01)
    assert st.ups_kw_max("A1") == pytest.approx(2157, abs=1)  # ≈ 2.16 MW -> 5 x 500 kW modules
    assert st.normal.system_aux_kw["A1"] == pytest.approx(50.0)
    loss_a1 = next(c for c in st.cases if c.failed == "T-A1")
    assert loss_a1.system_aux_kw["B1"] == pytest.approx(100.0) and loss_a1.system_it_kw["A1"] == 0.0
    assert st.spofs == []


def test_dr_partner_takes_one_extra_half_row(scn, models):
    st = study(scn, models[("DR", "TX-3150")])
    case = next(c for c in st.cases if c.failed == "UPS-S1")
    assert {s: round(case.system_it_kw[s]) for s in ("S2", "S3", "S4")} == {"S2": 2112, "S3": 2112, "S4": 2112}
    assert case.system_aux_kw["S2"] == pytest.approx(100.0)


def test_spof_detected_when_rack_fed_twice_from_one_busway(scn, models):
    m = models[("2N", "TX-3150")]
    racks = [r.model_copy(update={"feeds": ("A-02", "A-02")}) if r.id == "R2-03" else r for r in m.racks]
    st = study(scn, m.model_copy(update={"racks": racks}))
    assert "A-02" in st.spofs and "T-A1" in st.spofs and "B-02" not in st.spofs
