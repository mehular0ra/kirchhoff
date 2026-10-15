"""Assemble the demo world (spec §13, obligations §3): world.json and integrations.json (P3 `World` /
`IntegrationsSnapshot`), project bundles, documents, the enterprise seed and a manifest. Deterministic (spec §16)."""
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from kirchhoff.contracts import ProjectBundle

from ..capture import BOQ, CALC_REPORT, DOCS_ORDER, TARGETS, CapturedBundle, RawCapture, render_capture_docs, to_static
from .config import WorldConfig
from .docs import boq_csv_bytes, summary_pdf
from .enterprise_data import (MaterialsErp, build_enterprise_seed, build_historical_prs, build_materials,
                              hall_a_materials)
from .feed import activity, notifications, tool_summary
from .projects import archive_bundle, boxed_what_ifs, engine_bundles, project_record

DEMO = "apps/web/public/demo"
OUT = "scenarios/demo_world/out"
MANIFEST = f"{OUT}/manifest.json"
MANAGED_DIRS = (f"{DEMO}/projects", f"{DEMO}/files")
SCENARIO_DOCS = (("tender", "tender-hall-a.pdf"), ("drawing", "hall-a-plan.pdf"))  # WS3 copies them to /demo/docs


@dataclass
class WorldBuild:
    files: dict[str, bytes] = field(default_factory=dict)

    def manifest(self) -> dict[str, str]:
        return {rel: hashlib.sha256(data).hexdigest() for rel, data in sorted(self.files.items()) if rel != MANIFEST}

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.manifest(), sort_keys=True).encode("utf-8")).hexdigest()


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _asset_docs(cfg: WorldConfig, bundles: dict[str, ProjectBundle]) -> dict[str, dict[str, bytes]]:
    out: dict[str, dict[str, bytes]] = {}
    for pid in ("grid-132kv", "solar-5mwp"):
        s = tool_summary(bundles[pid]) if pid in bundles else {}
        if not s:
            continue
        rows = [("Recommended option", str(s.get("recommended"))),
                ("Options compared", ", ".join(str(o.get("id")) for o in s.get("options", []))),
                ("Findings", "; ".join(f"{f.get('rule_id')} {f.get('element_id')}: {f.get('status')}"
                                       for f in s.get("findings", [])) or "none")]
        out[pid] = {"summary.pdf": summary_pdf(cfg.project(pid).name, "Asset-pack evaluation", rows)}
    vindhya = bundles.get("vindhya-lv")
    if vindhya is not None and vindhya.prs:
        out["vindhya-lv"] = {BOQ: boq_csv_bytes([line for p in vindhya.prs for line in p.lines])}
    return out


def _documents(cfg: WorldConfig, bundles: dict[str, ProjectBundle], files_docs: dict[str, dict[str, bytes]],
               scenarios_root: Path) -> list[dict]:
    def updated(pid: str) -> float:
        return bundles[pid].project.updated_at if pid in bundles else cfg.ts(cfg.project(pid).days_ago)

    rows = [(pid, kind, name, f"/demo/docs/{name}") for pid in ("hall-a", "hall-b") for kind, name in SCENARIO_DOCS
            if (scenarios_root / "hall_a" / "out" / name).exists()]
    for pid in sorted(files_docs):
        for name in sorted(files_docs[pid]):
            kind = "boq" if name == BOQ else "calc_report" if name == CALC_REPORT else "summary"
            rows.append((pid, kind, name, f"/demo/files/{pid}/{name}"))
    return [{"id": f"doc-{pid}-{name.rsplit('.', 1)[0]}", "project_id": pid, "name": name, "kind": kind, "url": url,
             "updated_at": updated(pid)} for pid, kind, name, url in rows]


