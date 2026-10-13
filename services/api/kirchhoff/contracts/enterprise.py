from typing import Literal

from .common import Strict


class Material(Strict):
    id: str  # "TX-3150"
    category: str  # "transformer", "busway", "ups_module", "sts", "cdu", "pipe", "breaker", "cable"
    description: str
    rating: float | None = None
    unit: str | None = None
    voltage: str | None = None
    stock: int
    lead_time_weeks: int
    unit_price: float  # USD
    vendor: str


class PRLine(Strict):
    material_id: str
    description: str
    qty: int
    unit_price: float
    lead_time_weeks: int


class PurchaseRequisition(Strict):
    id: str  # "PR-2026-0142"
    project_id: str
    revision: str
    lines: list[PRLine]
    status: Literal["draft", "submitted", "blocked"]
    created_at: float


class Opportunity(Strict):
    id: str
    account: str
    name: str
    stage: str
    value: float
    next_step: str = ""


class CrmOverlay(Strict):
    opportunity_id: str
    stage: str
    updated_at: float
