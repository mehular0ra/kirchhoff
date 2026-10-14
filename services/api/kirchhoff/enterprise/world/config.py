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


class RegionCfg(_M):
    name: str
    places: list[str]  # case-insensitive substrings of the extracted site that place it in this region


class Appetite(_M):
    """The firm's bid appetite (spec §20): the deterministic fit rules WS2's kirchhoff.inbox.fit applies."""
    asset_types: list[Literal["datahall", "grid", "solar"]]
    mw: tuple[float, float]
    regions: list[RegionCfg]
    min_days_to_bid_due: int
    lead_time_check: bool = True


class InboxAttachmentCfg(_M):
    id: str
    name: str
    reuse: str | None = None  # a WS2-rendered PDF in scenarios/hall_a/out/, served at /demo/docs/{reuse}
    file: str | None = None  # a PDF rendered by the inbox generator into /demo/inbox/{file}
    render: Literal["letter", "scan"] | None = None
    title: str = ""
    lines: list[str] = []


class InboxEmailCfg(_M):
    id: str
    from_name: str
    from_addr: str
    from_org: str
    subject: str
    days_ago: float
    body: str
    attachments: list[InboxAttachmentCfg] = []
    project_id: str | None = None  # an existing world project this email is about (hall-b)
    live_triage: bool = False


class InboxCfg(_M):
    mailbox: str
    appetite: Appetite
    emails: list[InboxEmailCfg]


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
    inbox: InboxCfg | None = None

    def ts(self, days_ago: float) -> float:
        return round(self.now - days_ago * DAY_S, 3)

    def project(self, pid: str) -> ProjectCfg:
        return next(p for p in self.projects if p.id == pid)


def load_world_config(path: Path | str) -> WorldConfig:
    return WorldConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def rng_for(cfg: WorldConfig, purpose: str) -> random.Random:
    """One reproducible stream per purpose (str seeds are hashed with SHA-512: stable across processes)."""
    return random.Random(f"{cfg.seed}:{purpose}")
