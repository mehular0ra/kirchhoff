"""Test doubles shared by the WS4 tests."""
import hashlib

from kirchhoff.contracts import DesignModel, Finding, Geometry, PRLine, TopologyOption, WhatIfResult
from kirchhoff.contracts.extra import FixCandidate
from kirchhoff.enterprise.model import canonical_json

STUB_CHIPS = [("rack_kw", 200.0), ("rack_kw", 150.0), ("liquid_fraction", 0.9), ("dv_limit_pct", 1.5),
              ("tx_loading_cap_pct", 35.0)]


def stub_model(topology: str = "2N", fixed: bool = False) -> DesignModel:
    return DesignModel(topology=topology, racks=[], equipment=[], connections=[], cooling_nodes=[], pipes=[],
                       geometry=Geometry(hall=(60.0, 36.0), columns=[], keepouts=[], rooms={}, tiers={}),
                       loads={"rack_kw": 132.0, "fixed": 1.0 if fixed else 0.0})


class StubEngine:
    """Deterministic engine double: R05:FA-01 fails until either fix candidate is applied."""

    def load_scenario(self, name="hall_a", root=None):
        return {"name": name}

    def place_racks(self, scn):
        return []

    def power_options(self, scn, racks):
        return [(TopologyOption(id=t, installed_mva=12.6, normal_loading_pct=38.0, failover_loading_pct=76.0,
                                cost=1.0e6, losses_kw=100.0, max_lead_time_weeks=12, spof_count=0), stub_model(t))
                for t in ("2N", "DR", "BLOCK")]

    def annotate_options(self, scn, options, erp):
        swap = {"line": "transformer", "from": "TX-2500", "to": "TX-3150", "reason": "R15"}
        return [(o.model_copy(update={"swaps": [swap]}), m) for o, m in options]

    def route(self, scn, model):
        return model

    def check(self, scn, model, erp, pr_lines=None):
        fixed = model.loads.get("fixed", 0.0) > 0
        return [Finding(id="R01:T-A1", rule_id="R01", element_id="T-A1", status="pass", title="Transformer loading"),
                Finding(id="R05:FA-01", rule_id="R05", element_id="FA-01", status="pass" if fixed else "fail",
                        title="Voltage drop", value=1.0 if fixed else 2.16, limit=2.0, unit="%")]

    def fix_candidates(self, scn, model, finding, erp):
        return [FixCandidate(id="FA-01:upsize-BW-2000", finding_id=finding.id, label="Upsize FA-01 to 2,000 A busway",
                             cost_delta=11480.0, metrics={"dv_pct": 1.66, "dv_limit_pct": 2.0}, patch={}),
                FixCandidate(id="FA-01:cable-CBL-240-8P", finding_id=finding.id, label="Parallel cable feeder for FA-01",
                             cost_delta=26900.0, metrics={"dv_pct": 0.84, "dv_limit_pct": 2.0}, patch={})]

    def apply_fix(self, model, candidate):
        return model.model_copy(update={"loads": {**model.loads, "fixed": 1.0}})

    def derive_pr_lines(self, scn, model, erp):
        return [PRLine(material_id="BW-1600", description="BW-1600 item", qty=400, unit_price=100.0, lead_time_weeks=8),
                PRLine(material_id="TX-3150", description="TX-3150 item", qty=6, unit_price=100.0, lead_time_weeks=12)]

    def model_hash(self, model):
        return hashlib.sha256(canonical_json(model.model_dump(mode="json")).encode("utf-8")).hexdigest()

    def ledger_not_checked(self):
        return ["Selectivity"]

    def chip_what_ifs(self, scn, model, erp, revision_ref):
        return [WhatIfResult(revision_ref=revision_ref, param=p, value=v, findings=[], impact_chain=[])
                for p, v in STUB_CHIPS]


import json  # noqa: E402

from kirchhoff.contracts import (Approval, CrmOverlay, DesignBrief, PurchaseRequisition, Revision, RunEvent,  # noqa: E402
                                 RunRecord, StepRecord)
from kirchhoff.store.memory import MemoryStore  # noqa: E402

UID, RID, T0 = "Zq8vAnonUid00000000000000ab", "a1b2c3d4e5f6", 1792000000.0


class Blobs:
    def __init__(self):
        self.data: dict[str, bytes] = {}

    def get(self, path: str) -> bytes:
        return self.data[path]