def build_world(cfg: WorldConfig, *, scenarios_root: Path, engine=None, captures: dict[str, RawCapture] | None = None,
                engine_projects: bool = True) -> WorldBuild:
    scenarios_root = Path(scenarios_root)
    captures = dict(captures or {})
    if set(captures) - set(TARGETS):
        raise ValueError(f"no capture target for {sorted(set(captures) - set(TARGETS))}")
    if captures and engine is None:
        raise ValueError("captures need the engine (hashes, chip what-ifs, BOQ)")
    materials = build_materials(cfg, hall_a_materials(scenarios_root))
    erp = MaterialsErp(materials)
    historical = build_historical_prs(cfg, materials)
    if engine is not None and engine_projects:
        bundles = engine_bundles(cfg, engine, scenarios_root, erp, historical)
    else:
        bundles = {"vindhya-lv": archive_bundle(project_record(cfg, "vindhya-lv"),
                                                [p for p in historical if p.project_id == "vindhya-lv"])}
    scn = engine.load_scenario("hall_a", scenarios_root) if engine is not None else None
    files_docs: dict[str, dict[str, bytes]] = {}
    for pid, raw in sorted(captures.items()):
        cap = to_static(raw, engine, scn, erp, target=TARGETS[pid],
                        signed_at=cfg.ts(cfg.project(pid).days_ago) - 300.0)
        tender = scenarios_root / "hall_a" / "out" / "tender-hall-a.pdf"  # the chips come from the engine, unboxed
        bundles[pid] = (cap.bundle.model_copy(update={"what_ifs": boxed_what_ifs(cap.bundle.what_ifs, tender)})
                        if tender.is_file() else cap.bundle)
        files_docs[pid] = render_capture_docs(cap, engine, scn, erp)
    for pid in ("hall-a", "pune-edge-1"):  # engine-built fallbacks
        if pid in bundles and pid not in files_docs:
            b = bundles[pid]
            files_docs[pid] = render_capture_docs(CapturedBundle(bundle=b, docs_order=DOCS_ORDER,
                                                                 docs_summary=b.revisions[-1].summary), engine, scn, erp)
    files_docs.update(_asset_docs(cfg, bundles))
    seed = build_enterprise_seed(cfg, materials,
                                 [p for pid in ("hall-a", "pune-edge-1") if pid in bundles for p in bundles[pid].prs])
    world = {"org": cfg.org.model_dump(exclude_none=True),
             "people": [p.model_dump(exclude_none=True) for p in cfg.people],
             "projects": [(bundles[p.id].project if p.id in bundles else project_record(cfg, p.id)).model_dump(mode="json")
                          for p in cfg.projects],
             "activity": activity(cfg, bundles)}
    integrations = {"synced_at": cfg.now,
                    "erp": {"materials": [m.model_dump(mode="json") for m in seed.materials],
                            "prs": [p.model_dump(mode="json")
                                    for p in sorted(seed.prs, key=lambda p: (-p.created_at, p.id))]},
                    "crm": {"opportunities": [o.model_dump(mode="json") for o in seed.opportunities]},
                    "documents": _documents(cfg, bundles, files_docs, scenarios_root),
                    "notifications": notifications(cfg, bundles)}
    files = {f"{DEMO}/world.json": _json_bytes(world), f"{DEMO}/integrations.json": _json_bytes(integrations),
             f"{OUT}/enterprise_seed.json": (seed.model_dump_json(indent=1) + "\n").encode("utf-8")}
    for pid, bundle in sorted(bundles.items()):
        files[f"{DEMO}/projects/{pid}.json"] = (bundle.model_dump_json() + "\n").encode("utf-8")
    for pid, docs in sorted(files_docs.items()):
        for name, data in sorted(docs.items()):
            files[f"{DEMO}/files/{pid}/{name}"] = data
    build = WorldBuild(files)
    build.files[MANIFEST] = _json_bytes({"digest": build.digest(), "files": build.manifest()})
    return build


def write_world(build: WorldBuild, root: Path) -> list[str]:
    root = Path(root)
    for d in MANAGED_DIRS:
        folder = root / d
        if folder.is_dir():
            for f in sorted(folder.rglob("*")):
                if f.is_file() and f.relative_to(root).as_posix() not in build.files:
                    f.unlink()
    for rel, data in sorted(build.files.items()):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return sorted(build.files)


def diff_on_disk(build: WorldBuild, root: Path) -> list[str]:
    root = Path(root)
    return [rel for rel, data in sorted(build.files.items())
            if not (root / rel).exists() or (root / rel).read_bytes() != data]
