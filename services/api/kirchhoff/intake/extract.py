"""Gemini native PDF reading (spec §6.3). Output is untrusted until verify_quote accepts it."""
import logging
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator

from kirchhoff.agents.runner import AgentResult, AgentRunner, Attachment, run_json
from kirchhoff.agents.specs import INTAKE, INTAKE_DRAWING

from .drawing import DrawingRead

log = logging.getLogger("kirchhoff.intake")


class ExtractedRequirement(BaseModel):
    key: str
    clause: str | None = None  # untrusted free text; brief.py normalises it and checks it is printed on the page
    page: int
    verbatim_quote: str
    value: float | str | None = None
    unit: str | None = None


class ExtractedContradiction(BaseModel):
    # Only the pages and quotes are needed to verify a contradiction; every other field is free text that
    # brief.py normalises or replaces, so a missing one never costs the pair.
    topic: str = ""
    clause_a: str | None = None
    page_a: int
    quote_a: str
    value_a: str | None = None
    clause_b: str | None = None
    page_b: int
    quote_b: str
    value_b: str | None = None
    summary: str | None = None


def _valid_items(items: Any, model: type[BaseModel], field: str) -> Any:
    """P2 final fix wave (Minor 6): one malformed item (say `"page": "four"`) is dropped on its own instead of
    failing the whole extraction, which forced a lossy JSON repair. A field that is not a list still fails."""
    if not isinstance(items, list):
        return items
    kept = []
    for i, item in enumerate(items):
        try:
            kept.append(model.model_validate(item))
        except ValidationError as exc:
            log.warning("intake: dropped %s[%d]: %s", field, i, "; ".join(
                f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in exc.errors()))
    return kept


class TenderExtraction(BaseModel):
    requirements: list[ExtractedRequirement]
    contradictions: list[ExtractedContradiction] = []

    @field_validator("requirements", mode="before")
    @classmethod
    def _requirements(cls, v: Any) -> Any:
        return _valid_items(v, ExtractedRequirement, "requirements")

    @field_validator("contradictions", mode="before")
    @classmethod
    def _contradictions(cls, v: Any) -> Any:
        return _valid_items(v, ExtractedContradiction, "contradictions")


TENDER_PROMPT = """Read the attached tender PDF. Pages are numbered from 1 in PDF order.
Return JSON {"requirements": [...], "contradictions": [...]}.
requirements: one item per design requirement or design input, each with
  key: a snake_case name such as max_lead_time_weeks, rack_kw or dv_max_pct;
  clause: the clause id exactly as printed, for example "§4.6"; appendix clauses as "App. B";
  page: the PDF page number on which the quote appears;
  verbatim_quote: an exact contiguous phrase copied character for character from that page, including
    punctuation and symbols, that contains the value;
  value: the number as printed (or a short label such as "2N" or "N+1"; null if the requirement has no value);
  unit: the unit as printed, or null.
Do not treat standard numbers such as IEC 60364 as values. Include design inputs stated only in an
appendix (for example an appendix clause that allows a different topology, tolerance or limit from the
main body) as requirements too, citing the appendix clause id -- an appendix alternative is itself a
design input, not just something to compare in contradictions.
contradictions: pairs of clauses that literally conflict with each other, not clauses that merely
share a topic without disagreeing. Compare every appendix clause against the main-body clause on the
SAME topic -- especially redundancy or topology, lead times and other numeric limits -- and report a
pair only when they actually disagree. Each item has topic (one or two lowercase words), clause_a,
page_a, quote_a, value_a, clause_b, page_b, quote_b, value_b and summary (one sentence; no digits
except clause ids and topology names). quote_a and quote_b must each be copied character for
character from the page, including punctuation and symbols, never paraphrased or reconstructed from
memory -- if you are not certain both quotes are exact and the clauses truly conflict, omit that
contradiction entirely rather than invent or paraphrase one."""

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
