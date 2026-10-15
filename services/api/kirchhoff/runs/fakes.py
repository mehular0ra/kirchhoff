"""Deterministic stand-ins for the WS1 engine facade and the WS4 enterprise sandbox (tests + KIRCHHOFF_FAKES=1).
Shapes follow 2026-10-13-interfaces.md; values are illustrative and only loosely mirror spec §9.6.

Differences from the plan's illustrative FakeEngine sketch, reconciled against the real, now-merged
`kirchhoff.engine.api` facade (Task 7 report has the full list):
- `warm_up()` and `validate_model(scn, model) -> None` added: the real facade exports both, and
  `validate_model` must raise ValueError on duplicate element ids (ruling P2-R2) so a careless fix patch
  (e.g. appending a cooling node twice) fails loudly here too, not just in the real engine.
- `chip_what_ifs(scn, model, erp, revision_ref) -> list[WhatIfResult]` added, matching the real facade's
  parameter order (erp before revision_ref), which differs from `what_if`'s own order.
- `derive_boq(scn, model) -> list[dict]` and `default_erp(name="hall_a", root=None)` added: both are
  re-exported from `kirchhoff.engine.api` (via boq.py and erp.py) and so are part of the facade the
  drift test in test_runs_fakes.py enumerates.
"""
import hashlib
import json
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kirchhoff.agents.ports import ErpSnapshot
from kirchhoff.contracts import (Citation, ClauseRef, Connection, CoolingNode, CrmOverlay, DesignModel, Equipment,
                                 Finding, Geometry, Material, Pipe, Point3, PRLine, PurchaseRequisition, Rack,
                                 TopologyOption, WhatIfResult)
from kirchhoff.contracts import Opportunity
from kirchhoff.contracts.extra import ClashReport, FixCandidate
from kirchhoff.intake.render import load_geometry, render_drawing, render_tender_pdf
from kirchhoff.intake.tender_schema import load_tender
from kirchhoff.store.memory import MemoryStore
from kirchhoff.store.validate import firestore_safe_problems


def _m(id, category, description, rating, unit, stock, lead, price, vendor):
    return Material(id=id, category=category, description=description, rating=rating, unit=unit, voltage="415 V",
                    stock=stock, lead_time_weeks=lead, unit_price=price, vendor=vendor)


FAKE_MATERIALS = [
    _m("TX-2500", "transformer", "Transformer 2.5 MVA 33/0.415 kV cast resin", 2500, "kVA", 0, 98, 182000,
       "Vindhya Electricals"),
    _m("TX-3150", "transformer", "Transformer 3.15 MVA 33/0.415 kV cast resin", 3150, "kVA", 6, 12, 214000,
       "Vindhya Electricals"),
    _m("BW-1600", "busway", "Busway 1,600 A per metre", 1600, "A", 900, 8, 410, "Konark Busbar"),
    _m("BW-2000", "busway", "Busway 2,000 A per metre", 2000, "A", 400, 10, 520, "Konark Busbar"),
    _m("CBL-240-8P", "cable", "Cable feeder 8 x 1C 240 mm2 Cu per phase", 2500, "A", 300, 6, 610,
       "Konark Cables"),
    _m("UPS-500", "ups_module", "UPS module 500 kW", 500, "kW", 40, 14, 96000, "Godavari Power Systems"),
    _m("CDU-1200", "cdu", "Coolant distribution unit 1,200 kW", 1200, "kW", 12, 16, 148000,
       "Coolant Systems India"),
]
_MATERIALS_BY_ID = {m.id: m for m in FAKE_MATERIALS}
NOT_CHECKED = ["Earth-fault loop impedance (IEC 60364-4-41 §411)", "Selectivity", "Arc flash", "Harmonics",
               "Air-side cooling for the air-cooled share", "MV bus faults",
               "Busway derating above the assumed ambient"]


@dataclass(frozen=True)
class FakeScenario:
    name: str
    tender: dict
    catalogue: dict = field(default_factory=dict)
    geometry: dict = field(default_factory=dict)


def _base_model(topology: str, racks: list[Rack]) -> DesignModel:
    return DesignModel(
        topology=topology, racks=racks,
        equipment=[
            Equipment(id="T-A1", kind="transformer", rating=2500.0, unit="kVA", catalogue_id="TX-2500", system="A",
                      room="A"),
            Equipment(id="A1", kind="lv_board", system="A", room="A"),
            Equipment(id="UPS-A1", kind="ups", rating=2500.0, unit="kW", catalogue_id="UPS-500", system="A"),
            Equipment(id="A-01", kind="busway", rating=1600.0, unit="A", catalogue_id="BW-1600", system="A"),
            Equipment(id="B-03", kind="busway", rating=1600.0, unit="A", catalogue_id="BW-1600", system="B"),
        ],
        connections=[
            Connection(id="FA-01", src="A1", dst="A-01", kind="busway", length_m=82.0, catalogue_id="BW-1600"),
            Connection(id="FB-03", src="B2", dst="B-03", kind="busway", length_m=40.0, catalogue_id="BW-1600"),
        ],
        cooling_nodes=[], pipes=[],
        geometry=Geometry(hall=(60.0, 36.0), columns=[(0.0, 0.0), (12.0, 0.0)], keepouts=[(10.0, 10.0, 18.0, 26.0)],
                          rooms={"A": (60.0, 0.0, 72.0, 10.0)},
                          tiers={"pipe_low": 2.6, "busway": 3.2, "pipe_high": 3.8}),
        loads={"rack_kw": 132.0, "liquid_fraction": 0.8, "aux_mw": 0.3, "pumps_kw": 135.0})


