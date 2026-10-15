"""Inbox agent triage (spec §20). Gemini classifies the attachments, links the CRM and extracts bid fields with
verbatim quotes. Code verifies every quote (pdfplumber `verify_quote` on PDF pages that have text, a normalized
substring check on the email body), marks pages without a text layer "unverified (scan)", withholds unverified
values (never shown), sanitizes the LLM summary (spec §6.3) and runs the deterministic fit check, whose sentences
are sanitized too (see fit.py). A number is verified together with its unit, and the unit, source and page that reach
the UI are chosen by code, never copied from agent text."""
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from kirchhoff.agents.prose_guard import prose_is_safe
from kirchhoff.agents.runner import MODEL, AgentRunner, AgentSpec, Attachment, run_json
from kirchhoff.agents.specs import INBOX
from kirchhoff.agents.trust import fmt_value, sanitize
from kirchhoff.contracts import Opportunity
from kirchhoff.enterprise.world.inbox import Appetite, InboxEmail
from kirchhoff.intake.textnorm import normalize
from kirchhoff.intake.verify import PdfText, unit_in_quote, value_in_quote, verify_quote

from .fit import SupplyFn, assess_fit, day_zero_supply, fmt_date, parse_due, supply_for
from .models import (ASSET_LABELS, FIELD_LABELS, FIELD_ORDER, AttachmentTriage, CrmLink, ExtractedField,
                     InboxExtraction, RawCrm, RawField, TriageResult)

NUMERIC = ("mw", "lead_time_weeks")
UNITS = {"mw": ("MW", "MWp"), "lead_time_weeks": ("weeks",)}  # the only units a number is checked and shown with
TRIAGE_PROMPT = """Triage this email from the bids@ mailbox of Meridian Power Engineering, an EPC contractor for AI data
halls, grid connections and solar plants. The attached PDFs follow in the order listed under "Attachments".
Reply with JSON only:
{"is_bid": true if the email asks Meridian to bid or quote, else false,
 "summary": one sentence with no quantity in digits or words and no braces,
 "attachments": [{"attachment_id": a listed id, "kind": "tender"|"drawing"|"addendum"|"boq"|"brochure"|"other"}],
 "fields": [{"key": a field key, "value": the value, "unit": the unit or null, "source": "body" or an attachment id,
             "page": the PDF page number from 1, or null for the body,
             "verbatim_quote": an exact contiguous phrase copied from that page or from the body that contains the value}],
 "crm": {"account": one of the CRM accounts listed below or null, "opportunity_id": a listed opportunity id or null,
         "propose_new": true when this is a bid and no listed opportunity matches it}}
Field keys (omit a field you cannot find; never guess or paraphrase):
  client: the client company name as written;
  site: the site location as written, town and state;
  asset_type: one of "datahall", "grid", "solar", "substation", "other"; quote the phrase that shows it;
  mw: the IT or plant load in MW (MWp for solar) as a number;
  redundancy: the power redundancy as written, for example "2N";
  bid_due: the bid or quotation due date exactly as written, for example "13 November 2026";
  lead_time_weeks: the maximum equipment lead time in weeks as a number.
A value that appears only on a scanned image still counts: report it with its page."""


def build_message(email: InboxEmail, opportunities: Sequence[Opportunity]) -> str:
    lines = [TRIAGE_PROMPT, "", f"From: {email.from_name} <{email.from_addr}> ({email.from_org})", f"To: {email.to}",
             f"Subject: {email.subject}", "Body:", email.body, "", "Attachments:"]
    lines += [f"{i}. {a.id}: {a.name}" for i, a in enumerate(email.attachments, 1)] or ["(none)"]
    lines += ["", "CRM opportunities (id | account | name | stage):"]
    lines += [f"{o.id} | {o.account} | {o.name} | {o.stage}" for o in opportunities]
    return "\n".join(lines)


def _number(value) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _display(key: str, value, unit: str | None) -> str:
    if key == "asset_type":
        return ASSET_LABELS[str(value)]
    if key == "mw":
        return fmt_value(value, unit or "MW")
    if key == "lead_time_weeks":
        return fmt_value(value, "weeks")
    if key == "bid_due":
        d = parse_due(str(value))
        return fmt_date(d) if d else str(value)
    return str(value)


def _unit(key: str, requested: str | None, quote: str) -> str | None:
    """The unit a numeric field is checked and shown with. It is always one of UNITS[key], never the agent's own
    text: the requested one when the quote has it, else whichever allowed form the quote has (a solar plant's "MWp")."""
    allowed = UNITS.get(key)
    if allowed is None:
        return None
    first = requested if requested in allowed else allowed[0]
    return first if unit_in_quote(first, quote) else next((u for u in allowed if unit_in_quote(u, quote)), first)


