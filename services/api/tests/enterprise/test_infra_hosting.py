import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HOSTING = json.loads((REPO / "infra" / "firebase.json").read_text(encoding="utf-8"))["hosting"]


def _matches(rule: dict, path: str) -> bool:
    if "regex" in rule:
        return re.fullmatch(rule["regex"], path) is not None
    src = rule["source"]
    return path.startswith(src[:-2]) if src.endswith("/**") else path == src


def _cache(path: str) -> list[str]:
    return [h["value"] for r in HOSTING.get("headers", []) if _matches(r, path)
            for h in r["headers"] if h["key"] == "Cache-Control"]


def test_exactly_one_cache_policy_per_kind_of_path():
    for spa in ("/", "/app", "/app/p/hall-a", "/app/p/hall-a/review/r2", "/app/integrations", "/index.html"):
        assert _cache(spa) == ["no-cache"], spa
    assert _cache("/assets/index-Bx81abcd.js") == ["public, max-age=31536000, immutable"]
    assert _cache("/assets/index-Bx81abcd.css") == ["public, max-age=31536000, immutable"]
    for demo in ("/demo/world.json", "/demo/projects/hall-a.json", "/demo/docs/tender-hall-a.pdf",
                 "/demo/files/hall-a/calc-report.pdf"):
        assert _cache(demo) == ["public, max-age=300"], demo


def test_rewrites_and_public_dir_are_unchanged():
    assert HOSTING["public"] == "public_dist" and HOSTING["site"] == "kirchhoff"
    assert HOSTING["rewrites"] == [
        {"source": "/api/**", "run": {"serviceId": "kirchhoff-api", "region": "asia-south1"}},
        {"source": "**", "destination": "/index.html"},
    ]


def test_regexes_are_re2_compatible():
    assert all(not re.search(r"\(\?[=!<]", r["regex"]) for r in HOSTING["headers"] if "regex" in r)


def test_smoke_checks_the_three_cache_policies():
    text = (REPO / "infra" / "smoke.sh").read_text(encoding="utf-8")
    assert "no-cache" in text and "public, max-age=31536000, immutable" in text
