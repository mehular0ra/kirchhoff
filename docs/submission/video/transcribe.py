#!/usr/bin/env python3
"""Build burned-in captions from Mehul's real voiceover, not from the script.

Flow: record one WAV per beat → transcribe each with Cloud Speech-to-Text (Chirp 2, en-IN, word timings) →
glossary pass (product names, units, ids, British/Indian spelling) → cue rules → one SRT on the
final video timeline.

Each WAV is given with the time, in the final cut, where that beat's voice starts:

  GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep uv run --python 3.12 --with google-cloud-speech \\
      python docs/submission/video/transcribe.py \\
      vo/b01-intro.wav@5.4 vo/b03-problem.wav@15.0 vo/b04-requirements.wav@24.0 ... \\
      --out docs/submission/video/captions-v2.srt

Or list the beats in a JSON file ([{"wav": "vo/b03.wav", "start": 15.0}, ...]) and pass --beats.

Why Chirp, not Gemini (16 Oct, on Mehul's intro): gemini-3.8-flash heard the words well but Vertex blocked
most calls with prompt_feedback SAFETY (a fixed filter: no category ratings, unchanged by thresholds, wording
or schema), and gemini-3.5-flash-lite invented timings past the end of the clip. Chirp 2 with phrase hints for
our names got every product word and timed each word to the audio. `--engine gemini` keeps the Gemini path
(it needs google-genai and GOOGLE_GENAI_USE_VERTEXAI=true).

Each WAV is transcribed once and the word list is cached next to it (<wav>.words.json), so
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

MODEL = os.environ.get("TRANSCRIBE_MODEL", "gemini-3.8-flash")
STT_MODEL, STT_LOCATION, STT_LANGUAGE = "chirp_2", "us-central1", "en-IN"
# Phrase hints for Chirp: the names it otherwise mishears ("ketchup" for Kirchhoff, "Jatropha" for Jayadratha).
STT_PHRASES = ["Kirchhoff", "Jayadratha", "Mehul", "Ordinal", "Gemini", "Vertex AI", "Cloud Run", "Firestore",
               "Firebase", "SAP S/4HANA", "Ariba", "Gmail", "Google Drive", "MEP", "CDU", "UPS", "AI data centre",
               "power and cooling", "busway", "transformer", "tender", "2N", "R05", "R11", "R15", "FA-01", "H-Z2",
               "BOQ", "MWp", "kirchhoff.web.app"]
STT_BOOST = 15
ATTEMPTS = 8
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
    (r"\b(\d[\d,.]*)\s*(?:megawatts?|mega\s*watts?|mw)[\s-]*(?:peak|p)\b", r"\1 MWp"),  # before the MW rule: a solar plant is rated in MWp
    (r"\b(\d[\d,.]*)\s*(?:megawatts?|mega\s*watts?|mw)\b", r"\1 MW"),
    (r"\b(\d[\d,.]*)\s*(?:m\.?\s*v\.?\s*a)\b", r"\1 MVA"),
    (r"\b(\d[\d,.]*)\s*(?:kilovolts?|kv)\b", r"\1 kV"),
    (r"\bmva\b", "MVA"),
    (r"\bb[\s.-]*o[\s.-]*q\b", "BOQ"),  # the bill of quantities of a tender
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
    # Vertex blocks this call at random with prompt_feedback SAFETY after generating the transcript (16 Oct: 30-50 %
    # of calls on Mehul's intro, with or without the schema or the prompt's wording). Retrying is the fix; 8 tries
    # clear it about 98 % of the time. gemini-3.5-flash-lite is never blocked but invents timings (17 s of words in
    # a 12 s clip), so it is not the default; TRANSCRIBE_MODEL overrides MODEL.
    for attempt in range(1, ATTEMPTS + 1):
        resp = client.models.generate_content(
            model=MODEL,
            contents=[types.Part.from_bytes(data=path.read_bytes(), mime_type="audio/wav"), PROMPT],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                               temperature=0.0),
        )
        if resp.text:
            break
        why = resp.prompt_feedback.block_reason if resp.prompt_feedback else "no text"
        print(f"{path.name}: empty reply from {MODEL} ({why}; attempt {attempt} of {ATTEMPTS})", file=sys.stderr)
    else:
        raise SystemExit(f"{path.name}: {MODEL} returned no transcript after {ATTEMPTS} attempts; run it again")
    data = json.loads(resp.text)
    dur = wav_seconds(path)
    words = []
    late = [x for x in data.get("words", []) if float(x["start"]) > dur + 0.5]
    if late:
        raise SystemExit(f"{path.name}: {MODEL} timed {len(late)} words after the end of the {dur:.2f} s clip; "
                         "its timings are not usable")
    for x in data.get("words", []):
        s, e = max(0.0, float(x["start"])), min(dur, float(x["end"]))
        if x.get("w", "").strip():
            words.append(Word(x["w"].strip(), s, max(s + 0.05, e)))
    return words


def transcribe_chirp(path: Path) -> list[Word]:
    """Cloud Speech-to-Text v2, Chirp 2: word offsets measured on the audio, Indian English, phrase hints."""
    from google.api_core.client_options import ClientOptions
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech as cs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", PROJECT)
    client = SpeechClient(client_options=ClientOptions(api_endpoint=f"{STT_LOCATION}-speech.googleapis.com",
                                                       quota_project_id=project))
    phrases = cs.PhraseSet(phrases=[{"value": v, "boost": STT_BOOST} for v in STT_PHRASES])
    config = cs.RecognitionConfig(
        auto_decoding_config=cs.AutoDetectDecodingConfig(), model=STT_MODEL, language_codes=[STT_LANGUAGE],
        features=cs.RecognitionFeatures(enable_word_time_offsets=True, enable_automatic_punctuation=True),
        adaptation=cs.SpeechAdaptation(phrase_sets=[cs.SpeechAdaptation.AdaptationPhraseSet(inline_phrase_set=phrases)]))
    resp = client.recognize(request=cs.RecognizeRequest(
        recognizer=f"projects/{project}/locations/{STT_LOCATION}/recognizers/_", config=config,
        content=path.read_bytes()))
    words = []
    for result in resp.results:
        for w in (result.alternatives[0].words if result.alternatives else []):
            s, e = w.start_offset.total_seconds(), w.end_offset.total_seconds()
            if w.word.strip():
                words.append(Word(w.word.strip(), s, max(s + 0.05, e)))
    if not words:
        raise SystemExit(f"{path.name}: {STT_MODEL} heard no words; check the recording's level")
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
    if best:
        return best[1]
    # No two-line split fits: split at the middle word, never inside a word (16 Oct: the old fallback cut at 42
    # characters, so "AI dat / a centre" passed fits()); fits() then rejects it and the caller starts a new cue.
    mid = len(words) // 2
    return [" ".join(words[:mid]), " ".join(words[mid:])]


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
    # Measured word offsets can overlap by a few ms (Chirp, 16 Oct), so a cue never runs into the next one.
    for a, b in zip(out, out[1:]):
        a["end"] = min(a["end"], b["start"] - 0.04)
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
    ap.add_argument("--refresh", action="store_true", help="ignore cached <wav>.words.json and transcribe again")
    ap.add_argument("--engine", choices=["chirp", "gemini"], default="chirp",
                    help="chirp: Cloud Speech-to-Text (default); gemini: Gemini on Vertex AI, often blocked (see top)")
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
            if args.engine == "gemini":
                words, src = transcribe_vertex(path), f"Gemini {MODEL} on Vertex AI ({LOCATION})"
            else:
                words, src = transcribe_chirp(path), f"Speech-to-Text {STT_MODEL} ({STT_LOCATION}, {STT_LANGUAGE})"
            cache.write_text(json.dumps([w.__dict__ for w in words], indent=1), encoding="utf-8")
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
