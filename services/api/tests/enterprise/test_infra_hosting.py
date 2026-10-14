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


def test_no_cache_headers_do_not_match_api_paths():
    for api_path in ("/api/health", "/api/whoami", "/api/enterprise/erp/materials"):
        assert _cache(api_path) == [], f"API path {api_path} should not match any cache rule, got {_cache(api_path)}"


def test_smoke_checks_the_three_cache_policies():
    text = (REPO / "infra" / "smoke.sh").read_text(encoding="utf-8")
    assert "no-cache" in text and "public, max-age=31536000, immutable" in text


def test_smoke_checks_api_headers_are_not_no_cache():
    text = (REPO / "infra" / "smoke.sh").read_text(encoding="utf-8")
    assert "no-cache" in text and "/api/health" in text


def test_storage_cors_allows_plain_gets_from_the_site():
    cors = json.loads((REPO / "infra" / "storage-cors.json").read_text(encoding="utf-8"))
    assert cors == [{"origin": ["https://kirchhoff.web.app", "https://kirchhoff.firebaseapp.com", "http://localhost:5173"],
                     "method": ["GET"], "responseHeader": ["Content-Type", "Content-Disposition"], "maxAgeSeconds": 3600}]


def test_web_deploy_gates_on_the_demo_world_and_smoke_checks_it():
    deploy = (REPO / "infra" / "deploy_web.sh").read_text(encoding="utf-8")
    assert "build.py --check" in deploy and "ALLOW_NO_DEMO" in deploy and "dist/demo/docs/tender-hall-a.pdf" in deploy
    assert "cp " not in deploy  # WS4 never writes apps/web/public/demo/docs (WS3's sync script does)
    smoke = (REPO / "infra" / "smoke.sh").read_text(encoding="utf-8")
    for path in ("/demo/world.json", "/demo/projects/hall-a.json", "/demo/docs/tender-hall-a.pdf",
                 "/demo/files/hall-a/calc-report.pdf"):
        assert path in smoke, path
