"""Deterministic fit rules and the day-zero supply check (spec §20). No LLM: the inputs are verified fields, the
appetite rules from world.yaml, ERP records and the engine's own functions (addendum ruling B7). Every sentence is a
code-authored template filled from those records (P2 ruling R14).

Trust (spec §6.3, review carry-in on #4/#5): the web app renders these sentences verbatim, so each one goes through
`trust.sanitize` as a template whose numbers are {placeholders}; only afterwards does `fill` insert the values the
code formatted (an ERP rating, a date, a verified field's display). Free text quoted from a document (the site) is
interpolated into the template itself, so a digit in it never reaches the client: the digit-free fallback is used."""
import logging
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from kirchhoff.agents.trust import fill, fmt_number, fmt_value, sanitize
from kirchhoff.contracts import Material
from kirchhoff.enterprise.world.inbox import Appetite
from kirchhoff.intake.brief import canonical_topology

from .models import ASSET_LABELS, CrmLink, ExtractedField, FitReason, FitResult, ReasonStatus, SupplyCheck

log = logging.getLogger("kirchhoff.inbox")
IST = timezone(timedelta(hours=5, minutes=30))
DATE_FORMATS = ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%Y-%m-%d")
RULE_LABELS = {"asset_pack": "asset type", "mw_range": "load (MW)", "region": "region", "deadline": "bid deadline",
               "supply": "day-zero supply"}
SUPPLY_STATUS: dict[str, ReasonStatus] = {"ok": "pass", "swap": "pass", "risk": "warn", "not_assessed": "n/a"}
SUPPLY_FALLBACK = "The day-zero supply check ran; the figures are in the ERP."
SupplyFn = Callable[[float | None, str | None, float | None, object], SupplyCheck]


def _say(template: str, fallback: str, **values: object) -> str:
    """One rendered sentence: the template passes trust.sanitize, then the code-formatted values are filled in. If any
    sentence was replaced the fallback is used whole, never a mix of the two."""
    safe = sanitize(template, (), fallback)
    if safe != " ".join(template.split()):
        safe = fallback
    return fill(safe, {k: str(v) for k, v in values.items()})


def _plain(text: object) -> str:
    """Free text quoted from a document, with no braces, so it can never be read as one of our placeholders."""
    return re.sub(r"[{}]", "", str(text))


def parse_due(text: str | None) -> date | None:
    """A bid due date as printed ("13 November 2026", "13th Nov 2026", "2026-11-13"), or None."""
    if not text:
        return None
    t = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", str(text)).replace(",", " ")
    t = " ".join(t.split()).rstrip(".")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def fmt_date(d: date) -> str:
    return f"{d.day} {d.strftime('%b %Y')}"


def days_to_due(due: date, as_of: float) -> int:
    """Whole days from the inbox's as_of (the world anchor, in IST) to the due date; never the wall clock."""
    return (due - datetime.fromtimestamp(as_of, IST).date()).days


def region_of(site: str, appetite: Appetite) -> str | None:
    s = site.casefold()
    return next((r.name for r in appetite.regions if any(p.casefold() in s for p in r.places)), None)


def _mva(m: Material) -> str:
    if m.unit == "kVA" and m.rating:
        return f"{fmt_number(m.rating / 1000.0)} MVA"
    return fmt_value(m.rating, m.unit)


def _stock(m: Material) -> str:
    return "none in stock" if m.stock <= 0 else f"{m.stock} in stock"