def make_hall_b_workspace(stub_engine) -> tuple:
    """A finished Ask-mode Hall B run laid out exactly as WS2 writes it (P2 R3, R4, R7, R8; Task 14)."""
    store, blobs = MemoryStore(), Blobs()
    ws, rp = f"workspaces/{UID}", f"workspaces/{UID}/runs/{RID}"
    run = RunRecord(id=RID, project_id="hall-b", status="done", autonomy="ask", phase="p4", started_at=T0,
                    finished_at=T0 + 1000, lease={"owner": None, "attempt": 3, "heartbeat_at": 0.0})
    store.set_doc(rp, {**run.model_dump(mode="json"), "message": "extra key the capture ignores"})
    for sid, ph, att, s, f in (("p1.intake", "p1", 1, T0, T0 + 20), ("p2.place_racks", "p2", 2, T0 + 700, T0 + 710),
                               ("p3.check.1", "p3", 2, T0 + 720, T0 + 730), ("p4.create_prs", "p4", 3, T0 + 900, T0 + 905)):
        store.set_doc(f"{rp}/steps/{sid}", StepRecord(id=sid, phase=ph, status="done", attempt=att, started_at=s,
                                                      finished_at=f).model_dump(mode="json"))
    events = [
        (1, "p1", "p1.intake", 1, "intake", "status", "Reading the Hall B tender", {}, T0 + 1),
        (2, "p1", "p1.intake", 1, "intake", "artifact", "Brief ready", {"type": "brief", "ref": f"{rp}/outputs/p1.intake"}, T0 + 19),
        (3, "p2", "p2.place_racks", 1, "layout", "status", "stale attempt (dropped)", {}, T0 + 650),
        (4, "p2", "p2.place_racks", 2, "layout", "status", "Placing racks", {}, T0 + 701),
        (5, "p3", "p3.check.1", 2, "checker", "artifact", "Revision ready", {"type": "revision", "ref": f"{ws}/revisions/{RID}-r1"}, T0 + 725),
        (6, "p3", "p3.check.1", 2, "docs", "artifact", "calc-report.pdf ready", {"type": "export", "ref": f"exports/{RID}-r2/calc-report.pdf"}, T0 + 729),
        (7, "p4", "p4.create_prs", 3, "procurement", "message", "You (Demo Reviewer) approved; PRs to ERP for Hall B", {}, T0 + 901),
    ]
    for seq, ph, step, att, agent, kind, title, payload, ts in events:
        store.set_doc(f"{rp}/events/{seq:06d}", RunEvent(seq=seq, phase=ph, step=step, attempt=att, agent=agent, kind=kind,
                                                         title=title, payload=payload, ts=ts).model_dump(mode="json"))
    brief = DesignBrief(project_id="hall-b", requirements=[])
    store.set_doc(f"{rp}/outputs/p1.intake", {"step": "p1.intake", "json": json.dumps({"brief": brief.model_dump(mode="json")})})
    store.set_doc(f"{rp}/outputs/p3.docs", {"step": "p3.docs", "json": json.dumps(
        {"rev": f"{RID}-r2", "order": ["summary", "findings", "boq"], "summary": "Hall B passes every check after the FA-01 fix."})})
    for n, fixed, status in ((1, False, "checked"), (2, True, "signed")):
        m = stub_model(fixed=fixed)
        fs = stub_engine.check(None, m, None)
        rev = Revision(id=f"{RID}-r{n}", project_id="hall-b", parent=f"{RID}-r{n - 1}" if n > 1 else None,
                       author="Kirchhoff agents", hash=stub_engine.model_hash(m), model=None,
                       model_url=f"revisions/{RID}-r{n}/model.json", summary=f"revision {n}",
                       check_summary={s: sum(f.status == s for f in fs) for s in ("pass", "fail", "warn", "n/a")},
                       status=status, created_at=T0 + 715 + 10 * n)
        store.set_doc(f"{ws}/revisions/{rev.id}", rev.model_dump(mode="json"))
        blobs.data[f"{ws}/{rev.model_url}"] = m.model_dump_json().encode("utf-8")
        for f in fs:
            store.set_doc(f"{ws}/revisions/{rev.id}/findings/{f.id}", f.model_dump(mode="json"))
    store.set_doc(f"{ws}/approvals/ap1", Approval(id="ap1", revision=f"{RID}-r2", approver_name="You (Demo Reviewer)",
                                                  role="Reviewer", decision="approved", ts=T0 + 890).model_dump(mode="json"))
    for i, vendor in enumerate(["Tapti", "Indus"]):
        pr = PurchaseRequisition(id=f"PR-2026-{310 - i:04d}", project_id="hall-b", revision=f"{RID}-r2",
                                 lines=[PRLine(material_id="TX-3150", description=vendor, qty=1, unit_price=1.0,
                                               lead_time_weeks=12)], status="submitted", created_at=T0 + 902 + i)
        store.set_doc(f"{ws}/prs/{pr.id}", pr.model_dump(mode="json"))
    store.set_doc(f"{ws}/crm/opp-hall-b", CrmOverlay(opportunity_id="opp-hall-b", stage="Design approved",
                                                     updated_at=T0 + 906).model_dump(mode="json"))
    return store, blobs