def _find(items, id_):
    return next((x for x in items if x.id == id_), None)


def _f(rule, el, status, title, value, limit, unit, clause=None, page=None, inputs=None) -> Finding:
    return Finding(id=f"{rule}:{el}", rule_id=rule, element_id=el, status=status, title=title,
                   clause_refs=[ClauseRef(standard="IEC 60364")],
                   tender_refs=[Citation(doc_id="tender-hall-a", page=page or 1, quote="", clause=clause)]
                   if clause else [],
                   inputs=inputs or {}, value=value, limit=limit, unit=unit,
                   explanation=f"{title}: {{value}} against a limit of {{limit}}.")


CHIP_WHAT_IFS: list[tuple[str, float]] = [("rack_kw", 200.0), ("rack_kw", 150.0), ("liquid_fraction", 0.9)]


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def _log(self, name: str) -> None:
        with self._lock:
            self.calls.append(name)

    def load_scenario(self, name: str = "hall_a", root: Path | None = None) -> FakeScenario:
        p = Path(root) / name / "tender.yaml" if root else None
        tender = yaml.safe_load(p.read_text(encoding="utf-8")) if p and p.exists() else {"clauses": []}
        return FakeScenario(name=name, tender=tender)

    def place_racks(self, scn) -> list[Rack]:
        self._log("place_racks")
        return [Rack(id="R1-01", row="R1", x=6.0, y=15.9, kw=132.0, liquid_fraction=0.8, feeds=("A-01", "B-01")),
                Rack(id="R3-01", row="R3", x=28.0, y=15.9, kw=132.0, liquid_fraction=0.8, feeds=("A-03", "B-03"))]

    def size_cooling(self, scn, racks) -> list[CoolingNode]:
        self._log("size_cooling")
        return [CoolingNode(id=f"CDU-{i}", kind="cdu", zone="Z1" if i <= 3 else "Z2", capacity_kw=1200.0,
                            x=4.0 * i, y=30.0) for i in range(1, 7)]

    def power_options(self, scn, racks):
        self._log("power_options")
        out = []
        for tid, mva, cost in (("2N", 15.0, 4_100_000.0), ("DR", 10.0, 3_300_000.0), ("BLOCK", 10.0, 3_050_000.0)):
            out.append((TopologyOption(id=tid, installed_mva=mva, normal_loading_pct=48.0, failover_loading_pct=96.0,
                                       cost=cost, losses_kw=310.0, max_lead_time_weeks=98, spof_count=0),
                        _base_model(tid, list(racks))))
        return out

    def annotate_options(self, scn, options, erp):
        self._log("annotate_options")
        res = []
        for opt, model in options:
            eq = [e.model_copy(update={"catalogue_id": "TX-3150", "rating": 3150.0}) if e.kind == "transformer" else e
                  for e in model.equipment]
            res.append((opt.model_copy(update={
                "installed_mva": round(opt.installed_mva * 1.26, 2), "normal_loading_pct": 38.0,
                "failover_loading_pct": 76.0, "max_lead_time_weeks": 16, "cost": opt.cost + 192_000.0,
                "swaps": [{"line": "transformer", "from": "TX-2500", "to": "TX-3150", "qty": 1, "reason": "R15",
                           "ikss_ka_before": 60.4, "ikss_ka_after": 65.4}]}),
                model.model_copy(update={"equipment": eq})))
        return res

    def route(self, scn, model):
        """Mirrors the real `routing.route` (ruling P2-R3a): feeder routes are always recomputed, but
        `cooling_nodes`/`pipes` are only filled when empty, so calling route() on an already-fixed model
        never undoes a fix (e.g. a pipe tier changed by `apply_fix`)."""
        self._log("route")
        conns = [c.model_copy(update={"route": [Point3(x=66.0, y=2.0 if c.id.startswith("FA") else 34.2, z=3.2),
                                                Point3(x=6.0, y=2.0, z=3.2)]}) for c in model.connections]
        out = model.model_copy(update={"connections": conns})
        if not out.cooling_nodes:
            out = out.model_copy(update={"cooling_nodes": self.size_cooling(scn, out.racks)})
        if not out.pipes:
            pipes = [Pipe(id="H-Z1", kind="header", zone="Z1", dn=200, tier="pipe_high", flow_lps=10.5,
                          route=[Point3(x=12.0, y=30.0, z=3.8), Point3(x=12.0, y=21.0, z=3.8)]),
                     Pipe(id="H-Z2", kind="header", zone="Z2", dn=200, tier="pipe_high", flow_lps=10.5,
                          route=[Point3(x=31.0, y=30.0, z=3.8), Point3(x=31.0, y=21.0, z=3.8)])]
            out = out.model_copy(update={"pipes": pipes})
        return out

    def detect_clashes(self, model) -> ClashReport:
        self._log("detect_clashes")
        return ClashReport(clashes=[])

    def validate_model(self, scn, model) -> None:
        """Mirrors the real facade's duplicate-id guard (ruling P2-R2): never append a cooling node (or any
        other element) twice. The real engine checks catalogue resolution too; the fake only guards ids,
        since the fake has no real catalogue to resolve against."""
        self._log("validate_model")
        groups = (("equipment", [e.id for e in model.equipment]),
                  ("connections", [c.id for c in model.connections]),
                  ("pipes", [p.id for p in model.pipes]),
                  ("cooling_nodes", [n.id for n in model.cooling_nodes]))
        for label, ids in groups:
            seen: set[str] = set()
            for i in ids:
                if i in seen:
                    raise ValueError(f"duplicate {label} id: {i}")
                seen.add(i)

    def warm_up(self) -> None:
        """No-op in the fake: there is no pandapower import or JIT cost to pay up front."""
        self._log("warm_up")

    def check(self, scn, model, erp, pr_lines=None) -> list[Finding]:
        self._log("check")
        self.validate_model(scn, model)  # ruling P2-R3c: mirrors the real facade's `check`
        rack_kw = model.loads.get("rack_kw", 132.0)
        hot = rack_kw > 150.0
        t, fa, h = _find(model.equipment, "T-A1"), _find(model.connections, "FA-01"), _find(model.pipes, "H-Z2")
        tx_ok = t is not None and t.catalogue_id == "TX-3150"
        out = [_f("R01", "T-A1", "fail" if hot else "pass", "Transformer loading", 114.0 if hot else 76.0, 100.0, "%",
                  "§4.3", 4),
               _f("R02", "A-01", "fail" if hot else "pass", "Busway rating", 2343.0 if hot else 1546.0, 1600.0, "A"),
               _f("R04", "A1", "pass", "Breaker breaking capacity", 66.1, 100.0, "kA"),
               _f("R04b", "A-01", "pass", "Busway short-time withstand", 66.1, 85.0, "kA"),
               _f("R08", "Z2", "fail" if hot else "pass", "CDU capacity per zone", 2560.0 if hot else 1690.0, 2400.0,
                  "kW", "§6.2", 6),
               _f("R15", "T-A1", "pass" if tx_ok else "fail", "Lead time", 12.0 if tx_ok else 98.0, 26.0, "weeks",
                  "§2.3", 2)]
        if fa is not None and fa.route:
            dv = {"BW-1600": 2.16, "BW-2000": 1.66}.get(fa.catalogue_id or "", 0.84)
            out.append(_f("R05", "FA-01", "fail" if dv > 2.0 else "pass", "Voltage drop", dv, 2.0, "%", "§4.6", 4,
                          {"L_m": fa.length_m}))
        else:
            out.append(_f("R05", "FA-01", "n/a", "Voltage drop", None, 2.0, "%", "§4.6", 4))
        if h is not None:
            out.append(_f("R11", "H-Z2", "fail" if h.tier == "pipe_high" else "pass", "Liquid above electrical",
                          None, None, None, "§6.3.4", 6, {"above": "FB-03", "at_y": 24.0}))
        else:
            out.append(_f("R11", "H-Z2", "n/a", "Liquid above electrical", None, None, None, "§6.3.4", 6))
        expected = sum(line.qty for line in self.derive_pr_lines(scn, model, erp)) if erp is not None else None
        r12_ok = pr_lines is None or expected is None or sum(line.qty for line in pr_lines) == expected
        out.append(_f("R12", "BOQ", "pass" if r12_ok else "fail", "SLD, BOQ and PR lines agree", None, None, None))
        return out

    def fix_candidates(self, scn, model, finding, erp) -> list[FixCandidate]:
        """Every rule except R05 and R11 returns [] (final-review ruling); only those two findings ever reach
        this fake with a non-trivial fix, matching the real engine's narrower `fix_candidates`.

        Ruling P2-R3b: mirrors the real engine -- [] once the finding no longer fails on this model (so a
        second fix pass over an already-fixed finding is a no-op, not a repeat offer), and a ValueError for
        a finding id this model's checker never produced (the real engine has no candidates to look up for
        an id it doesn't recognise)."""
        self._log("fix_candidates")
        current = {f.id: f for f in self.check(scn, model, erp)}
        if finding.id not in current:
            raise ValueError(f"unknown finding id {finding.id!r}")
        if current[finding.id].status != "fail":
            return []
        cands: list[FixCandidate] = []
        if finding.id == "R05:FA-01":
            cands = [FixCandidate(id="FA-01:upsize-BW-2000", finding_id=finding.id,
                                  label="Upsize FA-01 to 2,000 A busway", cost_delta=11480.0,
                                  metrics={"dv_pct": 1.66, "dv_limit_pct": 2.0, "rating_a": 2000.0},
                                  patch={"connection": "FA-01", "catalogue_id": "BW-2000"}),
                     FixCandidate(id="FA-01:cable-CBL-240-8P", finding_id=finding.id,
                                  label="Parallel cable feeder for FA-01", cost_delta=26900.0,
                                  metrics={"dv_pct": 0.84, "dv_limit_pct": 2.0, "rating_a": 2500.0},
                                  patch={"connection": "FA-01", "catalogue_id": "CBL-240-8P", "kind": "cable"})]
        if finding.id == "R11:H-Z2":
            cands = [FixCandidate(id="H-Z2:local-drop", finding_id=finding.id,
                                  label="Local drop of H-Z2 to pipe_low at the FB-03 crossing", cost_delta=420.0,
                                  metrics={"crossings": 0.0, "added_pipe_m": 2.4, "changed_pipes": 1.0,
                                           "index_dp_kpa": 69.8},
                                  patch={"pipe": "H-Z2", "tier": "pipe_low"}),
                     FixCandidate(id="H-Z2:reroute", finding_id=finding.id, label="Reroute H-Z2 clear of FB-03",
                                  cost_delta=-910.0,
                                  metrics={"crossings": 0.0, "added_pipe_m": -4.0, "changed_pipes": 2.0,
                                           "index_dp_kpa": 68.9},
                                  patch={"pipe": "H-Z2", "tier": "pipe_low"})]
        return sorted(cands, key=lambda c: (c.cost_delta, c.id))

    def power_recheck(self, scn, model) -> list[Finding]:
        self._log("power_recheck")
        return [f for f in self.check(scn, model, None) if f.rule_id in ("R01", "R04", "R04b")]

    def apply_fix(self, model, candidate):
        self._log("apply_fix")
        p = candidate.patch
        if "connection" in p:
            upd = {k: v for k, v in p.items() if k in ("catalogue_id", "kind")}
            return model.model_copy(update={"connections": [c.model_copy(update=upd) if c.id == p["connection"]
                                                             else c for c in model.connections]})
        if "pipe" in p:
            return model.model_copy(update={"pipes": [x.model_copy(update={"tier": p["tier"]}) if x.id == p["pipe"]
                                                      else x for x in model.pipes]})
        return model

    def what_if(self, scn, model, param, value, revision_ref, erp) -> WhatIfResult:
        self._log("what_if")
        loads = dict(model.loads)
        if param in ("rack_kw", "liquid_fraction"):
            loads[param] = float(value)
        bad = [f for f in self.check(scn, model.model_copy(update={"loads": loads}), erp)
               if f.status in ("fail", "warn")]
        chain = [["R1-01", "A-01", "A1", "T-A1"], ["R1-01", "Z1", "CDU-1"]] if bad else []
        return WhatIfResult(revision_ref=revision_ref, param=param, value=float(value), findings=bad,
                            impact_chain=chain)

    def chip_what_ifs(self, scn, model, erp, revision_ref) -> list[WhatIfResult]:
        """Matches the real facade's parameter order (erp before revision_ref), which differs from
        `what_if`'s own order."""
        self._log("chip_what_ifs")
        return [self.what_if(scn, model, p, v, revision_ref, erp) for p, v in CHIP_WHAT_IFS]

    def _counts(self, model) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in model.equipment:
            if e.catalogue_id:
                counts[e.catalogue_id] = counts.get(e.catalogue_id, 0) + 1
        for c in model.connections:
            if c.catalogue_id:
                counts[c.catalogue_id] = counts.get(c.catalogue_id, 0) + max(1, round(c.length_m))
        cdus = sum(1 for n in model.cooling_nodes if n.kind == "cdu")
        if cdus:
            counts["CDU-1200"] = cdus
        return counts

    def derive_boq(self, scn, model) -> list[dict]:
        """Re-exported from the real facade (via boq.py); the fake prices off FAKE_MATERIALS since a
        FakeScenario carries no real catalogue."""
        self._log("derive_boq")
        lines = []
        for mid, qty in sorted(self._counts(model).items()):
            m = _MATERIALS_BY_ID[mid]
            lines.append({"material_id": mid, "description": m.description, "qty": qty, "unit": m.unit,
                          "unit_price": m.unit_price, "total": qty * m.unit_price})
        return lines

    def derive_pr_lines(self, scn, model, erp) -> list[PRLine]:
        lines = []
        for mid, qty in sorted(self._counts(model).items()):
            m = erp.get(mid)
            lines.append(PRLine(material_id=mid, description=m.description, qty=qty, unit_price=m.unit_price,
                                lead_time_weeks=m.lead_time_weeks))
        return lines

    def model_hash(self, model) -> str:
        raw = json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def ledger_not_checked(self) -> list[str]:
        return list(NOT_CHECKED)

    def default_erp(self, name: str = "hall_a", root: Path | None = None) -> ErpSnapshot:
        """Re-exported from the real facade (via erp.py); the fake ignores `name`/`root` and always returns
        FAKE_MATERIALS."""
        self._log("default_erp")
        return ErpSnapshot(FAKE_MATERIALS)

    def evaluate_grid(self, scn_dir: Path | None = None) -> dict[str, Any]:
        return {"options": [{"id": "ACSR-Panther", "ampacity_a": 520.0}, {"id": "ACSR-Zebra", "ampacity_a": 900.0},
                            {"id": "ACSR-Moose", "ampacity_a": 980.0}],
                "recommended": "ACSR-Zebra",
                "findings": [_f("G01", "LINE-1", "pass", "Conductor ampacity", 900.0, 656.0, "A")],
                "geometry": {"length_km": 18.0}}

    def evaluate_solar(self, scn_dir: Path | None = None) -> dict[str, Any]:
        return {"options": [{"id": "STR-26", "modules_per_string": 26}, {"id": "STR-28", "modules_per_string": 28}],
                "recommended": "STR-28",
                "findings": [_f("S01", "STR-28", "pass", "String voltage at minimum temperature", 1421.0, 1500.0,
                                "V")],
                "geometry": {"mwp": 5.0}}


