"""ERP and CRM seed for the demo world (spec §9.5, §13.3): Hall A materials verbatim + 40 authored extras, 5 accounts,
9 opportunities and historical PRs. Deterministic for a given world.yaml (ruling W7). Sandbox (simulated)."""
from pathlib import Path
from typing import Iterable

import yaml

from kirchhoff.contracts import Material, Opportunity, PRLine, PurchaseRequisition

from ..model import EnterpriseSeed
from .config import HISTORICAL_PR_BASE, WorldConfig, rng_for


class MaterialsErp:
    """The engine facade's ErpView (get/search) over a materials list."""

    def __init__(self, materials: list[Material]) -> None:
        self._by_id = {m.id: m for m in materials}

    def get(self, material_id: str) -> Material:
        return self._by_id[material_id]

    def search(self, category: str) -> list[Material]:
        return sorted((m for m in self._by_id.values() if m.category == category), key=lambda m: m.id)


def hall_a_materials(scenarios_root: Path) -> list[Material]:
    data = yaml.safe_load((Path(scenarios_root) / "hall_a" / "erp_seed.yaml").read_text(encoding="utf-8"))
    return [Material.model_validate(m) for m in data["materials"]]


def build_materials(cfg: WorldConfig, hall_a: list[Material]) -> list[Material]:
    rng = rng_for(cfg, "materials")
    extras = [Material(id=x.id, category=x.category, description=x.description, rating=x.rating, unit=x.unit,
                       voltage=x.voltage, stock=rng.randint(*x.stock), lead_time_weeks=x.lead_time_weeks,
                       unit_price=x.unit_price, vendor=x.vendor) for x in cfg.extra_materials]
    ids = [m.id for m in hall_a] + [m.id for m in extras]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate material ids: {dupes}")
    return sorted(hall_a + extras, key=lambda m: m.id)


def build_opportunities(cfg: WorldConfig) -> list[Opportunity]:
    unknown = sorted({o.account for o in cfg.opportunities} - set(cfg.accounts))
    if unknown:
        raise ValueError(f"opportunities reference unknown accounts: {unknown}")
    rng = rng_for(cfg, "crm")
    opps = [Opportunity(id=o.id, account=o.account, name=o.name, stage=o.stage,
                        value=float(round(rng.uniform(*o.value), -4)), next_step=o.next_step)
            for o in cfg.opportunities]
    return sorted(opps, key=lambda o: o.id)


def build_historical_prs(cfg: WorldConfig, materials: list[Material]) -> list[PurchaseRequisition]:
    rng = rng_for(cfg, "prs")
    by_id = {m.id: m for m in materials}
    out = []
    for i, h in enumerate(sorted(cfg.historical_prs, key=lambda h: (-h.days_ago, h.project_id))):
        lines = []
        for line in h.lines:
            m = by_id[line.material_id]
            lines.append(PRLine(material_id=m.id, description=m.description, qty=rng.randint(*line.qty),
                                unit_price=m.unit_price, lead_time_weeks=m.lead_time_weeks))
        out.append(PurchaseRequisition(id=f"PR-2026-{HISTORICAL_PR_BASE + i:04d}", project_id=h.project_id,
                                       revision=h.revision, lines=lines, status=h.status,
                                       created_at=cfg.ts(h.days_ago)))
    return out


def build_enterprise_seed(cfg: WorldConfig, materials: list[Material],
                          project_prs: Iterable[PurchaseRequisition] = ()) -> EnterpriseSeed:
    prs = build_historical_prs(cfg, materials) + list(project_prs)
    ids = [p.id for p in prs]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate PR ids: {sorted({i for i in ids if ids.count(i) > 1})}")
    known = {m.id for m in materials}
    missing = sorted({line.material_id for p in prs for line in p.lines} - known)
    if missing:
        raise ValueError(f"PR lines reference unknown materials: {missing}")
    return EnterpriseSeed(notice=cfg.notice, materials=materials, prs=sorted(prs, key=lambda p: p.id),
                          accounts=list(cfg.accounts), opportunities=build_opportunities(cfg))
