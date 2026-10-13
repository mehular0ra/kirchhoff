"""Engine facade (docs/superpowers/plans/2026-10-13-interfaces.md). WS2 imports only from here.
Pure Python, no LLM calls. IEC-based, illustrative, not for construction."""
import hashlib
import json

from kirchhoff.contracts import DesignModel, Finding, PRLine
from kirchhoff.contracts.extra import ClashReport, FixCandidate  # noqa: F401  (re-exported for WS2)

from .boq import derive_boq, derive_pr_lines  # noqa: F401
from .checker import run_rules
from .cooling import size_cooling  # noqa: F401
from .erp import ErpView, YamlErp, default_erp  # noqa: F401
from .fixes import apply_fix, fix_candidates  # noqa: F401
from .layout import place_racks  # noqa: F401
from .options import annotate_options, power_options, power_recheck  # noqa: F401
from .routing import route  # noqa: F401
from .scenario import Scenario, load_scenario  # noqa: F401
from .spatial import detect_clashes  # noqa: F401

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


def check(scn: Scenario, model: DesignModel, erp: ErpView, pr_lines: list[PRLine] | None = None) -> list[Finding]:
    """Full rule pack R01–R15 incl. R04b; one Finding per (rule, element) incl. passes."""
    return run_rules(scn, model, erp, pr_lines)


def model_hash(model: DesignModel) -> str:
    """SHA-256 of the canonical model JSON (sorted keys, compact separators)."""
    canonical = json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ledger_not_checked() -> list[str]:
    """Spec §8.4 items shown in the assumptions ledger as "not checked"."""
    return list(NOT_CHECKED)
