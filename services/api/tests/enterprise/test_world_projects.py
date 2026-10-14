import json

import numpy as np
import pytest

from kirchhoff.contracts import Finding, Project, ProjectBundle
from kirchhoff.contracts.extra import FixCandidate
from kirchhoff.enterprise.world.docs import boq_csv_bytes, summary_pdf
from kirchhoff.enterprise.world.enterprise_data import MaterialsErp, build_materials, hall_a_materials
from kirchhoff.enterprise.world.jsonable import jsonable
from kirchhoff.enterprise.world.projects import (asset_bundle, choose_fix, datahall_bundle, pr_id_seq,
                                                 project_record)

HALL_A = Project(id="hall-a", name="Deccan AI Campus · Hall A", client="Deccan Compute", asset_pack="datahall",
                 state="signed", sample=True, updated_at=0.0)


def _cand(cid, cost, **metrics):
    return FixCandidate(id=cid, finding_id="x", label=cid, cost_delta=cost, metrics=metrics, patch={})


def test_choose_fix_follows_p2_ruling_r23():
    r05 = Finding(id="R05:FA-01", rule_id="R05", element_id="FA-01", status="fail", title="dv")
    upsize = _cand("FA-01:upsize-BW-2000", 11480.0, dv_pct=1.66, dv_limit_pct=2.0)
    cable = _cand("FA-01:cable-CBL-240-8P", 26900.0, dv_pct=0.84, dv_limit_pct=2.0)
    assert choose_fix(r05, [upsize, cable])[0].id == cable.id  # 1.16/26900 > 0.34/11480 per dollar
    r11 = Finding(id="R11:H-Z2", rule_id="R11", element_id="H-Z2", status="fail", title="pipe")
    drop = _cand("H-Z2:local-drop", 420.0, changed_pipes=1)
    reroute = _cand("H-Z2:reroute", -910.0, changed_pipes=2)
    assert choose_fix(r11, [reroute, drop])[0].id == drop.id and choose_fix(r11, [reroute, drop])[2] == "cooling"
    r15 = Finding(id="R15:TX-2500", rule_id="R15", element_id="TX-2500", status="fail", title="lead")
    assert choose_fix(r15, [_cand("b", 5.0), _cand("a", 5.0), _cand("c", 9.0)])[0].id == "a"


def test_datahall_bundle_on_the_stub_engine(stub_engine, small_seed):
    b = datahall_bundle(stub_engine, {}, MaterialsErp(small_seed.materials), project=HALL_A, topology="2N",
                        signed_at=1000.0, pr_ids=pr_id_seq(142), opportunity_id="opp-hall-a", what_ifs=True)
    assert [(r.id, r.parent, r.status) for r in b.revisions] == [("r1", None, "checked"), ("r2", "r1", "signed")]
    assert all(r.model is not None and r.model_url is None and r.hash == stub_engine.model_hash(r.model)
               for r in b.revisions)
    fail = [f for f in b.findings["r1"] if f.status == "fail"]
    assert [f.id for f in fail] == ["R05:FA-01"]
    assert fail[0].fix["candidate"] == "FA-01:cable-CBL-240-8P" and fail[0].fix["agent"] == "power"
    assert fail[0].rejected_fix["candidate"] == "FA-01:upsize-BW-2000"
    assert b.revisions[1].check_summary["fail"] == 0
    a = b.approvals[0]
    assert (a.revision, a.approver_name, a.role, a.ts) == ("r2", "Priya Raman", "Lead Electrical Engineer (Reviewer)", 1000.0)
    assert [p.id for p in b.prs] == ["PR-2026-0142", "PR-2026-0143"] and {p.revision for p in b.prs} == {"r2"}
    assert [w.revision_ref for w in b.what_ifs] == ["seed:hall-a@r2"] * 5
    assert b.crm.opportunity_id == "opp-hall-a" and b.crm.stage == "Design approved"
    assert ProjectBundle.model_validate_json(b.model_dump_json()) == b


def test_datahall_bundle_is_deterministic(stub_engine, small_seed):
    def build():
        return datahall_bundle(stub_engine, {}, MaterialsErp(small_seed.materials), project=HALL_A, topology="2N",
                               signed_at=1000.0, pr_ids=pr_id_seq(142)).model_dump_json()
    assert build() == build()