FAKE_OPPORTUNITIES = [
    Opportunity(id="opp-hall-a", account="Deccan Compute", name="Hall A design-build", stage="Design approved",
                value=18_500_000.0),
    Opportunity(id="opp-hall-b", account="Deccan Compute", name="Hall B design-build", stage="Design in progress",
                value=18_500_000.0),
    Opportunity(id="opp-pune-edge-1", account="Konkan Cloud", name="Pune Edge Phase 1", stage="Closed won",
                value=7_000_000.0),
    Opportunity(id="opp-grid-132kv", account="Narmada Transmission", name="Deccan campus 132 kV intake",
                stage="Negotiation", value=4_800_000.0),
    Opportunity(id="opp-solar-5mwp", account="Suryodaya Renewables", name="Deccan campus 5 MWp solar",
                stage="Proposal", value=3_000_000.0),
    Opportunity(id="opp-vindhya-cpp", account="Vindhya Steel", name="Captive power switchyard", stage="Qualification",
                value=3_700_000.0),
]


class FakeEnterprise:
    def __init__(self, materials: list[Material] | None = None) -> None:
        self.materials = list(materials or FAKE_MATERIALS)
        self.prs: dict[tuple[str, str], PurchaseRequisition] = {}
        self.keys: dict[str, tuple[str, str]] = {}
        self.stages: dict[tuple[str, str], CrmOverlay] = {}
        self._n = 141
        self._lock = threading.Lock()

    def list_materials(self) -> list[Material]:
        return list(self.materials)

    def create_pr(self, uid, project_id, revision, lines, idempotency_key) -> PurchaseRequisition:
        with self._lock:
            if idempotency_key in self.keys:
                return self.prs[self.keys[idempotency_key]]
            self._n += 1
            pr = PurchaseRequisition(id=f"PR-2026-{self._n:04d}", project_id=project_id, revision=revision,
                                     lines=list(lines), status="submitted", created_at=time.time())
            self.prs[(uid, pr.id)] = pr
            self.keys[idempotency_key] = (uid, pr.id)
            return pr

    def set_pr_status(self, uid, pr_id, status) -> None:
        with self._lock:
            self.prs[(uid, pr_id)] = self.prs[(uid, pr_id)].model_copy(update={"status": status})

    def set_opportunity_stage(self, uid, opportunity_id, stage) -> CrmOverlay:
        ov = CrmOverlay(opportunity_id=opportunity_id, stage=stage, updated_at=time.time())
        with self._lock:
            self.stages[(uid, opportunity_id)] = ov
        return ov

    def reset_visitor(self, uid) -> None:
        with self._lock:
            self.prs = {k: v for k, v in self.prs.items() if k[0] != uid}
            self.keys = {k: v for k, v in self.keys.items() if v[0] != uid}
            self.stages = {k: v for k, v in self.stages.items() if k[0] != uid}

    # ---- bids inbox CRM (spec §20, I-2). Additive on purpose: the state is created on first use, so __init__ and
    # reset_visitor above are untouched and stay trivial to merge. A side effect: reset_visitor does not clear
    # visitor-created opportunities in this fake (create_opportunity is idempotent, so a repeat is harmless).
    def _crm(self) -> dict:
        return self.__dict__.setdefault("_crm_state", {"seed": list(FAKE_OPPORTUNITIES), "created": {}})

    @property
    def opportunities(self) -> list[Opportunity]:
        return self._crm()["seed"]

    @property
    def created(self) -> dict[tuple[str, str], Opportunity]:
        return self._crm()["created"]

    def list_opportunities(self, uid) -> list[Opportunity]:
        crm = self._crm()
        with self._lock:
            mine = [o for (u, _), o in crm["created"].items() if u == uid]
            stages = {oid: ov.stage for (u, oid), ov in self.stages.items() if u == uid}
        return sorted((o.model_copy(update={"stage": stages[o.id]}) if o.id in stages else o
                       for o in crm["seed"] + mine), key=lambda o: o.id)

    def create_opportunity(self, uid, opportunity) -> Opportunity:
        crm = self._crm()
        if opportunity.id in {o.id for o in crm["seed"]}:
            raise ValueError(f"{opportunity.id} is a seed opportunity")
        with self._lock:
            return crm["created"].setdefault((uid, opportunity.id), opportunity)


