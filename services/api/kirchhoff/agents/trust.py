"""Digit allowlist for LLM text shown in the UI (spec §6.3)."""
import re
import unicodedata
from collections.abc import Iterable

from kirchhoff.contracts import DesignModel

TOPOLOGY_TOKENS = ("4-to-make-3", "3 + 1", "N+1", "2N")
_ALWAYS = [r"R\d{2}b?", r"§\d+(?:\.\d+)*"]
_SENTENCES = re.compile(r"(?<=[.!?])(?<!App\.)\s+")
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
# The only placeholders any caller fills (fill_finding, from the finding record). Every other brace -- an
# unfillable name such as {rack_kw}, a malformed "{ value }", or any brace at all when the caller never fills
# placeholders (narration, fix reasons, the voice answer, question text) -- would reach the user literally.
_FILLABLE = re.compile(r"\{(?:value|limit|unit)\}")
_BRACE = re.compile(r"[{}]")
# P2 final fix wave (Important 1): a quantity written in words is still an LLM-written number (spec §6.3:
# every number displayed comes from the engine), so "two point one six percent" fails like "2.16%". A bare
# "one" stays allowed ("the one with the largest margin"), unless it reads as a quantity ("one point five",
# "one hundred", "one week"); ordinals ("fourth row") are not quantities.
_CARDINALS = ("zero|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
              "seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety")
_ONE_UNITS = (r"point|hundred|thousand|million|billion|percent|per\s+cent|k[wv]|kva|mva|mw|ka|kpa|kilowatts?|"
              r"megawatts?|volts?|amps?|amperes?|weeks?|days?|hours?|minutes?|metres?|meters?|mm|degrees?")
_NUMBER_WORDS = re.compile(
    rf"\b(?:{_CARDINALS}|hundreds?|thousands?|millions?|billions?|dozens?|half|twice|thrice|percent|per\s+cent)\b"
    rf"|\bone\s+(?:{_ONE_UNITS})\b|\bpoint\s+one\b", re.IGNORECASE)


def _has_digit(s: str) -> bool:
    # Nd: ASCII/other decimal digits. No: superscripts, subscripts, circled digits,
    # vulgar fractions (½) and similar numeral forms that re.compile(r"\d") misses.
    return any(unicodedata.category(c) in ("Nd", "No") for c in s)


def _pattern(allowed_ids: Iterable[str]) -> re.Pattern:
    ids = sorted({i for i in allowed_ids if i}, key=len, reverse=True)
    alts = [re.escape(t) for t in TOPOLOGY_TOKENS] + [re.escape(i) for i in ids] + _ALWAYS
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(alts) + r")(?![A-Za-z0-9])")


def _offends(text: str, pat: re.Pattern, placeholders: bool) -> bool:
    """True when `text` would show the user a number the engine did not produce: a digit outside the
    allowlisted record tokens, a quantity in words, or a brace that nothing will fill."""
    rest = pat.sub(" ", text)
    if placeholders:
        rest = _FILLABLE.sub(" ", rest)
    return _has_digit(rest) or bool(_BRACE.search(rest)) or bool(_NUMBER_WORDS.search(rest))


def is_clean(text: str, allowed_ids: Iterable[str], placeholders: bool = False) -> bool:
    return not _offends(text or "", _pattern(allowed_ids), placeholders)


def sanitize(text: str, allowed_ids: Iterable[str], template: str, placeholders: bool = False) -> str:
    """Replaces every offending sentence of LLM `text` with `template` (once). `placeholders=True` lets
    {value}, {limit} and {unit} through, for the one caller that fills them afterwards from the engine's
    finding record (explain_text, via fill_finding); every other surface keeps the default False, because an
    unfilled placeholder would be shown, or spoken by browser speech, literally."""
    text = " ".join((text or "").split())
    if not text:
        return template
    pat = _pattern(allowed_ids)
    out: list[str] = []
    replaced = False
    for sentence in _SENTENCES.split(text):
        if _offends(sentence, pat, placeholders):
            if not replaced:
                out.append(template)
                replaced = True
        else:
            out.append(sentence)
    return " ".join(out)


def fill(text: str, values: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def fill_finding(text: str, value: float | None, limit: float | None, unit: str | None) -> str:
    u = unit or ""

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name == "unit":
            return u
        if name not in ("value", "limit"):
            return m.group(0)
        x = value if name == "value" else limit
        rest = text[m.end():]
        has_unit = bool(u) and (re.match(rf" ?{re.escape(u)}(?![A-Za-z0-9])", rest) is not None
                                or rest.startswith(" {unit}"))
        return fmt_number(x) if has_unit or x is None else fmt_value(x, u)

    return _PLACEHOLDER.sub(repl, text)


def fmt_number(x: float | None) -> str:
    if x is None:
        return "n/a"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if float(x).is_integer():
        return f"{x:.0f}"
    return f"{x:.2f}".rstrip("0").rstrip(".")


def fmt_value(x: float | None, unit: str | None) -> str:
    n = fmt_number(x)
    if x is None or not unit:
        return n
    return f"{n}{unit}" if unit == "%" else f"{n} {unit}"


def allowed_ids_for(*models: DesignModel | None, extra: Iterable[str] = ()) -> set[str]:
    ids: set[str | None] = set(extra)
    for m in models:
        if m is None:
            continue
        for r in m.racks:
            ids.update({r.id, r.row, *r.feeds})
        for e in m.equipment:
            ids.update({e.id, e.catalogue_id, e.system})
            ids.update(v for v in e.params.values() if isinstance(v, str))  # breaker frames live in params
        for c in m.connections:
            ids.update({c.id, c.src, c.dst, c.catalogue_id})
        for n in m.cooling_nodes:
            ids.update({n.id, n.zone})
        for p in m.pipes:
            ids.update({p.id, p.zone})
    return {i for i in ids if i}
