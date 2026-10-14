"""Digit allowlist for LLM text shown in the UI (spec §6.3)."""
import re
import unicodedata
from collections.abc import Iterable

from kirchhoff.contracts import DesignModel

TOPOLOGY_TOKENS = ("4-to-make-3", "3 + 1", "N+1", "2N")
_ALWAYS = [r"R\d{2}b?", r"§\d+(?:\.\d+)*", r"\{[a-z_]+\}"]
_SENTENCES = re.compile(r"(?<=[.!?])(?<!App\.)\s+")
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def _has_digit(s: str) -> bool:
    # Nd: ASCII/other decimal digits. No: superscripts, subscripts, circled digits,
    # vulgar fractions (½) and similar numeral forms that re.compile(r"\d") misses.
    return any(unicodedata.category(c) in ("Nd", "No") for c in s)


def _pattern(allowed_ids: Iterable[str]) -> re.Pattern:
    ids = sorted({i for i in allowed_ids if i}, key=len, reverse=True)
    alts = [re.escape(t) for t in TOPOLOGY_TOKENS] + [re.escape(i) for i in ids] + _ALWAYS
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(alts) + r")(?![A-Za-z0-9])")


def is_clean(text: str, allowed_ids: Iterable[str]) -> bool:
    return not _has_digit(_pattern(allowed_ids).sub("", text or ""))


def sanitize(text: str, allowed_ids: Iterable[str], template: str) -> str:
    text = " ".join((text or "").split())
    if not text:
        return template
    pat = _pattern(allowed_ids)
    out: list[str] = []
    replaced = False
    for sentence in _SENTENCES.split(text):
        if _has_digit(pat.sub("", sentence)):
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
