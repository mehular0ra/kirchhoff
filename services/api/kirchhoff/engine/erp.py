"""ERP views. The facade takes any object with get/search (ErpView); YamlErp reads scenarios/<name>/erp_seed.yaml
and is what tests, the benchmark and offline runs use. WS4's sandbox client implements the same protocol."""
from pathlib import Path
from typing import Protocol

import yaml

from kirchhoff.contracts import Material

from .scenario import scenarios_root


class ErpView(Protocol):
    def get(self, material_id: str) -> Material: ...
    def search(self, category: str) -> list[Material]: ...


class YamlErp:
    def __init__(self, materials: list[Material]) -> None:
        self._by_id = {m.id: m for m in materials}

    @classmethod
    def from_file(cls, path: Path) -> "YamlErp":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls([Material(**m) for m in data["materials"]])

    def get(self, material_id: str) -> Material:
        return self._by_id[material_id]

    def search(self, category: str) -> list[Material]:
        return sorted((m for m in self._by_id.values() if m.category == category), key=lambda m: m.id)

    def all(self) -> list[Material]:
        return sorted(self._by_id.values(), key=lambda m: m.id)

    def with_material(self, material: Material) -> "YamlErp":
        """A copy with one material replaced (benchmark mutations)."""
        items = dict(self._by_id)
        items[material.id] = material
        return YamlErp(list(items.values()))


def default_erp(name: str = "hall_a", root: Path | None = None) -> YamlErp:
    return YamlErp.from_file(scenarios_root(root) / name / "erp_seed.yaml")


def effective_lead_weeks(material: Material, qty: int) -> int:
    """0 when the ERP holds enough stock for the whole quantity, else the quoted lead time."""
    return 0 if material.stock >= qty else material.lead_time_weeks
