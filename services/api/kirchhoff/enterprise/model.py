"""WS4-local shapes for the ERP/CRM sandbox seed (the frozen contracts are reused, never extended)."""
import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from kirchhoff.contracts import Material, Opportunity, PurchaseRequisition

FICTIONAL_NOTICE = "Demo workspace — all companies, people and data are fictional"
SANDBOX_LABEL = "sandbox (simulated)"
ILLUSTRATIVE = "IEC-based, illustrative values, not for construction"

FALLBACK_OPPORTUNITIES = [
    Opportunity(id="opp-hall-a", account="Deccan Compute", name="Hall A design-build", stage="Design approved",
                value=18_500_000.0, next_step="Issue purchase requisitions"),
    Opportunity(id="opp-hall-b", account="Deccan Compute", name="Hall B design-build", stage="Design in progress",
                value=18_500_000.0, next_step="Run the Hall B design"),
]


class EnterpriseSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notice: str = FICTIONAL_NOTICE
    label: str = SANDBOX_LABEL
    materials: list[Material]
    prs: list[PurchaseRequisition] = []
    accounts: list[str] = []
    opportunities: list[Opportunity] = []


def canonical_json(value) -> str:
    """Sorted keys, compact separators, UTF-8 text: the hashing form for every WS4 artefact."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def seed_hash(seed: EnterpriseSeed) -> str:
    return hashlib.sha256(canonical_json(seed.model_dump(mode="json")).encode("utf-8")).hexdigest()


def load_enterprise_seed(path: Path | str) -> EnterpriseSeed:
    return EnterpriseSeed.model_validate_json(Path(path).read_text(encoding="utf-8"))


def fallback_seed(erp_seed_yaml: Path | str) -> EnterpriseSeed:
    """Hall A materials + the two Hall opportunities; used only when the generated seed file is missing."""
    p = Path(erp_seed_yaml)
    materials: list[Material] = []
    if p.exists():
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        materials = [Material.model_validate(m) for m in data.get("materials", [])]
    return EnterpriseSeed(materials=materials, accounts=["Deccan Compute"],
                          opportunities=list(FALLBACK_OPPORTUNITIES))
