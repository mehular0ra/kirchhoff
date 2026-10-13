from typing import Literal

from .checks import Finding, Revision, WhatIfResult
from .common import AssetPack, Strict
from .enterprise import CrmOverlay, PurchaseRequisition
from .run import DesignBrief, RunEvent, RunRecord, StepRecord


class Project(Strict):
    id: str  # "hall-a", "hall-b", "pune-edge-1", "grid-132kv", "solar-5mwp", "vindhya-lv"
    name: str
    client: str
    asset_pack: AssetPack
    state: Literal["not_started", "running", "in_review", "checked", "draft", "signed", "archived"]
    sample: bool
    updated_at: float


class Approval(Strict):
    id: str
    revision: str
    approver_name: str
    role: str
    decision: Literal["approved", "rejected"]
    comment: str = ""
    ts: float


class ProjectBundle(Strict):
    project: Project
    brief: DesignBrief | None = None
    runs: list[RunRecord] = []
    steps: list[StepRecord] = []
    events: list[RunEvent] = []
    revisions: list[Revision] = []
    findings: dict[str, list[Finding]] = {}  # revision id -> findings
    approvals: list[Approval] = []
    prs: list[PurchaseRequisition] = []
    crm: CrmOverlay | None = None
    what_ifs: list[WhatIfResult] = []