def verify_field(raw: RawField, email: InboxEmail, pdfs: dict[str, PdfText], names: dict[str, str]) -> ExtractedField:
    value = raw.value
    if isinstance(value, str) and not value.strip():
        value = None  # "" is a substring of every quote: an empty value never verifies
    if raw.key in NUMERIC:
        value = _number(value)
    if raw.key == "asset_type":
        value = str(value).casefold() if value is not None else None
        value = value if value in ASSET_LABELS else None
    check_value = None if raw.key == "asset_type" else value  # a category is not printed; its quote must exist
    quote = normalize(raw.verbatim_quote)
    unit = _unit(raw.key, raw.unit, quote)  # a number must be quoted with its unit, as intake does (phase1.py)
    verification, bbox, page = "unverified", None, raw.page
    if raw.source == "body":
        source, source_label, page = "body", "Email body", None
        if (value is not None and len(quote) >= 8 and quote in normalize(email.body) and value_in_quote(check_value, quote)
                and unit_in_quote(unit, quote)):
            verification = "verified"
    else:
        pdf, name = pdfs.get(raw.source), names.get(raw.source)
        source = raw.source if name else "unknown"  # an id the code did not list is agent text, not a source
        if pdf is None or page is None or not 1 <= page <= pdf.page_count:
            page = None  # never echo a page the code could not open
        source_label = f"{name} · p.{page}" if name and page else (name or "Unknown attachment")
        if page is not None:
            if not pdf.page_text(page):
                verification = "unverified_scan"
            elif value is not None:
                chk = verify_quote(pdf, page, raw.verbatim_quote, check_value, unit)
                if chk.ok:
                    verification, bbox = "verified", list(chk.bbox) if chk.bbox else None
    if verification == "verified":
        return ExtractedField(key=raw.key, label=FIELD_LABELS[raw.key], value=value, unit=unit,
                              display=_display(raw.key, value, unit), source=source, source_label=source_label,
                              page=page, quote=quote, verification="verified", bbox=bbox)
    # Spec §6.3 outranks the plan's code: an unverified value is never shown, whatever it looks like. Only its source is.
    display = "Not verified (scan)" if verification == "unverified_scan" else "Not verified"
    return ExtractedField(key=raw.key, label=FIELD_LABELS[raw.key], value=None, display=display, source=source,
                          source_label=source_label, page=page, verification=verification)


def _subject_name(subject: str) -> str:
    return re.sub(r"^((re|fw|fwd)\s*:\s*)+", "", subject, flags=re.IGNORECASE).strip()


def link_crm(raw: RawCrm, is_bid: bool, email: InboxEmail, opportunities: Sequence[Opportunity]) -> CrmLink:
    by_id = {o.id: o for o in opportunities}
    o = by_id.get(raw.opportunity_id or "")
    if o is not None:
        return CrmLink(account=o.account, opportunity_id=o.id, opportunity_name=o.name, stage=o.stage)
    account = raw.account if raw.account in {x.account for x in opportunities} else None
    if is_bid and raw.propose_new:
        return CrmLink(account=account or email.from_org, proposed=True, proposed_name=_subject_name(email.subject))
    return CrmLink(account=account)


def triage_email(email: InboxEmail, *, runner: AgentRunner, scenarios_dir: Path, opportunities: Sequence[Opportunity],
                 erp, appetite: Appetite, as_of: float, source: Literal["live", "precomputed"], now: float,
                 supply_fn: SupplyFn = day_zero_supply, spec: AgentSpec = INBOX) -> TriageResult:
    paths = {a.id: Path(scenarios_dir) / a.source for a in email.attachments}
    files = [Attachment(paths[a.id].read_bytes(), a.content_type) for a in email.attachments]
    raw, res = run_json(runner, spec, f"triage:{email.id}", build_message(email, opportunities), InboxExtraction,
                        attachments=files)
    names = {a.id: a.name for a in email.attachments}
    kinds = {a.attachment_id: a.kind for a in raw.attachments}
    pdfs = {aid: PdfText(p) for aid, p in paths.items()}
    try:
        attachments = [AttachmentTriage(attachment_id=a.id, name=a.name, kind=kinds.get(a.id, "other"),
                                        scanned=all(not pdfs[a.id].page_text(p)
                                                    for p in range(1, pdfs[a.id].page_count + 1)))
                       for a in email.attachments]
        seen: dict[str, ExtractedField] = {}
        for f in raw.fields:
            if f.key not in seen:
                seen[f.key] = verify_field(f, email, pdfs, names)
    finally:
        for pdf in pdfs.values():
            pdf.close()
    fields = [seen[k] for k in FIELD_ORDER if k in seen]
    crm = link_crm(raw.crm, raw.is_bid, email, opportunities)
    supply = supply_for(seen, appetite, erp, supply_fn) if raw.is_bid else None
    allowed = set(paths) | {o.id for o in opportunities}
    template = f"{'Bid' if raw.is_bid else 'Email'} from {email.from_org}."
    # The summary is agent prose: no digits (sanitize), no {slot} nothing will fill and no quantity in words (prose_guard).
    summary = sanitize(raw.summary, allowed, template) if prose_is_safe(raw.summary) else template
    return TriageResult(
        email_id=email.id, is_bid=raw.is_bid, summary=summary, attachments=attachments, fields=fields, crm=crm,
        fit=assess_fit(is_bid=raw.is_bid, fields=seen, crm=crm, appetite=appetite, as_of=as_of, supply=supply),
        quotes_verified=sum(f.verification == "verified" for f in fields), quotes_total=len(fields), source=source,
        model=MODEL, triaged_at=now, tokens_in=res.tokens_in, tokens_out=res.tokens_out)