def day_zero_supply(mw: float | None, redundancy: str | None, lead_limit_weeks: float | None, erp,
                    scenarios_root: Path | None = None) -> SupplyCheck:
    """R15 before bidding (spec §20): size the transformer the extracted load and redundancy imply with the engine
    (Hall A's reference hall, per-rack load scaled to the load), then check its ERP lead time against the extracted
    limit and, if it misses, let the engine's r15_swap find the swap."""
    if mw is None:
        return SupplyCheck(status="not_assessed", text="No verified load, so the transformer cannot be sized yet.")
    if lead_limit_weeks is None:
        return SupplyCheck(status="not_assessed", mw=mw,
                           text="No verified lead-time clause, so there is no limit to check the ERP against.")
    from kirchhoff.engine.api import load_scenario, place_racks, power_options
    from kirchhoff.engine.erp import effective_lead_weeks
    from kirchhoff.engine.options import r15_swap
    from kirchhoff.engine.scenario import with_limit

    topology = canonical_topology(redundancy) if redundancy else None
    note = "" if topology else "Redundancy not stated; assumed 2N. "
    topology = topology or "2N"
    limit = float(lead_limit_weeks)
    base = load_scenario("hall_a", scenarios_root)
    scn = with_limit(with_limit(base, "rack_kw", mw * 1000.0 / len(place_racks(base))), "max_lead_time_weeks", limit)
    options = {opt.id: model for opt, model in power_options(scn, place_racks(scn))}
    common: dict = {"topology": topology, "mw": mw, "lead_limit_weeks": limit}
    if topology not in options:
        return SupplyCheck(
            status="not_assessed", **common,
            text=_say(note + "No catalogue transformer passes R01 for {mw} in {topology} on the reference hall; "
                      "size it at intake.", SUPPLY_FALLBACK, mw=fmt_value(mw, "MW"), topology=topology))
    model = options[topology]
    txs = [e for e in model.equipment if e.kind == "transformer"]
    m = erp.get(txs[0].catalogue_id)
    common.update(material_id=m.id, lead_time_weeks=m.lead_time_weeks, stock=m.stock)
    head = note + "{limit}-week limit; the {mva} unit {mat}"
    figures = {"limit": fmt_number(limit), "mva": _mva(m), "mat": m.id, "weeks": m.lead_time_weeks,
               "stock": _stock(m)}
    if effective_lead_weeks(m, len(txs)) <= limit:
        how = _stock(m) if m.stock >= len(txs) else f"{m.lead_time_weeks} weeks to order"
        return SupplyCheck(status="ok", **common,
                           text=_say(head + " ships in time ({how}).", SUPPLY_FALLBACK, how=how, **figures))
    found = r15_swap(scn, model, m.id, erp)
    if found is None:
        return SupplyCheck(
            status="risk", **common,
            text=_say(head + " is {weeks} weeks with {stock}, and the ERP has no compliant alternative; ask whether "
                      "the limit can move.", SUPPLY_FALLBACK, **figures))
    to = erp.get(found[1]["to"])
    kind = (f"an in-stock swap to {to.id} ({_mva(to)}, {to.stock} in stock)" if to.stock >= len(txs)
            else f"a swap to {to.id} ({_mva(to)}, {to.lead_time_weeks} weeks)")
    return SupplyCheck(status="swap", **common, swap_to=to.id, swap_stock=to.stock,
                       text=_say(head + " is {weeks} weeks with {stock}; expect {kind}.", SUPPLY_FALLBACK,
                                 kind=kind, **figures))


def warm_engine() -> None:
    """Pay the engine's first-call cost (pandapower import, about 6 s) off the request path (ruling B8)."""
    try:
        from kirchhoff.engine.api import warm_up
        warm_up()
    except Exception as exc:  # warming is best effort
        log.warning("engine warm-up failed: %r", exc)


def _verified(fields: dict[str, ExtractedField], key: str) -> ExtractedField | None:
    f = fields.get(key)
    return f if f is not None and f.verification == "verified" and f.value is not None else None


def supply_for(fields: dict[str, ExtractedField], appetite: Appetite, erp,
               supply_fn: SupplyFn = day_zero_supply) -> SupplyCheck | None:
    if not appetite.lead_time_check:
        return None
    asset = _verified(fields, "asset_type")
    if asset is None:
        return SupplyCheck(status="not_assessed", text="The asset type is not verified, so the supply check did not run.")
    if asset.value != "datahall":
        return SupplyCheck(status="not_assessed", text="The day-zero supply check covers AI data halls only.")
    mw, red, lead = (_verified(fields, k) for k in ("mw", "redundancy", "lead_time_weeks"))
    return supply_fn(float(mw.value) if mw else None, str(red.value) if red else None,
                     float(lead.value) if lead else None, erp)


def _asset(fields: dict[str, ExtractedField], appetite: Appetite) -> FitReason:
    f = _verified(fields, "asset_type")
    if f is None:
        return FitReason(rule="asset_pack", status="warn", text="The asset type is not stated or not verified.")
    label = ASSET_LABELS.get(str(f.value), str(f.value))
    if f.value in appetite.asset_types:
        return FitReason(rule="asset_pack", status="pass",
                         text=_say("{label} is one of our asset packs.", "That asset type is one of our asset packs.",
                                   label=label))
    packs = ", ".join(ASSET_LABELS[a] for a in appetite.asset_types)
    return FitReason(rule="asset_pack", status="fail",
                     text=_say("{label} is not one of our asset packs ({packs}).",
                               "That asset type is not one of our asset packs ({packs}).", label=label, packs=packs))


