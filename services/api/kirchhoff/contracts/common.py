from typing import Literal

from pydantic import BaseModel, ConfigDict

AgentName = Literal["intake", "orchestrator", "layout", "power", "cooling", "procurement",
                    "checker", "docs", "copilot", "asset", "system"]
Phase = Literal["p1", "p2", "p3", "p4"]
EventKind = Literal["plan", "tool_call", "tool_result", "message", "artifact", "finding", "gate",
                    "ledger", "status"]
FindingStatus = Literal["pass", "fail", "warn", "n/a"]
TopologyId = Literal["2N", "DR", "BLOCK"]
AssetPack = Literal["datahall", "grid", "solar"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(Strict):
    doc_id: str
    page: int
    quote: str
    bbox: tuple[float, float, float, float] | None = None  # pdfplumber coords: x0, top, x1, bottom (points)
    clause: str | None = None  # e.g. "§4.6"


class ClauseRef(Strict):
    standard: str  # e.g. "IEC 60364-5-52"
    clause: str | None = None  # e.g. "§525"
