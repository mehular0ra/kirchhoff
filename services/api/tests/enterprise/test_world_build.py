import json

import pytest
from .ws4_fakes import RID, UID, make_hall_b_workspace

from kirchhoff.contracts import Material, Opportunity, Project, ProjectBundle, PurchaseRequisition
from kirchhoff.enterprise.capture import export_run
from kirchhoff.enterprise.model import EnterpriseSeed
from kirchhoff.enterprise.world.build import DEMO, OUT, build_world, diff_on_disk, write_world

PROJECT_KEYS = set(Project.model_fields)


def _json(build, rel):
    return json.loads(build.files[rel])


def test_world_json_has_exactly_the_p3_world_shape(world_cfg, scenarios_root):
    world = _json(build_world(world_cfg, scenarios_root=scenarios_root), f"{DEMO}/world.json")
    assert set(world) == {"org", "people", "projects", "activity"}
    assert world["org"] == {"name": "Meridian Power Engineering", "tagline": "Data-centre and grid EPC contractor"}
    assert [p["name"] for p in world["people"]] == ["Priya Raman", "Arjun Mehta", "Kavya Iyer", "Rohan Das", "Neha Kapoor"]
    assert all(set(p) <= {"id", "name", "role", "initials"} for p in world["people"])
    assert [p["id"] for p in world["projects"]] == ["hall-a", "hall-b", "pune-edge-1", "grid-132kv", "solar-5mwp",
                                                    "vindhya-lv"]
    assert all(set(p) == PROJECT_KEYS for p in world["projects"])
    states = {p["id"]: p["state"] for p in world["projects"]}
    assert states["hall-a"] == "signed" and states["hall-b"] == "not_started" and states["vindhya-lv"] == "archived"
    acts = world["activity"]
    assert acts and all(set(a) <= {"id", "ts", "actor", "project_id", "text"} for a in acts)
    assert [a["ts"] for a in acts] == sorted((a["ts"] for a in acts), reverse=True)
    assert all(world_cfg.now - 45 * 86400 <= a["ts"] <= world_cfg.now for a in acts)


def test_integrations_json_has_exactly_the_p3_snapshot_shape(world_cfg, scenarios_root):
    snap = _json(build_world(world_cfg, scenarios_root=scenarios_root), f"{DEMO}/integrations.json")
    assert set(snap) == {"synced_at", "erp", "crm", "documents", "notifications"} and snap["synced_at"] == world_cfg.now
    assert set(snap["erp"]) == {"materials", "prs"} and set(snap["crm"]) == {"opportunities"}
    assert len([Material.model_validate(m) for m in snap["erp"]["materials"]]) == 60
    prs = [PurchaseRequisition.model_validate(p) for p in snap["erp"]["prs"]]
    assert [p.created_at for p in prs] == sorted((p.created_at for p in prs), reverse=True)
    assert len([Opportunity.model_validate(o) for o in snap["crm"]["opportunities"]]) == 9
    for d in snap["documents"]:
        assert set(d) == {"id", "project_id", "name", "kind", "url", "updated_at"}
        assert d["url"] in (f"/demo/docs/{d['name']}", f"/demo/files/{d['project_id']}/{d['name']}")
    assert all(set(n) <= {"id", "ts", "kind", "title", "body", "project_id"} for n in snap["notifications"])


def test_world_is_deterministic_and_seed_sensitive(world_cfg, scenarios_root):
    a = build_world(world_cfg, scenarios_root=scenarios_root)
    assert a.digest() == build_world(world_cfg, scenarios_root=scenarios_root).digest()
    other = world_cfg.model_copy(update={"seed": world_cfg.seed + 1})
    assert build_world(other, scenarios_root=scenarios_root).digest() != a.digest()
    manifest = json.loads(a.files[f"{OUT}/manifest.json"])
    assert manifest["digest"] == a.digest() and f"{DEMO}/world.json" in manifest["files"]