_EXTRACTION = {
    "requirements": [
        {"key": "max_lead_time_weeks", "clause": "§2.3", "page": 2, "value": 26, "unit": "weeks",
         "verbatim_quote": "All major electrical and mechanical equipment shall be on site no later than 26 weeks "
                           "from contract award."},
        {"key": "racks", "clause": "§3.1", "page": 3, "value": 48, "unit": "racks",
         "verbatim_quote": "The hall shall accommodate 48 racks in 6 rows of 8, each rack rated 132 kW."},
        {"key": "rack_kw", "clause": "§3.1", "page": 3, "value": 132, "unit": "kW",
         "verbatim_quote": "each rack rated 132 kW"},
        {"key": "redundancy", "clause": "§4.2", "page": 4, "value": "2N", "unit": None,
         "verbatim_quote": "The critical power distribution shall be 2N, with each rack fed from two independent "
                           "systems."},
        {"key": "tx_loading_normal_max_pct", "clause": "§4.3", "page": 4, "value": 80, "unit": "%",
         "verbatim_quote": "Transformer loading shall not exceed 80% of rating in normal operation"},
        {"key": "dv_max_pct", "clause": "§4.6", "page": 4, "value": 2.0, "unit": "%",
         "verbatim_quote": "shall not exceed 2.0% at the worst-case design current"},
        {"key": "pipe_velocity_max_mps", "clause": "§6.4", "page": 6, "value": 2.5, "unit": "m/s",
         "verbatim_quote": "Coolant velocity in any pipe shall not exceed 2.5 m/s."},
        {"key": "ups_autonomy_min", "clause": "§4.5", "page": 3, "value": 5, "unit": "min",
         "verbatim_quote": "battery autonomy of not less than 5 minutes"},
    ],
    "contradictions": [
        {"topic": "redundancy", "clause_a": "§4.2", "page_a": 4,
         "quote_a": "The critical power distribution shall be 2N", "value_a": "2N", "clause_b": "App. B", "page_b": 7,
         "quote_b": "Block or distributed redundancy acceptable",
         "value_b": "BLOCK or DR", "summary": "§4.2 requires 2N but App. B accepts block or distributed redundancy."},
    ],
}

