#!/usr/bin/env python3
"""Build burned-in captions from Mehul's real voiceover, not from the script.

Flow: record one WAV per beat → transcribe each with Gemini on Vertex AI (word timings) →
glossary pass (product names, units, ids, British/Indian spelling) → cue rules → one SRT on the
final video timeline.

Each WAV is given with the time, in the final cut, where that beat's voice starts:

  GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep \\
  uv run --with google-genai python docs/submission/video/transcribe.py \\
      vo/b01-intro.wav@5.4 vo/b03-problem.wav@15.0 vo/b04-requirements.wav@24.0 ... \\
      --out docs/submission/video/captions-v2.srt

Or list the beats in a JSON file ([{"wav": "vo/b03.wav", "start": 15.0}, ...]) and pass --beats.

Gemini is called once per WAV and the word list is cached next to it (<wav>.words.json), so
re-running after a timing change costs nothing; --refresh forces a new call. --dry-run never
touches the network: it spreads the words of --text evenly over the WAV, which is enough to
test the glossary and cue rules (that is how this script was tested, on one macOS `say` clip).

Cue rules: at most 42 characters per line, at most 2 lines per cue, each cue 1.5–6 s on screen.
The wording is what he said; only the glossary changes spellings.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

MODEL = "gemini-3.8-flash"
PROJECT = "ordinal-mep"
LOCATION = "global"
MAX_LINE = 42
MAX_LINES = 2
MIN_CUE = 1.5
MAX_CUE = 6.0
GAP_BREAK = 0.6  # a pause this long starts a new cue

PROMPT = """You are transcribing a product-demo voiceover recorded by an Indian engineer.
Transcribe exactly what is spoken, word for word, in Indian English with British spelling
(organise, colour, programme, centre). Do not paraphrase, summarise or fix grammar. Write
numbers as digits the way an engineer writes them (132 kW, 2.16 percent, 3.15 MVA, 26 weeks).
Return JSON only: {"words": [{"w": "<word with any attached punctuation>", "start": <seconds>,
"end": <seconds>}]}, with times measured from the start of this audio file, to the nearest
0.01 s, in spoken order. Product names you will hear: Kirchhoff, Ordinal, Gemini, Vertex AI,
Cloud Run, Firestore, Firebase, SAP S/4HANA, Ariba, Gmail, Google Drive, MEP, CDU, UPS."""

# (pattern, replacement), applied in order to the joined caption text. Case-insensitive.
GLOSSARY: list[tuple[str, str]] = [
    (r"\bkirch\s*h?off?s?\b|\bkirk\s*off\b|\bkirchof+\b|\bkirchhof\b", "Kirchhoff"),
    (r"\bordinal\b", "Ordinal"),
    (r"\bjay?a?\s*drath?a?\b", "Jayadratha"),  # 16 Oct: Gemini heard "Jayadrath" in the intro
    (r"\bgemini\b", "Gemini"),
    (r"\bvertex\s*a\.?\s*i\b", "Vertex AI"),
    (r"\bcloud\s*run\b", "Cloud Run"),
    (r"\bfire\s*store\b", "Firestore"),
    (r"\bfire\s*base\b", "Firebase"),
    (r"\bs\s*/?\s*4\s*hana\b|\bs\s*four\s*hana\b|\bs4\s*hana\b", "S/4HANA"),
    (r"\bsap\b|\bs\.a\.p\.?\b", "SAP"),
    (r"\bariba\b", "Ariba"),
    (r"\bg\s*mail\b", "Gmail"),
    (r"\bgoogle\s*drive\b", "Google Drive"),
    (r"\bgoogle\s*cloud\b", "Google Cloud"),
    (r"\bm\.?\s*e\.?\s*p\b", "MEP"),
    (r"\bc\.?\s*d\.?\s*u(s?)\b", r"CDU\1"),
    (r"\bu\.?\s*p\.?\s*s\b", "UPS"),
    (r"\bl\.?\s*l\.?\s*m\b", "LLM"),
    (r"\ba\.?\s*d\.?\s*k\b", "ADK"),
    (r"\b(\d[\d,.]*)\s*(?:kilowatts?|kilo\s*watts?|kw)\b", r"\1 kW"),
    (r"\b(\d[\d,.]*)\s*(?:megawatts?|mega\s*watts?|mw)\b", r"\1 MW"),
    (r"\b(\d[\d,.]*)\s*(?:m\.?\s*v\.?\s*a)\b", r"\1 MVA"),
    (r"\b(\d[\d,.]*)\s*(?:kilovolts?|kv)\b", r"\1 kV"),
    (r"\bmva\b", "MVA"),
    (r"\b(\d[\d,.]*)\s*per\s*cent\b|\b(\d[\d,.]*)\s*percent\b", lambda m: f"{m.group(1) or m.group(2)}%"),
    (r"\br\s*0?5\b|\br\s*zero\s*five\b", "R05"),
    (r"\br\s*11\b|\br\s*eleven\b", "R11"),
    (r"\br\s*15\b|\br\s*fifteen\b", "R15"),
    (r"\bf\s*a\s*-?\s*0?1\b|\bf\s*a\s*zero\s*one\b", "FA-01"),
    (r"\bf\s*b\s*-?\s*0?3\b|\bf\s*b\s*zero\s*three\b", "FB-03"),
    (r"\bh\s*-?\s*z\s*2\b|\bh\s*z\s*two\b", "H-Z2"),
    (r"\b2\s*n\b|\btwo\s*n\b", "2N"),
    (r"\bkirchhoff\s*dot\s*web\s*dot\s*app\b", "kirchhoff.web.app"),
]
# American → British/Indian spelling (whole words; keeps case of the first letter).
BRITISH = {
    "organize": "organise", "organized": "organised", "organizes": "organises", "organizing": "organising",
    "optimize": "optimise", "optimized": "optimised", "optimizing": "optimising", "analyze": "analyse",
    "analyzed": "analysed", "color": "colour", "colors": "colours", "center": "centre", "centers": "centres",
    "program": "programme", "programs": "programmes", "behavior": "behaviour", "labor": "labour",
    "catalog": "catalogue", "standardize": "standardise", "summarize": "summarise", "recognize": "recognise",
    "license": "licence", "meters": "metres", "meter": "metre", "liter": "litre", "liters": "litres",
}


@dataclass
class Word:
    w: str
    start: float
    end: float


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as f:
        return f.getnframes() / float(f.getframerate())


def transcribe_vertex(path: Path) -> list[Word]:
    from google import genai  # only imported for a real run
    from google.genai import types

    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", PROJECT)
    os.environ.setdefault("GOOGLE_CLOUD_QUOTA_PROJECT", PROJECT)
    client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location=LOCATION)
    schema = {
        "type": "OBJECT",
        "properties": {"words": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"w": {"type": "STRING"}, "start": {"type": "NUMBER"}, "end": {"type": "NUMBER"}},
            "required": ["w", "start", "end"]}}},
        "required": ["words"],
    }
    # The first real run (16 Oct, on the intro) came back with no candidate parts and no finish reason once, then
    # succeeded unchanged on the next call; so retry an empty reply a few times before giving up.
    for attempt in range(1, 4):
        resp = client.models.generate_content(
            model=MODEL,
            contents=[types.Part.from_bytes(data=path.read_bytes(), mime_type="audio/wav"), PROMPT],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                               temperature=0.0),
        )
        if resp.text:
            break
        print(f"{path.name}: empty reply from {MODEL} (attempt {attempt} of 3)", file=sys.stderr)
    else:
        raise SystemExit(f"{path.name}: {MODEL} returned no transcript after 3 attempts")
    data = json.loads(resp.text)
    dur = wav_seconds(path)
    words = []
    for x in data.get("words", []):
        s, e = max(0.0, float(x["start"])), min(dur, float(x["end"]))
        if x.get("w", "").strip():
            words.append(Word(x["w"].strip(), s, max(s + 0.05, e)))
    return words


def mock_words(path: Path, text: str) -> list[Word]:
    """Dry run: spread the given text evenly over the WAV (no network)."""
    toks = text.split()
    dur = wav_seconds(path)
    step = dur / max(1, len(toks))
    return [Word(tk, i * step, (i + 1) * step - 0.02) for i, tk in enumerate(toks)]


def glossary(text: str) -> str:
    for pat, rep in GLOSSARY:
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    def brit(m: re.Match) -> str:
        w = m.group(0)
        b = BRITISH.get(w.lower())
        if not b:
            return w
        return b[0].upper() + b[1:] if w[0].isupper() else b

    return re.sub(r"[A-Za-z]+", brit, text)


def wrap(text: str) -> list[str]:
    """Split into at most two balanced lines of ≤ MAX_LINE characters."""
    if len(text) <= MAX_LINE:
        return [text]
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if len(a) <= MAX_LINE and len(b) <= MAX_LINE:
            score = abs(len(a) - len(b))
            if best is None or score < best[0]:
                best = (score, [a, b])
    return best[1] if best else [text[:MAX_LINE], text[MAX_LINE:]]


def fits(text: str) -> bool:
    return len(text) <= MAX_LINE or (len(text) <= 2 * MAX_LINE + 1 and len(wrap(text)) == 2
                                     and all(len(x) <= MAX_LINE for x in wrap(text)))


def build_cues(words: list[Word]) -> list[dict]:
    cues: list[dict] = []
    cur: list[Word] = []

    def flush():
        if cur:
            cues.append({"start": cur[0].start, "end": cur[-1].end, "text": " ".join(w.w for w in cur)})
            cur.clear()

    for w in words:
        if cur:
            text = " ".join(x.w for x in cur + [w])
            gap = w.start - cur[-1].end
            too_long = (w.end - cur[0].start) > MAX_CUE
            sentence_end = re.search(r"[.!?]$", cur[-1].w) and (cur[-1].end - cur[0].start) >= MIN_CUE
            if not fits(glossary(text)) or too_long or gap > GAP_BREAK or sentence_end:
                flush()
        cur.append(w)
    flush()
    # minimum on-screen time: stretch into the following silence, else merge with the next cue
    out: list[dict] = []
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else c["end"] + MIN_CUE
        if c["end"] - c["start"] < MIN_CUE:
            c["end"] = min(c["start"] + MIN_CUE, max(c["end"], nxt - 0.04))
        if out and c["end"] - c["start"] < MIN_CUE and fits(glossary(out[-1]["text"] + " " + c["text"])) \
                and c["end"] - out[-1]["start"] <= MAX_CUE:
            out[-1]["end"] = c["end"]
            out[-1]["text"] += " " + c["text"]
            continue
        out.append(c)
    return out


def ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wavs", nargs="*", help="WAV@START: a beat's voice file and where it starts in the final cut (s)")
    ap.add_argument("--beats", type=Path, help='JSON list of {"wav": ..., "start": ...}')
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "captions-v2.srt")
    ap.add_argument("--refresh", action="store_true", help="ignore cached <wav>.words.json and call Gemini again")
    ap.add_argument("--dry-run", action="store_true", help="no network: spread --text evenly over the WAV")
    ap.add_argument("--text", default="", help="dry run only: the words to spread")
    args = ap.parse_args()

    beats: list[tuple[Path, float]] = []
    if args.beats:
        for b in json.loads(args.beats.read_text(encoding="utf-8")):
            beats.append((Path(b["wav"]), float(b.get("start", 0.0))))
    for spec in args.wavs:
        path, _, start = spec.partition("@")
        beats.append((Path(path), float(start or 0.0)))
    if not beats:
        ap.error("give at least one WAV@START or --beats")

    all_cues: list[dict] = []
    for path, start in beats:
        if not path.exists():
            print(f"ERROR: {path} not found", file=sys.stderr)
            return 1
        cache = path.with_suffix(path.suffix + ".words.json")
        if args.dry_run:
            words = mock_words(path, args.text or "dry run")
            src = "dry run (no network)"
        elif cache.exists() and not args.refresh:
            words = [Word(**w) for w in json.loads(cache.read_text(encoding="utf-8"))]
            src = f"cache {cache.name}"
        else:
            words = transcribe_vertex(path)
            cache.write_text(json.dumps([w.__dict__ for w in words], indent=1), encoding="utf-8")
            src = f"Gemini {MODEL} on Vertex AI ({LOCATION})"
        cues = build_cues(words)  # glossary runs on the cue text, so multi-word terms are caught
        for c in cues:
            c["text"] = glossary(c["text"])
            c["start"] += start
            c["end"] += start
        print(f"{path.name} @ {start:.2f}s · {len(words)} words → {len(cues)} cues · {src}")
        all_cues += cues

    all_cues.sort(key=lambda c: c["start"])
    lines, problems = [], []
    for i, c in enumerate(all_cues, 1):
        rows = wrap(c["text"])
        dur = c["end"] - c["start"]
        if any(len(r) > MAX_LINE for r in rows) or len(rows) > MAX_LINES:
            problems.append(f"cue {i}: line too long")
        if dur < MIN_CUE - 1e-6 or dur > MAX_CUE + 1e-6:
            problems.append(f"cue {i}: {dur:.2f} s on screen")
        lines += [str(i), f"{ts(c['start'])} --> {ts(c['end'])}", *rows, ""]
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(all_cues)} cues → {args.out}")
    for p in problems:
        print(f"  CHECK: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
