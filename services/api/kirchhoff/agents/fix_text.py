"""The fix line of the co-pilot's "why" answer (UX-1 D1), ported from the web co-pilot so voice and the typed
co-pilot word a fix the same way: apps/web/src/lib/format.ts (fmtKeyValue and its helpers),
src/workspace/finding/fixView.ts (readFix) and src/workspace/copilot/tools.ts (fixLine). Formatting only:
every value comes from the engine's fix record (R14 code-authored text)."""
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from kirchhoff.contracts import Finding

DASH = "—"
_KEY_LABELS: dict[str, tuple[str, str | None, bool]] = {  # key -> (label, unit, usd)
    "dv_pct": ("ΔV", "%", False), "dv_limit_pct": ("ΔV limit", "%", False),
    "index_dp_kpa": ("Index-circuit Δp", "kPa", False), "added_pipe_m": ("Added pipe", "m", False),
    "changed_pipes": ("Changed pipes", None, False), "rating_a": ("Rating", "A", False),
    "cost_delta": ("Cost Δ", None, True), "cost_usd": ("Cost", None, True), "cost": ("Cost", None, True),
    "capex_usd": ("Capex", None, True), "lifecycle_usd": ("Lifecycle cost", None, True),
    "margin_pct": ("Margin", "%", False), "loading_pct": ("Loading", "%", False), "losses_kw": ("Losses", "kW", False),
    "lead_time_weeks": ("Lead time", "weeks", False), "finding_id": ("Finding", None, False), "ok": ("OK", None, False),
    "i_a": ("Current I", "A", False), "at_x": ("At x", "m", False), "at_y": ("At y", "m", False),
    "at_z": ("At z", "m", False), "n1_current_a": ("N-1 current", "A", False), "dc_kwp": ("DC capacity", "kWp", False),
    "dc_ac": ("DC/AC ratio", None, False), "voc_max_v": ("Voc max", "V", False), "vmp_min_v": ("Vmp min", "V", False),
    "annual_mwh": ("Annual energy", "MWh", False), "annual_loss_mwh": ("Annual loss", "MWh", False),
}
_SUFFIX_UNITS = [("_pct", "%"), ("_kva", "kVA"), ("_mva", "MVA"), ("_mwh", "MWh"), ("_kw", "kW"), ("_mw", "MW"),
                 ("_kv", "kV"), ("_ka", "kA"), ("_kpa", "kPa"), ("_lps", "L/s"), ("_ms", "m/s"), ("_km", "km"),
                 ("_weeks", "weeks"), ("_usd", "USD"), ("_a", "A"), ("_v", "V"), ("_m", "m")]
_COUNT_UNITS = {"crossings", "lines", "systems", "elements", "pipes", "clashes", "checks", "findings", "weeks"}
_TOKEN_LABELS = {"pipe_low": "the low pipe tier", "pipe_high": "the high pipe tier"}


def _rounded(v: float, places: int) -> Decimal:
    # Node's Intl.NumberFormat rounds the shortest decimal form of the number (what repr prints, so 2.675 and
    # not 2.67499999...) half away from zero: 2.675 -> 2.68, -1.005 -> -1.01. Decimal(v) would round the binary
    # value instead and disagree with the web on these ties.
    return Decimal(repr(float(v))).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _non_finite(v: float) -> str | None:
    """Intl's text for a non-finite value ("∞", "-∞"); NaN is the web's dash (fmtNum)."""
    if v != v:
        return DASH
    return ("-∞" if v < 0 else "∞") if v in (float("inf"), float("-inf")) else None


def fmt_num(v: float | None) -> str:
    """Intl.NumberFormat('en-US', {maximumFractionDigits: 2}), negative zero included ("-0")."""
    if v is None:
        return DASH
    if (special := _non_finite(v)) is not None:
        return special
    return f"{_rounded(v, 2):,.2f}".rstrip("0").rstrip(".")


