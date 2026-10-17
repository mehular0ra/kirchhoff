"""The measured-numbers card of the longer video cut (docs/submission/video/scenes/s10-numbers.html) shows four figures, and a
viewer can check each one: the seeded-fault benchmark (35 of 35, no false alarms), the verified tender quotes (25 of 26), the median
time to a checker-clean design (149 s) and the Gemini cost of one design ($0.066). Three of them are hand-kept in
scenes/lib/measured.js, the fourth comes from the recorded run in scenes/lib/data.js. This test ties every one to its evidence (the
engine's own benchmark, run here; the deck's fill.yaml; the recorded run), keeps the scene from typing a number of its own, and keeps
it registered and previewed. A later edit that lets the card drift from the deck or the engine fails here instead of in the video."""
import re
import statistics
from pathlib import Path

from kirchhoff.engine.benchmark import mutations, run_benchmark

REPO = Path(__file__).resolve().parents[4]
SCENES = REPO / "docs" / "submission" / "video" / "scenes"
MEASURED = SCENES / "lib" / "measured.js"
DATA = SCENES / "lib" / "data.js"
SCENE = SCENES / "s10-numbers.html"
RENDER = SCENES / "render.py"
PREVIEW = SCENES / "previews" / "s10-numbers.png"
FILL = REPO / "docs" / "submission" / "deck" / "fill.yaml"


def _block(name: str) -> str:
    """The body of one `name: { ... }` entry of lib/measured.js. The file is a JS object literal; pytest has no JS engine, so the
    numbers are read with patterns (the strings in the file hold no braces)."""
    m = re.search(rf"\b{name}:\s*\{{(.*?)\}}", MEASURED.read_text(encoding="utf-8"), re.S)
    assert m, f"lib/measured.js has no {name!r} entry"
    return m.group(1)


def _int(block: str, key: str) -> int:
    m = re.search(rf"\b{key}:\s*(\d+)\b", block)
    assert m, f"lib/measured.js: no whole number for {key!r}"
    return int(m.group(1))


def _fill_line(key: str) -> str:
    m = re.search(rf"^\s*{key}:\s*(.+)$", FILL.read_text(encoding="utf-8"), re.M)
    assert m, f"deck/fill.yaml has no {key!r} entry"
    return m.group(1)


def test_the_benchmark_figures_are_the_engines_own():
    faults = _block("faults")
    report = run_benchmark()
    assert _int(faults, "total") == report["mutations"] == len(mutations()), "the card's count of planted faults is not the benchmark's"
    assert _int(faults, "caught") == report["caught"], "the card's count of caught faults is not what the benchmark catches now"
    assert _int(faults, "false_positives") == report["false_positive_mutations"]


def test_the_median_is_the_deck_s_and_follows_from_its_runs():
    median = _block("median")
    line = _fill_line("upload_to_clean_median")
    runs = [float(x) for x in re.findall(r"(\d+\.\d) s", line)]
    assert len(runs) == _int(median, "runs"), "the card's run count is not the number of runs fill.yaml lists"
    assert round(statistics.median(runs)) == _int(median, "seconds"), "the card's median is not the median of the listed runs"
    assert f"Median {_int(median, 'seconds')} s" in line and f"over {_int(median, 'runs')} live runs" in line


def test_the_cost_is_the_deck_s():
    usd = re.search(r"\busd:\s*'(\d+\.\d+)'", _block("cost"))
    assert usd, "lib/measured.js: no quoted dollar amount for 'usd'"
    assert f"${usd.group(1)}" in _fill_line("usd_per_run")
    assert f"about ${usd.group(1)} per design" in _fill_line("tokens_and_usd_per_run")


def test_the_quote_counts_are_the_recorded_runs_and_the_deck_s():
    m = re.search(r'"intake":\s*\{.*?"verified":\s*(\d+),\s*"total":\s*(\d+)', DATA.read_text(encoding="utf-8"), re.S)
    assert m, "lib/data.js has no intake counts"
    verified, total = int(m.group(1)), int(m.group(2))
    line = _fill_line("intake_accuracy")
    assert f"{verified} of {total} extracted quotes verified" in line
    recall = _block("recall")
    low, high = (re.search(rf"\b{k}:\s*'(\d\.\d\d)'", recall) for k in ("low", "high"))
    assert low and high, "lib/measured.js: the recall needs a quoted low and high"
    assert f"recall of {low.group(1)} to {high.group(1)}" in line, "the card's intake recall is not the deck's"
    words = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}  # the deck writes the count of runs as a word
    assert f"over {words.get(_int(recall, 'runs'))} live runs" in line, "the card's run count for the recall is not the deck's"


def test_the_scene_reads_its_numbers_and_types_none():
    html = SCENE.read_text(encoding="utf-8")
    assert 'src="lib/measured.js"' in html and "window.KMEASURED" in html and "K.D.intake" in html
    typed = re.findall(r"(?<![\w.])(?:35|149|0\.066|0\.78|0\.84|25|26)(?![\w.])", html)
    assert not typed, f"s10-numbers.html types its own figures {typed}; they must come from lib/measured.js or the recorded run"


def test_the_scene_is_registered_and_has_its_preview():
    assert re.search(r'\("s10-numbers",\s*"s10-numbers\.html"', RENDER.read_text(encoding="utf-8")), "render.py does not list s10-numbers"
    assert PREVIEW.is_file(), "scenes/previews/s10-numbers.png is missing"
    head = PREVIEW.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n" and int.from_bytes(head[16:20], "big") == 1920 and int.from_bytes(head[20:24], "big") == 1080