def _mw(fields: dict[str, ExtractedField], appetite: Appetite) -> FitReason:
    lo, hi = appetite.mw
    f = _verified(fields, "mw")
    rng = {"lo": fmt_number(lo), "hi": fmt_number(hi)}
    if f is not None:
        inside = lo <= float(f.value) <= hi
        return FitReason(rule="mw_range", status="pass" if inside else "fail",
                         text=_say("{mw} is {where} our {lo}–{hi} MW range.", "The load is checked against our range.",
                                   mw=f.display, where="inside" if inside else "outside", **rng))
    raw = fields.get("mw")
    if raw is not None and raw.verification == "unverified_scan":
        return FitReason(rule="mw_range", status="warn",
                         text=_say("The load is only on a scanned page ({source}) and is not verified; ask for a "
                                   "text copy.", "The load is only on a scanned page and is not verified; ask for a "
                                   "text copy.", source=raw.source_label))
    if raw is not None:
        return FitReason(rule="mw_range", status="warn", text="The load could not be verified against its quote.")
    return FitReason(rule="mw_range", status="warn", text="No load (MW) is stated.")


def _region(fields: dict[str, ExtractedField], appetite: Appetite) -> FitReason:
    f = _verified(fields, "site")
    if f is None:
        return FitReason(rule="region", status="warn", text="The site is not stated or not verified.")
    site, name = _plain(f.value), region_of(str(f.value), appetite)
    if name:
        return FitReason(rule="region", status="pass",
                         text=_say(site + " is in {region}, one of our regions.",
                                   "The stated site is in {region}, one of our regions.", region=name))
    names = ", ".join(r.name for r in appetite.regions)
    return FitReason(rule="region", status="fail",
                     text=_say(site + " is outside our regions ({names}).",
                               "The stated site is outside our regions ({names}).", names=names))


def _deadline(fields: dict[str, ExtractedField], appetite: Appetite, as_of: float) -> FitReason:
    f = _verified(fields, "bid_due")
    due = parse_due(str(f.value)) if f else None
    if due is None:
        return FitReason(rule="deadline", status="warn", text="No verified bid due date yet; ask for it.")
    days, today, need = days_to_due(due, as_of), fmt_date(datetime.fromtimestamp(as_of, IST).date()), \
        appetite.min_days_to_bid_due
    fb = "The bid due date is checked against our minimum."
    if days < 0:
        return FitReason(rule="deadline", status="fail",
                         text=_say("Bid due {due} has passed (as of {today}).", fb, due=fmt_date(due), today=today))
    if days < need:
        return FitReason(rule="deadline", status="fail",
                         text=_say("Bid due {due}: {days} days from {today}, under our {need}-day minimum.", fb,
                                   due=fmt_date(due), days=days, today=today, need=need))
    return FitReason(rule="deadline", status="pass",
                     text=_say("Bid due {due}: {days} days from {today} (minimum {need}).", fb, due=fmt_date(due),
                               days=days, today=today, need=need))


def assess_fit(*, is_bid: bool, fields: dict[str, ExtractedField], crm: CrmLink, appetite: Appetite, as_of: float,
               supply: SupplyCheck | None) -> FitResult:
    if not is_bid:
        text = (_say("Not a bid; filed to {account} · {opportunity} in the CRM.", "Not a bid; filed in the CRM.",
                     account=crm.account, opportunity=crm.opportunity_name) if crm.opportunity_id
                else "Not a bid; no CRM record to update.")
        return FitResult(verdict=None, headline="Not a bid: no fit check.",
                         reasons=[FitReason(rule="not_a_bid", status="n/a", text=text)])
    reasons = [_asset(fields, appetite), _mw(fields, appetite), _region(fields, appetite),
               _deadline(fields, appetite, as_of)]
    if supply is not None:
        reasons.append(FitReason(rule="supply", status=SUPPLY_STATUS[supply.status], text=supply.text))
    fails = [RULE_LABELS[r.rule] for r in reasons if r.status == "fail"]
    warns = [RULE_LABELS[r.rule] for r in reasons if r.status == "warn"]
    if fails:
        return FitResult(verdict="decline", reasons=reasons, supply=supply,
                         headline=_say("Decline: outside our appetite on {what}.", "Decline: outside our appetite.",
                                       what=", ".join(fails)))
    if warns:
        return FitResult(verdict="clarify", reasons=reasons, supply=supply,
                         headline=_say("Clarify before bidding: {what}.", "Clarify before bidding.",
                                       what=", ".join(warns)))
    headline = ("Pursue: inside our appetite; plan the transformer swap the lead-time limit needs."
                if supply is not None and supply.status == "swap" else "Pursue: inside our appetite on every rule.")
    return FitResult(verdict="pursue", headline=headline, reasons=reasons, supply=supply)
