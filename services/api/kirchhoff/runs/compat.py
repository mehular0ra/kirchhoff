"""FixCandidate / ClashReport live in WS1's kirchhoff/contracts/extra.py. Until that lands, identical local
shapes (2026-10-13-interfaces.md) keep WS2 testable. Task 18 deletes this module."""
from typing import Any

try:
    from kirchhoff.contracts.extra import ClashReport, FixCandidate
except ImportError:
    from kirchhoff.contracts.common import Strict

    class FixCandidate(Strict):  # type: ignore[no-redef]
        id: str
        finding_id: str
        label: str
        cost_delta: float
        metrics: dict[str, float]
        patch: dict[str, Any]

    class ClashReport(Strict):  # type: ignore[no-redef]
        clashes: list[dict[str, Any]]

__all__ = ["ClashReport", "FixCandidate"]
