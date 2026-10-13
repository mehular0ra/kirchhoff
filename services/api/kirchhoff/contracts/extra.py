"""WS1 additions to the frozen contracts (new models only)."""
from typing import Any

from .common import Strict


class FixCandidate(Strict):
    id: str  # "FA-01:upsize-BW-2000"
    finding_id: str  # "R05:FA-01"
    label: str  # "Upsize FA-01 to 2,000 A busway"
    cost_delta: float  # USD
    metrics: dict[str, float]  # e.g. {"dv_pct": 1.66}
    patch: dict[str, Any]  # engine-internal description consumed by apply_fix


class ClashReport(Strict):
    clashes: list[dict[str, Any]]  # [{"a": "H-Z2", "b": "FB-03", "kind": "solid", "at": [x, y, z]}]
