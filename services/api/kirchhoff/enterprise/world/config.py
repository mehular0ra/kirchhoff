"""The authored demo world (scenarios/demo_world/world.yaml, spec §13), typed and validated."""
import random
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

HISTORICAL_PR_BASE = 101
PUNE_PR_BASE = 121
HALL_A_PR_BASE = 142
DAY_S = 86400.0


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Org(_M):
    name: str
    tagline: str | None = None


class Person(_M):
    id: str
    name: str
    role: str
    initials: str | None = None


class ProjectCfg(_M):
    id: str
    name: str
    client: str
    asset_pack: Literal["datahall", "grid", "solar"]
    state: Literal["not_started", "running", "in_review", "checked", "draft", "signed", "archived"]
    days_ago: float
    opportunity: str | None = None


class OpportunityCfg(_M):
    id: str
    account: str
    name: str
    stage: str
    value: tuple[float, float]
    next_step: str = ""


class ExtraMaterialCfg(_M):
    id: str
    category: str
    description: str
    rating: float | None = None
    unit: str | None = None
    voltage: str | None = None
    stock: tuple[int, int]
    lead_time_weeks: int
    unit_price: float
    vendor: str


class PrLineCfg(_M):
    material_id: str
    qty: tuple[int, int]


class HistoricalPrCfg(_M):
    project_id: str
    revision: str
    days_ago: float
    status: Literal["draft", "submitted", "blocked"] = "submitted"
    lines: list[PrLineCfg]


class ActivityCfg(_M):
    days_ago: float
    actor: str
    project_id: str | None = None
    text: str


class WorldConfig(_M):
    seed: int
    now: float
    notice: str
    org: Org
    people: list[Person]
    accounts: list[str]
    projects: list[ProjectCfg]
    opportunities: list[OpportunityCfg]
    extra_materials: list[ExtraMaterialCfg]
    historical_prs: list[HistoricalPrCfg] = []
    activity: list[ActivityCfg] = []

    def ts(self, days_ago: float) -> float:
        return round(self.now - days_ago * DAY_S, 3)

    def project(self, pid: str) -> ProjectCfg:
        return next(p for p in self.projects if p.id == pid)


def load_world_config(path: Path | str) -> WorldConfig:
    return WorldConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def rng_for(cfg: WorldConfig, purpose: str) -> random.Random:
    """One reproducible stream per purpose (str seeds are hashed with SHA-512: stable across processes)."""
    return random.Random(f"{cfg.seed}:{purpose}")
