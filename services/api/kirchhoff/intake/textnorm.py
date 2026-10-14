import unicodedata

# Helvetica 10 pt word spaces (~2.8 pt) are narrower than pdfplumber's default x_tolerance of 3.
PDF_TEXT_KW = {"x_tolerance": 1.5, "y_tolerance": 3}

_TRANSLATE = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                            "–": "-", "—": "-", " ": " "})


def normalize(s: str | None) -> str:
    """Canonical form for quote matching: NFKC, straight quotes, single spaces."""
    s = unicodedata.normalize("NFKC", s or "").translate(_TRANSLATE)
    return " ".join(s.split())
