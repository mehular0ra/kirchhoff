"""Ports WS2 consumes: the WS4 enterprise sandbox client and the engine's ErpView."""
from pathlib import Path
from typing import Protocol

import yaml

from kirchhoff.contracts import CrmOverlay, Material, PRLine, PurchaseRequisition

HALL_B_OPPORTUNITY_ID = "opp-hall-b"
STAGE_DESIGN_APPROVED = "Design approved"


class EnterpriseClient(Protocol):
    """WS4 provides kirchhoff.enterprise.client.make_enterprise_client() -> EnterpriseClient (no network at
    construction). All visitor data is scoped by uid."""

    def list_materials(self) -> list[Material]: ...
    def create_pr(self, uid: str, project_id: str, revision: str, lines: list[PRLine],
                  idempotency_key: str) -> PurchaseRequisition: ...
    def set_pr_status(self, uid: str, pr_id: str, status: str) -> None: ...
    def set_opportunity_stage(self, uid: str, opportunity_id: str, stage: str) -> CrmOverlay: ...
    def reset_visitor(self, uid: str) -> None: ...


class ErpSnapshot:
    """Implements the engine facade's ErpView over a materials list."""

    def __init__(self, materials: list[Material]) -> None:
        self._by_id = {m.id: m for m in materials}

    def get(self, material_id: str) -> Material:
        return self._by_id[material_id]

    def search(self, category: str) -> list[Material]:
        return sorted((m for m in self._by_id.values() if m.category == category), key=lambda m: m.id)

    def ids(self) -> list[str]:
        return sorted(self._by_id)


def load_erp_seed(path: Path | str) -> list[Material]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    items = data["materials"] if isinstance(data, dict) else data
    return [Material.model_validate(m) for m in items]