FAKE_REPLIES: dict[str, dict] = {
    "intake:p1.extract": {"text": _EXTRACTION, "usage": {"in": 9000, "out": 900}},
    "intake:p1.drawing": {"text": {"grid_x": ["1", "2", "3", "4", "5", "6"], "grid_y": ["A", "B", "C", "D"],
                                   "overall_mm": [60000, 36000]}, "usage": {"in": 2000, "out": 60}},
    "orchestrator:p1.plan": {"text": {"summary": "The brief is complete; the redundancy conflict between §4.2 and "
                                                 "App. B needs the engineer.", "ask_human": ["Q-redundancy"]}},
    "layout:p2.place_racks": {"tool_calls": [{"name": "place_racks", "args": {}}],
                              "text": "Layout placed the racks in rows R1 and R3 with the engine default."},
    "power:p2.power_options": {"tool_calls": [{"name": "enumerate_topologies", "args": {}}],
                               "text": {"offer": ["2N", "DR", "BLOCK"],
                                        "reason": "All three pass R01 at their minimum rating; §4.2 asks for 2N and "
                                                  "App. B allows the others."}},
    "cooling:p2.cooling_sizing": {"tool_calls": [{"name": "size_cdus", "args": {}},
                                                 {"name": "hydraulic_zones", "args": {}}],
                                  "text": "Cooling sized the CDUs with N+1 in each zone."},
    "procurement:p2.annotate_options": {"tool_calls": [{"name": "annotate_options", "args": {}}],
                                        "text": "TX-2500 misses the §2.3 lead-time limit, so the engine swapped it "
                                                "for TX-3150, which ships from stock."},
    "power:p2.power_recheck": {"tool_calls": [{"name": "recheck_swapped_options", "args": {}}],
                               "text": "Power re-ran short circuit on the TX-3150 options; R01, R04 and R04b still "
                                       "pass."},
    "power:p3.select_option": {"text": "2N follows §4.2 with zero single points of failure at the lowest "
                                       "qualifying cost."},
    "layout:p3.route": {"tool_calls": [{"name": "route_busways", "args": {}}],
                        "text": "Layout routed the A feeders along the south corridor and the B feeders along the "
                                "north corridor."},
    "power:p3.fix.1:R05:FA-01": {"text": {"candidate_id": "FA-01:cable-CBL-240-8P",
                                          "reason": "The cable feeder gives FA-01 the largest voltage-drop margin per "
                                                    "dollar under §4.6."}},
    "cooling:p3.fix.1:R11:H-Z2": {"text": {"candidate_id": "H-Z2:local-drop",
                                           "reason": "The local drop changes the fewest pipe segments and clears R11 at "
                                                     "the FB-03 crossing."}},
    "docs:p3.docs": {"text": {"order": ["summary", "requirements", "options", "findings", "fixes", "ledger", "boq"],
                              "summary": "The 2N design passes every check after fixes to FA-01 and H-Z2."}},
    "copilot:explain:R05:FA-01": {"text": "FA-01 has a voltage drop of {value}, above the {limit} limit in §4.6. "
                                          "It is the longest A-side feeder from A1."},
    "asset:grid": {"text": {"option": "ACSR-Zebra", "reason": "Zebra meets the ampacity need with the lowest "
                                                              "losses."}},
    "asset:solar": {"text": {"option": "STR-28", "reason": "STR-28 stays under the inverter limit on cold "
                                                           "mornings."}},
}