def fmt_qty(v: float | None, unit: str | None = None) -> str:
    if v is None:
        return DASH
    if not unit:
        return fmt_num(v)
    if unit == "%":
        return f"{fmt_num(v)}%"
    return f"{fmt_num(v)} {unit[:-1] if abs(v) == 1 and unit in _COUNT_UNITS else unit}"


def fmt_usd(v: float | None, signed: bool = False) -> str:
    """Intl's USD with no decimals: the sign before the symbol, negative zero kept ("-$0", as Node prints)."""
    if v is None:
        return DASH
    if v != v:
        return "$NaN"  # what the web's fmtUsd shows; no engine record carries one
    if v in (float("inf"), float("-inf")):
        body, negative = "∞", v < 0
    else:
        n = _rounded(v, 0)
        body, negative = f"{abs(n):,.0f}", n.is_signed()
    s = f"{'-' if negative else ''}${body}"
    return f"+{s}" if signed and v > 0 else s


def _humanize(key: str) -> str:
    words = key.replace("_", " ").strip()
    return words[:1].upper() + words[1:]


def describe_key(key: str) -> tuple[str, str | None, bool]:
    if key in _KEY_LABELS:
        return _KEY_LABELS[key]
    lower = key.lower()
    for suffix, unit in _SUFFIX_UNITS:
        if lower.endswith(suffix) and len(lower) > len(suffix):
            return _humanize(key[: -len(suffix)]), unit, False
    return _humanize(key), None, False


def _singular(word: str) -> str:
    if re.search(r"(ches|shes|sses|xes)$", word):
        return word[:-2]
    return word[:-1] if word.endswith("s") else word


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def fmt_key_value(key: str, value: Any) -> str:
    label, unit, usd = describe_key(key)
    if _is_number(value):
        if usd:
            return f"{label} {fmt_usd(value, key.endswith('delta'))}"
        return f"{label} {fmt_qty(value, None if unit == 'USD' else unit)}{' USD' if unit == 'USD' else ''}"
    if isinstance(value, bool):
        return f"{label} {'✓' if value else '✗'}"
    if value is None:
        return f"{label} {DASH}"
    if isinstance(value, (list, dict)):
        if isinstance(value, list) and value and all(isinstance(x, str) or _is_number(x) for x in value):
            shown = [fmt_num(x) if _is_number(x) else x for x in value[:4]]
            return f"{label} {', '.join(shown)}{f' +{len(value) - 4} more' if len(value) > 4 else ''}"
        n, noun = len(value), label.lower()
        return f"{n} {_singular(noun) if n == 1 else noun}"
    return f"{label} {value}"


def tidy_tokens(text: str) -> str:
    return re.sub(r"\b(pipe_low|pipe_high)\b", lambda m: _TOKEN_LABELS[m.group(1)], text)


def _is_problem(f: Finding | None) -> bool:
    return f is not None and f.status in ("fail", "warn")


def fix_line(finding: Finding, child_id: str | None, child_findings: list[Finding]) -> str:
    """" Fixed in r2: <label> · Cost Δ +$15,580 · ΔV 0.84%." from the finding's chosen-fix record, or "Chosen
    fix: ..." when the next revision (`child_id`) does not show the same finding fixed; "" with no record."""
    fix = finding.fix
    if not fix:
        return ""
    raw = fix.get("deltas")
    inner = list(raw.items()) if isinstance(raw, dict) else []
    cost = ([("cost_delta", fix["cost_delta"])]
            if _is_number(fix.get("cost_delta")) and not any(k == "cost_delta" for k, _ in inner) else [])
    deltas = [fmt_key_value(k, v) for k, v in (cost + inner)[:2]]
    label = fix.get("label")
    if label is None:
        label = fix.get("candidate")
    after = next((f for f in child_findings if f.id == finding.id), None) if child_id else None
    lead = f"Fixed in {child_id}" if after is not None and not _is_problem(after) else "Chosen fix"
    return f" {lead}: {' · '.join([tidy_tokens(str('Fix' if label is None else label)), *deltas])}."
