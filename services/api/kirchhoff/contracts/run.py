from typing import Any, Literal

from .common import AgentName, Citation, EventKind, Phase, Strict, TopologyId


class Requirement(Strict):
    id: str  # "REQ-4.6"
    text: str
    value: float | str | None = None
    unit: str | None = None
    citation: Citation
    verified: bool


class OpenQuestion(Strict):
    id: str  # "Q-redundancy"
    text: str
    options: list[str]
    citations: list[Citation]
    default_resolution: str  # used by Auto mode (main body beats appendix)
    resolution: str | None = None


class DesignBrief(Strict):
    project_id: str
    requirements: list[Requirement]
    open_questions: list[OpenQuestion] = []
    intake_score: dict[str, float] = {}  # extracted, verified, recall_vs_ground_truth
    drawing_check: dict[str, Any] = {}  # {"agrees": bool, "differences": [...]}


class PlanStep(Strict):
    id: str
    agent: AgentName
    title: str
    note: str = ""  # engineer's edit


class TopologyOption(Strict):
    id: TopologyId
    installed_mva: float
    normal_loading_pct: float
    failover_loading_pct: float
    cost: float
    losses_kw: float
    max_lead_time_weeks: int
    spof_count: int
    swaps: list[dict[str, Any]] = []  # [{"line": "T", "from": "TX-2500", "to": "TX-3150", "reason": "R15"}]


RunStatus = Literal["running", "at_gate", "done", "expired", "failed"]


class RunRecord(Strict):
    id: str
    project_id: str
    status: RunStatus
    autonomy: Literal["ask", "auto"]
    phase: Phase | None = None
    gate: Literal["plan", "option", "review"] | None = None
    plan: list[PlanStep] = []
    open_questions: list[OpenQuestion] = []
    options: list[TopologyOption] = []
    selected_option: TopologyId | None = None
    metrics: dict[str, float] = {}
    lease: dict[str, Any] | None = None  # {"owner": str, "attempt": int, "heartbeat_at": float}
    started_at: float
    finished_at: float | None = None


class StepRecord(Strict):
    id: str  # "p2.place_racks"
    phase: Phase
    status: Literal["running", "done", "failed"]
    attempt: int
    outputs_ref: str | None = None
    started_at: float
    finished_at: float | None = None


class RunEvent(Strict):
    seq: int
    phase: Phase
    step: str
    attempt: int = 1
    agent: AgentName
    kind: EventKind
    title: str
    detail: str = ""
    payload: dict[str, Any] = {}
    ts: float
