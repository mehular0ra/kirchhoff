import pytest

from kirchhoff.engine import api
from kirchhoff.engine.options import r15_requirement, r15_swap


def test_power_options_minimum_rating_per_topology(options):
    assert list(options) == ["2N", "DR", "BLOCK"]
    two_n, dr, blk = options["2N"][0], options["DR"][0], options["BLOCK"][0]
    assert (two_n.installed_mva, two_n.normal_loading_pct, two_n.failover_loading_pct) == pytest.approx(
        (15.0, 48.0, 96.0), abs=0.5)
    assert (dr.installed_mva, dr.normal_loading_pct, dr.failover_loading_pct) == pytest.approx(
        (10.0, 72.0, 96.0), abs=0.5)
    # block on 2.5 MVA loads 96% in normal operation (fails R01), so it is offered on 3.15 MVA only
    assert (blk.installed_mva, blk.normal_loading_pct, blk.failover_loading_pct) == pytest.approx(
        (12.6, 76.0, 76.0), abs=0.5)
    assert two_n.max_lead_time_weeks == 98 and two_n.spof_count == 0 and two_n.swaps == []
    assert two_n.cost > 0 and two_n.losses_kw > 0


def test_r15_swap_picks_3150_deterministically(scn, erp, options):
    model = options["2N"][1]
    assert r15_requirement(scn, model, "TX-2500") == pytest.approx(2399, abs=1)
    new, rec = r15_swap(scn, model, "TX-2500", erp)
    assert rec["to"] == "TX-3150" and rec["from"] == "TX-2500" and rec["qty"] == 6 and rec["reason"] == "R15"
    assert rec["ikss_ka_before"] == pytest.approx(61, abs=8) and rec["ikss_ka_after"] == pytest.approx(66, abs=8)
    assert {e.catalogue_id for e in new.equipment if e.kind == "transformer"} == {"TX-3150"}
    again = r15_swap(scn, model, "TX-2500", erp)
    assert api.model_hash(again[0]) == api.model_hash(new) and again[1] == rec


def test_annotate_options_applies_swaps(annotated):
    two_n, dr, blk = annotated["2N"][0], annotated["DR"][0], annotated["BLOCK"][0]
    assert two_n.installed_mva == pytest.approx(18.9)
    assert (two_n.normal_loading_pct, two_n.failover_loading_pct) == pytest.approx((38.0, 76.0), abs=0.5)
    assert (dr.installed_mva, dr.normal_loading_pct, dr.failover_loading_pct) == pytest.approx(
        (12.6, 57.0, 76.0), abs=0.5)
    assert [s["to"] for s in two_n.swaps] == ["TX-3150"] and [s["to"] for s in dr.swaps] == ["TX-3150"]
    assert blk.swaps == []
    assert all(o.max_lead_time_weeks <= 26 for o in (two_n, dr, blk))


def test_power_recheck_after_swap(scn, annotated):
    findings = api.power_recheck(scn, annotated["2N"][1])
    assert {f.rule_id for f in findings} == {"R01", "R04", "R04b"}
    assert all(f.status == "pass" for f in findings)


def test_p2_facade(scn, racks, erp, annotated):
    nodes = api.size_cooling(scn, racks)
    assert sum(1 for n in nodes if n.kind == "cdu") == 9
    prs = api.derive_pr_lines(scn, annotated["2N"][1], erp)
    assert {p.material_id for p in prs} >= {"TX-3150", "UPS-500", "BW-1600", "CDU-1200"}