def test_captured_hall_a_drives_the_erp_prs_deterministically(world_cfg, scenarios_root, stub_engine):
    raw = export_run(*make_hall_b_workspace(stub_engine), UID, RID)

    def build():
        return build_world(world_cfg, scenarios_root=scenarios_root, engine=stub_engine, captures={"hall-a": raw},
                           engine_projects=False)

    a, b = build(), build()
    for rel in (f"{DEMO}/projects/hall-a.json", f"{DEMO}/integrations.json", f"{OUT}/enterprise_seed.json"):
        assert a.files[rel] == b.files[rel], rel  # spec §16 capture determinism
    hall_a = ProjectBundle.model_validate_json(a.files[f"{DEMO}/projects/hall-a.json"])
    ids = [p.id for p in hall_a.prs]
    assert ids == ["PR-2026-0142", "PR-2026-0143"]
    snap = _json(a, f"{DEMO}/integrations.json")
    assert ids == sorted(p["id"] for p in snap["erp"]["prs"] if p["project_id"] == "hall-a")
    seed = EnterpriseSeed.model_validate_json(a.files[f"{OUT}/enterprise_seed.json"])
    assert ids == [p.id for p in seed.prs if p.project_id == "hall-a"]
    assert {f"{DEMO}/files/hall-a/calc-report.pdf", f"{DEMO}/files/hall-a/boq.csv"} <= set(a.files)
    world = _json(a, f"{DEMO}/world.json")
    assert next(p for p in world["projects"] if p["id"] == "hall-a") == hall_a.project.model_dump(mode="json")
    assert any("PR-2026-0142" in act["text"] for act in world["activity"])


def test_write_world_replaces_stale_files_and_detects_drift(world_cfg, scenarios_root, tmp_path):
    build = build_world(world_cfg, scenarios_root=scenarios_root)
    stale = [tmp_path / DEMO / "projects" / "old-project.json", tmp_path / DEMO / "files" / "old" / "x.pdf"]
    for f in stale:
        f.parent.mkdir(parents=True)
        f.write_text("{}", encoding="utf-8")
    write_world(build, tmp_path)
    assert not any(f.exists() for f in stale) and diff_on_disk(build, tmp_path) == []
    (tmp_path / DEMO / "world.json").write_text("{}", encoding="utf-8")
    assert diff_on_disk(build, tmp_path) == [f"{DEMO}/world.json"]


def test_full_world_with_the_real_engine(world_cfg, scenarios_root):
    api = pytest.importorskip("kirchhoff.engine.api")
    if not hasattr(api, "fix_candidates"):
        pytest.skip("WS1 fix candidates not landed yet")
    build = build_world(world_cfg, scenarios_root=scenarios_root, engine=api)
    for pid in ("hall-a", "pune-edge-1", "vindhya-lv"):
        assert f"{DEMO}/projects/{pid}.json" in build.files
    assert f"{DEMO}/files/hall-a/calc-report.pdf" in build.files and f"{DEMO}/files/pune-edge-1/boq.csv" in build.files
    prs = {p["id"]: p["project_id"] for p in _json(build, f"{DEMO}/integrations.json")["erp"]["prs"]}
    assert (prs["PR-2026-0142"], prs["PR-2026-0121"], prs["PR-2026-0101"]) == ("hall-a", "pune-edge-1", "vindhya-lv")
    hall_a = ProjectBundle.model_validate_json(build.files[f"{DEMO}/projects/hall-a.json"])
    assert all(r.model is not None for r in hall_a.revisions)  # P2's seed: what-ifs read the inline models


def test_committed_demo_files_are_valid(scenarios_root):
    """Obligations §3.4: every generated bundle validates strictly; PRs and document links are consistent."""
    demo = scenarios_root.parent / DEMO
    bundles = sorted((demo / "projects").glob("*.json"))
    if not bundles:
        pytest.skip("run `make demo-world` first")
    for path in bundles:
        b = ProjectBundle.model_validate_json(path.read_text(encoding="utf-8"))
        assert b.project.id == path.stem and all(r.model is not None for r in b.revisions)
    assert "hall-b.json" not in {p.name for p in bundles}
    snap = json.loads((demo / "integrations.json").read_text(encoding="utf-8"))
    erp_prs = {p["id"] for p in snap["erp"]["prs"]}
    for pid in ("hall-a", "pune-edge-1"):
        path = demo / "projects" / f"{pid}.json"
        if path.exists():
            assert {p.id for p in ProjectBundle.model_validate_json(path.read_text(encoding="utf-8")).prs} <= erp_prs
    for d in snap["documents"]:
        if d["url"].startswith("/demo/files/"):
            assert (demo / d["url"].removeprefix("/demo/")).is_file(), d["url"]


def test_write_world_never_deletes_outside_the_managed_demo_dirs(world_cfg, scenarios_root, tmp_path):
    """write_world's cleanup must stay inside apps/web/public/demo/{projects,files}/ under the given root."""
    build = build_world(world_cfg, scenarios_root=scenarios_root)
    outside = [
        tmp_path / DEMO / "docs" / "tender-hall-a.pdf",  # owned by WS3, must survive
        tmp_path / "scenarios" / "demo_world" / "out" / "stray.json",
        tmp_path / "some_other_project" / "keep.txt",
    ]
    for f in outside:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("keep me", encoding="utf-8")
    write_world(build, tmp_path)
    for f in outside:
        assert f.exists() and f.read_text(encoding="utf-8") == "keep me", f
