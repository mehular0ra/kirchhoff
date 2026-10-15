import re
import unicodedata

# Helvetica 10 pt word spaces (~2.8 pt) are narrower than pdfplumber's default x_tolerance of 3.
PDF_TEXT_KW = {"x_tolerance": 1.5, "y_tolerance": 3}

_TRANSLATE = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                            "–": "-", "—": "-", " ": " ",
                            "‐": "-", "‑": "-", "‒": "-", "−": "-"})


def normalize(s: str | None) -> str:
    """Canonical form for quote matching: NFKC, straight quotes, single spaces."""
    s = unicodedata.normalize("NFKC", s or "").translate(_TRANSLATE)
    return " ".join(s.split())


# P2 final fix wave (Important 2): a clause label is model free text, shown on the tender chip, in the PDF and in
# question text. The tender prints "App. B Appendix B: ..." and "§4.2 Redundancy", so the model may write
# "Appendix B", "App B", "Section 4.2" or "§4.2 (450 kW per row)". Every form maps to one canonical id; a label
# that is not a clause id at all maps to None, so no free-text digits ever ride along on a chip.
_APPENDIX = re.compile(r"(?:appendix|annex|app)\.?\s*([a-z])(?![a-z0-9])", re.IGNORECASE)
_SECTION = re.compile(r"(?:(?:§|sect?(?:ion)?\.?|cl(?:ause)?\.?)\s*(\d+(?:\.\d+)*)|(\d+(?:\.\d+)+))(?![\d.]*\d)",
                      re.IGNORECASE)
_TAIL = re.compile(r"$|[^A-Za-z0-9]")
CLAUSE_ID = re.compile(r"^(?:§\d+(?:\.\d+)*|App\. [A-Z])$")


def normalize_clause(label: str | None) -> str | None:
    """`§4.2`, `§6.3.4` or `App. B`; None for anything else."""
    s = normalize(label)
    if m := _APPENDIX.match(s):
        out = f"App. {m.group(1).upper()}"
    elif m := _SECTION.match(s):
        out = "§" + (m.group(1) or m.group(2))
    else:
        return None
    rest = s[m.end():].lstrip(".")
    return out if _TAIL.match(rest) and CLAUSE_ID.match(out) else None
