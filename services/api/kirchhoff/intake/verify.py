"""Deterministic citation check (spec §6.3): a quote is accepted only if pdfplumber finds it on the cited
page and the quote contains the extracted value. Bounding boxes come from pdfplumber."""
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from .textnorm import PDF_TEXT_KW, normalize

NUM_RE = re.compile(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?")
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10, "twelve": 12}
BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class QuoteCheck:
    ok: bool
    reason: str
    bbox: BBox | None = None


class PdfText:
    def __init__(self, path: Path | str) -> None:
        self._pdf = pdfplumber.open(str(path))
        self._text: dict[int, str] = {}

    def __enter__(self) -> "PdfText":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._pdf.close()

    @property
    def page_count(self) -> int:
        return len(self._pdf.pages)

    def page_text(self, page: int) -> str:
        if page not in self._text:
            self._text[page] = normalize(self._pdf.pages[page - 1].extract_text(**PDF_TEXT_KW) or "")
        return self._text[page]

    def find_bbox(self, page: int, quote: str) -> BBox | None:
        words = normalize(quote).split()
        if not words:
            return None
        pattern = r"\s+".join(re.escape(w) for w in words)
        try:
            hits = self._pdf.pages[page - 1].search(pattern, regex=True, case=True, **PDF_TEXT_KW)
        except Exception:  # pdfplumber layout edge cases: fall back to "verified without box"
            return None
        if not hits:
            return None
        h = hits[0]
        return (float(h["x0"]), float(h["top"]), float(h["x1"]), float(h["bottom"]))


def _as_float(value: float | int | str) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def value_in_quote(value: float | int | str | None, quote: str) -> bool:
    if value is None:
        return True
    q = normalize(quote)
    num = _as_float(value)
    if num is None:
        return normalize(str(value)).casefold() in q.casefold()
    found = [float(m.replace(",", "").rstrip(",")) for m in NUM_RE.findall(q)]
    found += [float(n) for w, n in NUMBER_WORDS.items() if re.search(rf"\b{w}\b", q, re.IGNORECASE)]
    return any(abs(f - num) <= 1e-6 * max(1.0, abs(num)) for f in found)


def verify_quote(pdf: PdfText, page: int, quote: str, value: float | int | str | None) -> QuoteCheck:
    if page < 1 or page > pdf.page_count:
        return QuoteCheck(False, "page_out_of_range")
    q = normalize(quote)
    if len(q) < 8:
        return QuoteCheck(False, "quote_too_short")
    if q not in pdf.page_text(page):
        return QuoteCheck(False, "quote_not_found")
    if not value_in_quote(value, q):
        return QuoteCheck(False, "value_not_in_quote")
    return QuoteCheck(True, "ok", pdf.find_bbox(page, q))
