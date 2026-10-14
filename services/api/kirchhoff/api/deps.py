"""Production wiring. Constructing Deps makes no network calls (clients are lazy)."""
import importlib
import logging
import os
from pathlib import Path

from kirchhoff.agents.adk_runner import AdkRunner
from kirchhoff.agents.genai_runner import GenaiRunner
from kirchhoff.agents.runner import RecordingRunner
from kirchhoff.runs.blobs import GcsBlobStore, MemoryBlobStore
from kirchhoff.runs.deps import Deps

log = logging.getLogger("kirchhoff")
_HERE = Path(__file__).resolve()


def _ancestor(n: int) -> Path:
    p = _HERE
    for _ in range(n + 1):
        p = p.parent
    return p


class LazyModule:
    """Imports the module on first attribute access (the WS1 engine may land after this code)."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._mod = None

    def __getattr__(self, attr: str):
        if attr.startswith("_"):
            raise AttributeError(attr)
        if self._mod is None:
            self._mod = importlib.import_module(self._name)
        return getattr(self._mod, attr)


def _first(env: str, *candidates: Path) -> Path:
    if os.environ.get(env):
        return Path(os.environ[env])
    return next((c for c in candidates if c.exists()), candidates[0])


def scenarios_dir() -> Path:  # image: /app/scenarios; repo: <repo>/scenarios
    return _first("KIRCHHOFF_SCENARIOS_DIR", _ancestor(2) / "scenarios", _ancestor(4) / "scenarios")


def seed_dir() -> Path:  # image: /app/seed; repo: the static demo bundles WS4 generates
    return _first("KIRCHHOFF_SEED_DIR", _ancestor(2) / "seed", _ancestor(4) / "apps" / "web" / "public" / "demo" / "projects")


def _enterprise(scen: Path):
    try:
        from kirchhoff.enterprise.client import make_enterprise_client  # WS4
        return make_enterprise_client()
    except ImportError:
        from kirchhoff.agents.ports import load_erp_seed
        from kirchhoff.runs.fakes import FakeEnterprise

        seed = scen / "hall_a" / "erp_seed.yaml"
        log.warning("kirchhoff.enterprise.client unavailable; using the in-process sandbox")
        return FakeEnterprise(load_erp_seed(seed) if seed.exists() else None)


def _asset_engines() -> dict:
    def grid(d: Path) -> dict:
        return importlib.import_module("kirchhoff.engine.grid").evaluate_grid(d)

    def solar(d: Path) -> dict:
        return importlib.import_module("kirchhoff.engine.solar").evaluate_solar(d)

    return {"grid": grid, "solar": solar}


def build_production_deps(store=None) -> Deps:
    scen, seed = scenarios_dir(), seed_dir()
    if store is None:
        from kirchhoff.store.firestore import FirestoreStore
        store = FirestoreStore()
    if os.environ.get("KIRCHHOFF_FAKES") == "1":  # local UI development before WS1/WS4/Vertex are wired
        from kirchhoff.runs.fakes import build_fake_deps
        return build_fake_deps(store, scen, seed_dir=seed, blobs=MemoryBlobStore(public_base=None))
    runner = GenaiRunner() if os.environ.get("KIRCHHOFF_AGENT_BACKEND") == "genai" else AdkRunner()
    if os.environ.get("KIRCHHOFF_RECORD_DIR"):
        runner = RecordingRunner(runner, Path(os.environ["KIRCHHOFF_RECORD_DIR"]))
    blobs = MemoryBlobStore(public_base=None) if os.environ.get("KIRCHHOFF_BLOBS") == "memory" else GcsBlobStore()
    return Deps(store=store, engine=LazyModule("kirchhoff.engine.api"), runner=runner, enterprise=_enterprise(scen),
                blobs=blobs, scenarios_dir=scen, seed_dir=seed, voice_runner=GenaiRunner(),
                asset_engines=_asset_engines())
