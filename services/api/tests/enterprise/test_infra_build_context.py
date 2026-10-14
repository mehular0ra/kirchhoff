import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / "infra" / "build_context.sh"


def _stage(tmp_path: Path) -> Path:
    out = tmp_path / "ctx"
    r = subprocess.run(["bash", str(SCRIPT), str(out)], capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stderr
    return out


def test_context_ships_code_scenarios_and_seed_but_no_venv(tmp_path):
    out = _stage(tmp_path)
    for rel in ("Dockerfile", ".dockerignore", ".gcloudignore", "pyproject.toml", "uv.lock", "kirchhoff/api/app.py",
                "kirchhoff/enterprise/app.py", "scenarios/hall_a/erp_seed.yaml", "scenarios/demo_world/world.yaml"):
        assert (out / rel).exists(), rel
    assert (out / "seed").is_dir()
    for banned in (".venv", "tests", "build", ".pytest_cache"):
        assert not (out / banned).exists(), banned
    assert not list(out.rglob("__pycache__"))


def test_seed_bundles_are_staged(tmp_path):
    bundles = sorted((REPO / "apps" / "web" / "public" / "demo" / "projects").glob("*.json"))
    if not bundles:
        pytest.skip("no demo bundles yet (Task 11 generates them)")
    out = _stage(tmp_path)
    assert sorted(p.name for p in (out / "seed").glob("*.json")) == [p.name for p in bundles]


def test_dockerfile_and_ignore_files():
    df = (REPO / "services" / "api" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY scenarios /app/scenarios" in df and "COPY seed /app/seed" in df
    assert "KIRCHHOFF_SCENARIOS_DIR=/app/scenarios" in df and "KIRCHHOFF_SEED_DIR=/app/seed" in df
    assert "uv sync --frozen" in df and "uv lock" not in df
    for name in (".dockerignore", ".gcloudignore"):
        text = (REPO / "services" / "api" / name).read_text(encoding="utf-8")
        assert ".venv" in text and "tests" in text and "uv.lock" not in text


@pytest.mark.skipif(not os.environ.get("KIRCHHOFF_DOCKER_TEST"), reason="set KIRCHHOFF_DOCKER_TEST=1 (slow, needs docker)")
def test_image_contains_scenarios_and_enterprise_entrypoint(tmp_path):
    out = _stage(tmp_path)
    subprocess.run(["docker", "build", "-t", "kirchhoff-local-test", str(out)], check=True)
    r = subprocess.run(["docker", "run", "--rm", "--entrypoint", "/app/.venv/bin/python", "kirchhoff-local-test", "-c",
                        "import pathlib, kirchhoff.enterprise.app, kirchhoff.api.app; "
                        "assert pathlib.Path('/app/scenarios/hall_a/erp_seed.yaml').exists(); "
                        "assert pathlib.Path('/app/seed').is_dir(); print('ok')"],
                       capture_output=True, text=True)
    assert r.stdout.strip() == "ok", r.stderr
