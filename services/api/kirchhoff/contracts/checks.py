from typing import Any, Literal

from .common import AgentName, Citation, ClauseRef, FindingStatus, Strict
from .design import DesignModel


class Finding(Strict):
    id: str  # f"{rule_id}:{element_id}"
    rule_id: str  # "R05"
    element_id: str  # "FA-01"
    status: FindingStatus
    title: str
    clause_refs: list[ClauseRef] = []
    tender_refs: list[Citation] = []
    formula: str = ""
    inputs: dict[str, float | str] = {}
    value: float | None = None
    limit: float | None = None
    unit: str | None = None
    explanation: str = ""  # may contain {value}/{limit} placeholders
    fix: dict[str, Any] | None = None  # {"candidate": "...", "reason": "...", "deltas": {...}}
    rejected_fix: dict[str, Any] | None = None


class LedgerEntry(Strict):
    kind: Literal["did", "assumed", "not_checked"]
    agent: AgentName
    text: str


class Revision(Strict):
    id: str  # "r1"
    project_id: str
    parent: str | None = None
    author: str
    hash: str  # sha256 of canonical model JSON
    model: DesignModel | None = None
    model_url: str | None = None
    summary: str = ""
    check_summary: dict[str, int] = {}  # {"pass": n, "fail": n, "warn": n, "n/a": n}
    status: Literal["draft", "checked", "signed"]
    ledger: list[LedgerEntry] = []
    created_at: float


class WhatIfResult(Strict):
    revision_ref: str  # "seed:hall-a@r2" | "ws:r2"
    param: Literal["rack_kw", "liquid_fraction", "dv_limit_pct", "tx_loading_cap_pct"]
    value: float
    findings: list[Finding]
    impact_chain: list[list[str]]  # ordered element-id paths, e.g. [["R1-01","A-01","A1","T-A1"], ...]