def test_asset_bundle_carries_the_tool_result_event():
    finding = Finding(id="G01:L1", rule_id="G01", element_id="L1", status="pass", title="Ampacity")
    result = {"options": [{"id": "ACSR-ZEBRA", "_tables": [1]}], "recommended": "ACSR-ZEBRA", "findings": [finding],
              "geometry": {"route": [(0.0, 0.0), (1.0, np.float64(2.0))]}}
    project = HALL_A.model_copy(update={"id": "grid-132kv", "asset_pack": "grid", "state": "checked"})
    b = asset_bundle(project, "grid", result, at=1000.0)
    assert [e.kind for e in b.events] == ["tool_call", "tool_result", "message"]
    ev = [e for e in b.events if e.kind == "tool_result"][-1]
    assert (ev.agent, ev.payload["tool"], ev.step) == ("asset", "evaluate_grid", "asset.evaluate")
    summary = ev.payload["summary"]
    assert summary["recommended"] == "ACSR-ZEBRA" and "_tables" not in summary["options"][0]
    assert summary["findings"][0]["rule_id"] == "G01" and summary["geometry"]["route"] == [[0.0, 0.0], [1.0, 2.0]]
    assert summary["choice"] == {"option": "ACSR-ZEBRA", "reason": b.events[-1].title, "source": "engine"}
    assert (b.steps[0].id, b.steps[0].attempt, b.steps[0].status) == (ev.step, ev.attempt, "done")
    json.dumps(b.model_dump(mode="json"))


def test_jsonable_handles_numpy_and_non_finite_values():
    assert jsonable({"a": np.int64(3), "b": float("nan"), "c": (1, 2), "_x": 1, "d": True}) == \
        {"a": 3, "b": None, "c": [1, 2], "d": True}


def test_documents_are_deterministic_and_labelled():
    a = summary_pdf("Pune Edge Phase 1", "Konkan Cloud · signed", [("Topology", "DR"), ("Checks", "149 pass")])
    assert a == summary_pdf("Pune Edge Phase 1", "Konkan Cloud · signed", [("Topology", "DR"), ("Checks", "149 pass")])
    assert a.startswith(b"%PDF")
    from kirchhoff.contracts import PRLine
    csv = boq_csv_bytes([PRLine(material_id="TX-3150", description="t", qty=6, unit_price=118000.0, lead_time_weeks=12)])
    assert csv.decode().splitlines() == ["material_id,description,qty,unit_price_usd,line_total_usd,lead_time_weeks",
                                         "TX-3150,t,6,118000.00,708000.00,12"]


def test_real_engine_hall_a_and_pune(world_cfg, scenarios_root):
    api = pytest.importorskip("kirchhoff.engine.api")
    if not hasattr(api, "fix_candidates"):
        pytest.skip("WS1 fix candidates not landed yet")
    erp = MaterialsErp(build_materials(world_cfg, hall_a_materials(scenarios_root)))
    scn = api.load_scenario("hall_a", scenarios_root)
    ha = datahall_bundle(api, scn, erp, project=project_record(world_cfg, "hall-a"), topology="2N",
                         signed_at=world_cfg.ts(3) - 300.0, pr_ids=pr_id_seq(142), opportunity_id="opp-hall-a")
    assert sorted(f.id for f in ha.findings["r1"] if f.status == "fail") == ["R05:FA-01", "R11:H-Z2"]
    assert {f.id: f.fix["candidate"] for f in ha.findings["r1"] if f.fix}["R11:H-Z2"] == "H-Z2:local-drop"
    assert ha.revisions[-1].status == "signed" and ha.revisions[-1].check_summary["fail"] == 0
    lines = api.derive_pr_lines(scn, ha.revisions[-1].model, erp)
    assert sorted((x.material_id, x.qty) for p in ha.prs for x in p.lines) == sorted((x.material_id, x.qty) for x in lines)
    pune = datahall_bundle(api, scn, erp, project=project_record(world_cfg, "pune-edge-1"), topology="DR",
                           signed_at=world_cfg.ts(14) - 300.0, pr_ids=pr_id_seq(121))
    assert pune.revisions[-1].status == "signed" and pune.revisions[0].model.topology == "DR"


def test_real_grid_and_solar_bundles(world_cfg, scenarios_root):
    grid = pytest.importorskip("kirchhoff.engine.grid")
    solar = pytest.importorskip("kirchhoff.engine.solar")
    g = asset_bundle(project_record(world_cfg, "grid-132kv"), "grid", grid.evaluate_grid(scenarios_root / "grid"), 1.0)
    s = asset_bundle(project_record(world_cfg, "solar-5mwp"), "solar", solar.evaluate_solar(scenarios_root / "solar"), 1.0)
    for b in (g, s):
        summary = [e for e in b.events if e.kind == "tool_result"][-1].payload["summary"]
        assert summary["recommended"] and summary["options"] and summary["choice"]["source"] == "engine"
        assert json.dumps(summary)
