"""Shapes of the bids inbox triage (spec §20). InboxExtraction is the agent's untrusted output; everything else is
built by code from verified quotes, ERP records and engine results (spec §6.3, P2 ruling R14)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict

AttachmentKind = Literal["tender", "drawing", "addendum", "boq", "brochure", "other"]
AssetType = Literal["datahall", "grid", "solar", "substation", "other"]
FieldKey = Literal["client", "site", "asset_type", "mw", "redundancy", "bid_due", "lead_time_weeks"]
Verification = Literal["verified", "unverified_scan", "unverified"]
Verdict = Literal["pursue", "clarify", "decline"]
ReasonStatus = Literal["pass", "warn", "fail", "n/a"]  # the FindingStatus vocabulary, rendered with icon + text
FIELD_ORDER: tuple[FieldKey, ...] = ("client", "site", "asset_type", "mw", "redundancy", "bid_due", "lead_time_weeks")
FIELD_LABELS: dict[str, str] = {"client": "Client", "site": "Site", "asset_type": "Asset type", "mw": "Load",
                                "redundancy": "Redundancy", "bid_due": "Bid due", "lead_time_weeks": "Lead-time limit"}
ASSET_LABELS: dict[str, str] = {"datahall": "AI data hall", "grid": "Grid", "solar": "Solar",
                                "substation": "Substation", "other": "Other"}


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- agent output (untrusted until verified) -------------------------------------------------------------------
class RawAttachment(BaseModel):
    attachment_id: str
    kind: AttachmentKind = "other"


class RawField(BaseModel):
    key: FieldKey
    value: float | str | None = None
    unit: str | None = None
    source: str = "body"  # "body" or an attachment id
    page: int | None = None  # 1-based PDF page when source is an attachment
    verbatim_quote: str = ""


class RawCrm(BaseModel):
    account: str | None = None
    opportunity_id: str | None = None
    propose_new: bool = False


class InboxExtraction(BaseModel):
    is_bid: bool
    summary: str = ""
    attachments: list[RawAttachment] = []
    fields: list[RawField] = []
    crm: RawCrm = RawCrm()


# ---- triage result (code-built) ---------------------------------------------------------------------------------
class AttachmentTriage(_M):
    attachment_id: str
    name: str
    kind: AttachmentKind
    scanned: bool  # no page has a text layer: nothing on it can be verified


class ExtractedField(_M):
    key: FieldKey
    label: str
    value: float | str | None  # None when withheld (unverified and not digit-free text)
    unit: str | None = None
    display: str  # code-formatted from the verified value
    source: str  # "body" or an attachment id
    source_label: str  # "Email body" or "{attachment name} · p.{page}"
    page: int | None = None
    quote: str = ""  # the verified verbatim quote (normalized); "" when unverified
    verification: Verification
    bbox: list[float] | None = None


class CrmLink(_M):
    account: str | None = None
    opportunity_id: str | None = None  # an existing opportunity, checked against the CRM list
    opportunity_name: str | None = None
    stage: str | None = None
    proposed: bool = False  # no existing opportunity matches: Pursue creates one
    proposed_name: str | None = None


class FitReason(_M):
    rule: Literal["asset_pack", "mw_range", "region", "deadline", "supply", "not_a_bid"]
    status: ReasonStatus
    text: str


class SupplyCheck(_M):
    status: Literal["ok", "swap", "risk", "not_assessed"]
    text: str
    topology: str | None = None
    mw: float | None = None
    lead_limit_weeks: float | None = None
    material_id: str | None = None
    lead_time_weeks: int | None = None
    stock: int | None = None
    swap_to: str | None = None
    swap_stock: int | None = None


class FitResult(_M):
    verdict: Verdict | None  # None: not a bid
    headline: str
    reasons: list[FitReason]
    supply: SupplyCheck | None = None


class TriageResult(_M):
    email_id: str
    is_bid: bool
    summary: str  # LLM text, sanitized
    attachments: list[AttachmentTriage]
    fields: list[ExtractedField]
    crm: CrmLink
    fit: FitResult
    quotes_verified: int
    quotes_total: int
    source: Literal["live", "precomputed"]
    model: str
    triaged_at: float
    tokens_in: int = 0
    tokens_out: int = 0


class PursueResult(_M):
    email_id: str
    project_id: str
    project_name: str | None  # None for an existing world project: the UI names it from world.json
    project_created: bool
    opportunity_id: str
    opportunity_name: str
    stage: str
    previous_stage: str | None
    opportunity_created: bool
    open: str | None  # the app route to open next (Hall B's intake), or None