def _q(key, value, source, quote, page=None, unit=None):
    return {"key": key, "value": value, "unit": unit, "source": source, "page": page, "verbatim_quote": quote}


# Bids inbox (addendum I-2): one recorded Inbox-agent reply per seeded email. Quotes are verbatim from I-1's world.yaml
# bodies and rendered PDFs (and the Hall A tender), so verification runs for real in the tests.
INBOX_REPLIES: dict[str, dict] = {
    "inbox:triage:em-hall-b": {"usage": {"in": 14200, "out": 610}, "text": {
        "is_bid": True,
        "summary": "Deccan Compute invites a design-build bid for Data Hall B, a twin of Hall A with 2N power.",
        "attachments": [{"attachment_id": "att-hall-b-tender", "kind": "tender"},
                        {"attachment_id": "att-hall-b-drawing", "kind": "drawing"},
                        {"attachment_id": "att-hall-b-addendum", "kind": "addendum"}],
        "fields": [_q("client", "Deccan Compute", "body", "Deccan Compute invites your bid"),
                   _q("site", "AI campus near Hyderabad, Telangana", "body",
                      "at our AI campus near Hyderabad, Telangana"),
                   _q("asset_type", "datahall", "body", "liquid-cooling design-build of Data Hall B"),
                   _q("mw", 6.336, "att-hall-b-addendum", "Hall B IT load: 6.336 MW", 1, "MW"),
                   _q("redundancy", "2N", "att-hall-b-tender", "The critical power distribution shall be 2N", 4),
                   _q("bid_due", "13 November 2026", "att-hall-b-addendum", "Bids are due by 13 November 2026", 1),
                   _q("lead_time_weeks", 26, "att-hall-b-tender", "no later than 26 weeks from contract award", 2,
                      "weeks")],
        "crm": {"account": "Deccan Compute", "opportunity_id": "opp-hall-b", "propose_new": False}}},
    "inbox:triage:em-tapti-brochure": {"usage": {"in": 2100, "out": 140}, "text": {
        "is_bid": False, "summary": "Vendor marketing from Tapti Transformers about its cast-resin range.",
        "attachments": [{"attachment_id": "att-tapti-brochure", "kind": "brochure"}], "fields": [],
        "crm": {"account": None, "opportunity_id": None, "propose_new": False}}},
    "inbox:triage:em-konkan-rfi": {"usage": {"in": 2300, "out": 180}, "text": {
        "is_bid": False,
        "summary": "Konkan Cloud confirms the CDU gallery door stays as drawn, so the signed Pune Edge design holds.",
        "attachments": [{"attachment_id": "att-konkan-rfi", "kind": "other"}],
        "fields": [_q("client", "Konkan Cloud", "att-konkan-rfi", "Signed for Konkan Cloud", 1)],
        "crm": {"account": "Konkan Cloud", "opportunity_id": "opp-pune-edge-1", "propose_new": False}}},
    "inbox:triage:em-vindhya-boq": {"usage": {"in": 2600, "out": 260}, "text": {
        "is_bid": True,
        "summary": "Vindhya Steel asks for pricing of a captive power switchyard; its BOQ is a scanned image.",
        "attachments": [{"attachment_id": "att-vindhya-boq", "kind": "boq"}],
        "fields": [_q("client", "Vindhya Steel", "body", "Forwarding from Vindhya Steel"),
                   _q("site", "Satna mill, Madhya Pradesh", "body", "at our Satna mill, Madhya Pradesh"),
                   _q("asset_type", "grid", "body", "the 33 kV captive power switchyard"),
                   _q("mw", 40, "att-vindhya-boq", "Plant load: 40 MW", 1, "MW"),
                   _q("bid_due", "30 October 2026", "body", "Bids are due by 30 October 2026")],
        "crm": {"account": "Vindhya Steel", "opportunity_id": "opp-vindhya-cpp", "propose_new": False}}},
    "inbox:triage:em-suryodaya-solar": {"usage": {"in": 900, "out": 200}, "text": {
        "is_bid": True,
        "summary": "Suryodaya Renewables asks whether Meridian will bid for a ground-mount solar EPC.",
        "attachments": [],
        "fields": [_q("client", "Suryodaya Renewables", "body", "Suryodaya Renewables is planning"),
                   _q("site", "near Anantapur, Andhra Pradesh", "body", "plant near Anantapur, Andhra Pradesh"),
                   _q("asset_type", "solar", "body", "ground-mount solar plant"),
                   _q("mw", 20, "body", "a 20 MWp ground-mount solar plant", unit="MWp")],
        "crm": {"account": "Suryodaya Renewables", "opportunity_id": None, "propose_new": True}}},
    "inbox:triage:em-narmada-400kv": {"usage": {"in": 2400, "out": 230}, "text": {
        "is_bid": True,
        "summary": "Narmada Transmission requests EPC quotations for a GIS substation in Gujarat.",
        "attachments": [{"attachment_id": "att-narmada-spec", "kind": "tender"}],
        "fields": [_q("client", "Narmada Transmission", "body", "Narmada Transmission requests EPC quotations"),
                   _q("site", "Bharuch, Gujarat", "body", "substation at Bharuch, Gujarat"),
                   _q("asset_type", "substation", "att-narmada-spec",
                      "EPC of a new 400/220 kV gas-insulated substation", 1),
                   _q("bid_due", "20 November 2026", "body", "Quotations are due by 20 November 2026")],
        "crm": {"account": "Narmada Transmission", "opportunity_id": None, "propose_new": True}}},
}
FAKE_REPLIES.update(INBOX_REPLIES)


