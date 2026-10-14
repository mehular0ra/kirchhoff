"""Activity feed and notifications (spec §13.2–13.3): derived from the project bundles plus world.yaml's authored
background activity. Deterministic: bundle timestamps, or anchor offsets with seeded jitter."""
from kirchhoff.contracts import ProjectBundle

from .config import WorldConfig, rng_for


def tool_summary(b: ProjectBundle) -> dict:
    results = [e for e in b.events if e.kind == "tool_result"]
    return results[-1].payload.get("summary", {}) if results else {}


def _fails(b: ProjectBundle) -> list[str]:
    if not b.revisions:
        return []
    return [f"{f.rule_id} {f.element_id}" for f in b.findings.get(b.revisions[0].id, []) if f.status == "fail"]


def activity(cfg: WorldConfig, bundles: dict[str, ProjectBundle]) -> list[dict]:
    rng = rng_for(cfg, "activity")
    items = [(cfg.ts(a.days_ago) + rng.randint(0, 3600), a.actor, a.project_id, a.text) for a in cfg.activity]
    for pid, b in sorted(bundles.items()):
        name = cfg.project(pid).name
        if b.runs:
            items.append((b.runs[0].started_at, "Arjun Mehta", pid, f"started a design run on {name}"))
        if _fails(b):
            items.append((b.revisions[0].created_at, "Checker", pid,
                          f"flagged {', '.join(_fails(b))} on {b.revisions[0].id}"))
        for a in b.approvals:
            items.append((a.ts, a.approver_name, pid, f"approved and signed {a.revision} of {name}"))
        for p in b.prs:
            actor = "Procurement agent" if b.revisions else "Rohan Das"
            items.append((p.created_at, actor, pid, f"submitted {p.id} to the ERP sandbox ({len(p.lines)} lines)"))
        if b.crm:
            items.append((b.crm.updated_at, "Neha Kapoor", pid, f"moved {name} to {b.crm.stage} in the CRM"))
        if not b.revisions and tool_summary(b):
            items.append((b.events[-1].ts, "Asset agent", pid,
                          f"evaluated {name}; recommended {tool_summary(b).get('recommended')}"))
    items.sort(key=lambda x: (-x[0], x[3]))
    return [{"id": f"act-{i + 1:03d}", "ts": round(ts, 3), "actor": actor, "project_id": pid, "text": text}
            for i, (ts, actor, pid, text) in enumerate(items)]


def notifications(cfg: WorldConfig, bundles: dict[str, ProjectBundle]) -> list[dict]:
    items = []
    for pid, b in sorted(bundles.items()):
        name = cfg.project(pid).name
        if _fails(b):
            items.append({"ts": b.revisions[0].created_at, "kind": "finding",
                          "title": f"Checker flagged {len(_fails(b))} failures on {name} {b.revisions[0].id}",
                          "body": ", ".join(_fails(b)), "project_id": pid})
        for a in b.approvals:
            items.append({"ts": a.ts, "kind": "approval", "title": f"{name} {a.revision} approved by {a.approver_name}",
                          "body": f"{len(b.prs)} purchase requisitions submitted to the ERP sandbox", "project_id": pid})
        if not b.revisions and tool_summary(b):
            items.append({"ts": b.events[-1].ts, "kind": "check", "title": f"{name}: asset-pack evaluation complete",
                          "project_id": pid})
    items.sort(key=lambda n: (-n["ts"], n["title"]))
    return [{"id": f"n-{i + 1:02d}", **n, "ts": round(n["ts"], 3)} for i, n in enumerate(items)]
