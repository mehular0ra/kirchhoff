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