def build_fake_scenarios(root: Path, tender_yaml: Path, geometry_yaml: Path, ground_truth_yaml: Path) -> Path:
    root = Path(root)
    hall = root / "hall_a"
    (hall / "out").mkdir(parents=True, exist_ok=True)
    for src, name in ((tender_yaml, "tender.yaml"), (geometry_yaml, "geometry.yaml"),
                      (ground_truth_yaml, "ground_truth.yaml")):
        shutil.copy(src, hall / name)
    render_tender_pdf(load_tender(tender_yaml), hall / "out" / "tender-hall-a.pdf")
    render_drawing(load_geometry(geometry_yaml), hall / "out" / "hall-a.dxf", hall / "out" / "hall-a-plan.pdf")
    (root / "grid").mkdir(exist_ok=True)
    (root / "solar").mkdir(exist_ok=True)
    return root


class CheckedStore(MemoryStore):
    """MemoryStore that records Firestore-safety problems (R7) in every written document (tests only)."""

    def __init__(self) -> None:
        super().__init__()
        self.problems: list[tuple[str, list[str]]] = []

    def _check(self, path: str, data: dict | None) -> None:
        if data is not None and (found := firestore_safe_problems(data)):
            self.problems.append((path, found[:3]))

    def set_doc(self, path: str, data: dict) -> None:
        self._check(path, data)
        super().set_doc(path, data)

    def update_doc(self, path: str, data: dict) -> None:
        self._check(path, data)
        super().update_doc(path, data)

    def batch_set(self, items: list[tuple[str, dict]]) -> None:
        for path, data in items:
            self._check(path, data)
        super().batch_set(items)

    def transact(self, read_paths, fn):
        def checked(snapshot):
            writes = fn(snapshot)
            for path, data in writes:
                self._check(path, data)
            return writes
        return super().transact(read_paths, checked)


def build_fake_deps(store, scenarios_dir: Path, seed_dir: Path | None = None, replies: dict | None = None,
                    **overrides):
    from kirchhoff.agents.runner import ReplayRunner

    from .blobs import MemoryBlobStore
    from .deps import Deps

    engine = overrides.pop("engine", None) or FakeEngine()
    kw = dict(store=store, engine=engine, runner=ReplayRunner({**FAKE_REPLIES, **(replies or {})}),
              enterprise=FakeEnterprise(), blobs=MemoryBlobStore(), scenarios_dir=Path(scenarios_dir),
              seed_dir=Path(seed_dir or scenarios_dir), voice_runner=ReplayRunner(dict(replies or {})),
              asset_engines={k: getattr(engine, f"evaluate_{k}") for k in ("grid", "solar")
                             if hasattr(engine, f"evaluate_{k}")})
    kw.update(overrides)
    return Deps(**kw)
