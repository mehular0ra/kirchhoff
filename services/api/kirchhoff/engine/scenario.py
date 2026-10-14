"""Scenario files (spec §9): tender.yaml, catalogue.yaml, geometry.yaml under <repo>/scenarios/<name>/."""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

LABEL = "IEC-based, illustrative, not for construction"
CATALOGUE_SECTIONS = ("transformers", "busways", "cables", "breakers", "ups", "sts", "switchboards", "cdus", "pipes")
_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


@dataclass(frozen=True)
class Scenario:
    name: str  # "hall_a"
    tender: dict  # parsed tender.yaml (clauses with ids, text, limits)
    catalogue: dict  # parsed catalogue.yaml
    geometry: dict  # parsed geometry.yaml


def scenarios_root(root: Path | None = None) -> Path:
    """The directory that contains one folder per scenario (<repo>/scenarios)."""
    if root is not None:
        return Path(root)
    env = os.environ.get("KIRCHHOFF_SCENARIOS_DIR")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        cand = parent / "scenarios"
        if (cand / "hall_a" / "tender.yaml").exists():
            return cand
    raise FileNotFoundError("scenarios/ directory not found; set KIRCHHOFF_SCENARIOS_DIR")


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_scenario(name: str = "hall_a", root: Path | None = None) -> Scenario:
    if not _NAME_RE.fullmatch(name):
        raise ValueError(f"invalid scenario name {name!r}; must match [a-z0-9_-]+")
    base = scenarios_root(root) / name
    return Scenario(name=name, tender=_read_yaml(base / "tender.yaml"),
                    catalogue=_read_yaml(base / "catalogue.yaml"), geometry=_read_yaml(base / "geometry.yaml"))


def clause(scn: Scenario, clause_id: str) -> dict:
    for c in scn.tender["clauses"]:
        if c["id"] == clause_id:
            return c
    raise KeyError(clause_id)


def limit_clause(scn: Scenario, key: str) -> dict:
    for c in scn.tender["clauses"]:
        if key in (c.get("limits") or {}):
            return c
    raise KeyError(f"no tender clause defines limit {key!r}")


def limit(scn: Scenario, key: str) -> float:
    return float(limit_clause(scn, key)["limits"][key])


def with_limit(scn: Scenario, key: str, value: float) -> Scenario:
    """A copy of the scenario with one tender limit overridden (used by what-ifs and the benchmark)."""
    import copy
    from dataclasses import replace

    tender = copy.deepcopy(scn.tender)
    for c in tender["clauses"]:
        if key in (c.get("limits") or {}):
            c["limits"][key] = value
            return replace(scn, tender=tender)
    raise KeyError(key)


def cat_item(scn: Scenario, item_id: str) -> dict:
    for section in CATALOGUE_SECTIONS:
        for item in scn.catalogue.get(section, []):
            if item["id"] == item_id:
                return item
    raise KeyError(f"catalogue item {item_id!r} not found")


def cat_section(scn: Scenario, section: str) -> list[dict]:
    return list(scn.catalogue[section])
