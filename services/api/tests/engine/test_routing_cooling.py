import pytest

from kirchhoff.contracts import DesignModel
from kirchhoff.engine.cooling import (build_pipes, index_dp_kpa, pipe_velocity_ms, rack_required_flow_lps,
                                      select_dn, size_cooling)
from kirchhoff.engine.layout import build_geometry
from kirchhoff.engine.routing import feeder_length_m, feeder_routes

TWO_N = [(f"FA-0{n}", f"A-0{n}", "A") for n in range(1, 7)] + [(f"FB-0{n}", f"B-0{n}", "B") for n in range(1, 7)]


def test_feeder_bundles_and_lengths_2n(scn):
    routes = feeder_routes(scn, TWO_N)
    bundle_y = {fid: pts[1][1] for fid, pts in routes.items() if len(pts) > 2}
    assert [bundle_y[f"FA-0{n}"] for n in range(1, 6)] == [2.0, 2.4, 2.8, 3.2, 3.6]
    assert routes["FA-06"][0] == (66.0, 4.0, 3.2) and routes["FA-06"][1] == (46.0, 4.0, 3.2)  # y 4.0 = exit
    assert (bundle_y["FB-01"], bundle_y["FB-02"], bundle_y["FB-03"]) == (35.0, 34.6, 34.2)
    assert (bundle_y["FB-06"], bundle_y["FB-05"], bundle_y["FB-04"]) == (35.0, 34.6, 34.2)
    lengths = {fid: feeder_length_m(scn, pts) for fid, pts in routes.items()}
    assert lengths["FA-01"] == pytest.approx(82.0)
    assert lengths["FA-02"] == pytest.approx(65.2)  # 66 m in spec §9.6 predates the 0.4 m bundle pitch
    assert lengths["FB-01"] == pytest.approx(50.0) and lengths["FB-03"] == pytest.approx(28.0)
    assert routes["FA-01"][-1] == (6.0, 15.6, 3.2) and routes["FB-03"][-1] == (28.0, 20.4, 3.2)


def test_feeders_route_from_their_source_room_dr(scn):
    dr = [("FA-01", "A-01", "A"), ("FB-01", "B-01", "A"), ("FA-02", "A-02", "A"), ("FA-03", "A-03", "A"),
          ("FA-04", "A-04", "A"), ("FA-05", "A-05", "A"), ("FB-02", "B-02", "B"), ("FB-03", "B-03", "B"),
          ("FA-06", "A-06", "B"), ("FB-04", "B-04", "B"), ("FB-05", "B-05", "B"), ("FB-06", "B-06", "B")]
    routes = feeder_routes(scn, dr)
    assert routes["FB-01"][1][1] == 2.4  # room-A system feeding a B busway: south corridor, second bundle slot
    assert feeder_length_m(scn, routes["FB-01"]) == pytest.approx(81.2)
    assert routes["FA-06"][-1] == (46.0, 20.4, 3.2) and feeder_length_m(scn, routes["FA-06"]) == pytest.approx(42.0)


def test_size_cooling_n_plus_one(scn, racks):
    nodes = size_cooling(scn, racks)
    cdus = [n for n in nodes if n.kind == "cdu"]
    assert [c.id for c in cdus] == [f"CDU-{k}" for k in range(1, 10)]
    assert [c.zone for c in cdus] == ["Z1"] * 3 + ["Z2"] * 3 + ["Z3"] * 3
    assert [c.x for c in cdus[3:6]] == [29.4, 31.0, 32.6]
    assert all(c.capacity_kw == 1200.0 for c in cdus)
    assert [n.id for n in nodes if n.kind == "manifold"] == [f"M-R{k}" for k in range(1, 7)]


def _cooling_model(scn, racks) -> DesignModel:
    m = DesignModel(topology="2N", racks=racks, equipment=[], connections=[], cooling_nodes=size_cooling(scn, racks),
                    pipes=[], geometry=build_geometry(scn), loads={})
    return m.model_copy(update={"pipes": build_pipes(scn, m)})


def test_pipes_flows_sizes_and_index_dp(scn, racks):
    m = _cooling_model(scn, racks)
    assert rack_required_flow_lps(scn, racks[0]) * 60 == pytest.approx(157, abs=0.5)
    pipes = {p.id: p for p in m.pipes}
    assert (pipes["H-Z2"].dn, pipes["BR-R3"].dn) == (200, 150)
    assert (pipes["H-Z2"].tier, pipes["BR-R3"].tier) == ("pipe_high", "pipe_low")
    assert pipe_velocity_ms(scn, pipes["H-Z1"]) == pytest.approx(1.26, abs=0.01)
    assert pipe_velocity_ms(scn, pipes["BR-R1"]) == pytest.approx(1.13, abs=0.01)
    assert select_dn(scn, 41.94) == 200 and select_dn(scn, 20.97) == 150
    dps = {z: index_dp_kpa(scn, m, z)[0] for z in ("Z1", "Z2", "Z3")}
    assert max(dps.values()) == pytest.approx(70, abs=3)  # spec §9.6: index Δp ≈ 70 kPa
    assert index_dp_kpa(scn, m, "Z1")[1:] == ("H-Z1", "BR-R1")
    assert all(v <= 150 for v in dps.values())
