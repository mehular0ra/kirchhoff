"""Engine facade (docs/superpowers/plans/2026-10-13-interfaces.md). WS2 imports only from here.
Pure Python, no LLM calls. IEC-based, illustrative, not for construction."""
import hashlib
import json

from kirchhoff.contracts import DesignModel
from kirchhoff.contracts.extra import ClashReport, FixCandidate  # noqa: F401  (re-exported for WS2)

from .erp import ErpView, YamlErp, default_erp  # noqa: F401
from .scenario import Scenario, load_scenario  # noqa: F401

NOT_CHECKED = [
    "Earth-fault loop impedance (IEC 60364-4-41 §411)",
    "Selectivity between protective devices",
    "Arc flash",
    "Harmonics",
    "Air-side cooling for the air-cooled share of rack heat",
    "MV bus faults",
    "Busway derating above 35 °C ambient (ambient assumed ≤ 35 °C)",
    "Overload protection (R03) of transformer incomer and UPS breakers: sized to equipment rating, checked by R04 only",
    "Short-circuit withstand of cable feeders",
]


def model_hash(model: DesignModel) -> str:
    """SHA-256 of the canonical model JSON (sorted keys, compact separators)."""
    canonical = json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ledger_not_checked() -> list[str]:
    """Spec §8.4 items shown in the assumptions ledger as "not checked"."""
    return list(NOT_CHECKED)
