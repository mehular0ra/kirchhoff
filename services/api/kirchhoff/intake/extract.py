"""Gemini native PDF reading (spec §6.3). Output is untrusted until verify_quote accepts it."""
from pydantic import BaseModel

from kirchhoff.agents.runner import AgentResult, AgentRunner, Attachment, run_json
from kirchhoff.agents.specs import INTAKE, INTAKE_DRAWING

from .drawing import DrawingRead


class ExtractedRequirement(BaseModel):
    key: str
    clause: str
    page: int
    verbatim_quote: str
    value: float | str | None = None
    unit: str | None = None


class ExtractedContradiction(BaseModel):
    topic: str
    clause_a: str
    page_a: int
    quote_a: str
    value_a: str
    clause_b: str
    page_b: int
    quote_b: str
    value_b: str
    summary: str


class TenderExtraction(BaseModel):
    requirements: list[ExtractedRequirement]
    contradictions: list[ExtractedContradiction] = []


TENDER_PROMPT = """Read the attached tender PDF. Pages are numbered from 1 in PDF order.
Return JSON {"requirements": [...], "contradictions": [...]}.
requirements: one item per design requirement or design input, each with
  key: a snake_case name such as max_lead_time_weeks, rack_kw or dv_max_pct;
  clause: the clause id exactly as printed, for example "§4.6"; appendix clauses as "App. B";
  page: the PDF page number on which the quote appears;
  verbatim_quote: an exact contiguous phrase copied from that page that contains the value;
  value: the number as printed (or a short label such as "2N" or "N+1"; null if the requirement has no value);
  unit: the unit as printed, or null.
Do not treat standard numbers such as IEC 60364 as values.
contradictions: pairs of clauses that conflict, each with topic (one or two lowercase words), clause_a, page_a,
quote_a, value_a, clause_b, page_b, quote_b, value_b and summary (one sentence; no digits except clause ids and
topology names)."""

DRAWING_PROMPT = """The attached PDF is a general-arrangement plot of a data hall. Read the structural grid bubble
labels along the bottom from left to right and along the left side from bottom to top, and the two overall
dimension strings in millimetres. Reply with JSON {"grid_x": [...], "grid_y": [...],
"overall_mm": [length_along_x, width_along_y]}."""


def extract_tender(runner: AgentRunner, pdf_bytes: bytes) -> tuple[TenderExtraction, AgentResult]:
    return run_json(runner, INTAKE, "p1.extract", TENDER_PROMPT, TenderExtraction,
                    attachments=[Attachment(pdf_bytes, "application/pdf")])


def read_drawing(runner: AgentRunner, plan_pdf_bytes: bytes) -> tuple[DrawingRead, AgentResult]:
    return run_json(runner, INTAKE_DRAWING, "p1.drawing", DRAWING_PROMPT, DrawingRead,
                    attachments=[Attachment(plan_pdf_bytes, "application/pdf")])
