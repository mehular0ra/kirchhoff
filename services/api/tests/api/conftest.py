from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kirchhoff.api.app import create_app
from kirchhoff.runs.fakes import CheckedStore, build_fake_deps, build_fake_scenarios

INTAKE_FIX = Path(__file__).resolve().parents[1] / "intake" / "fixtures"
GROUND_TRUTH = Path(__file__).resolve().parents[4] / "scenarios" / "hall_a" / "ground_truth.yaml"


@pytest.fixture(scope="session")
def scen_dir(tmp_path_factory):
    return build_fake_scenarios(tmp_path_factory.mktemp("scenarios"), INTAKE_FIX / "tender.yaml",
                                INTAKE_FIX / "geometry.yaml", GROUND_TRUTH)


@pytest.fixture
def deps(scen_dir, tmp_path):
    return build_fake_deps(CheckedStore(), scen_dir, seed_dir=tmp_path, spawn=lambda fn: fn(), heartbeat_s=3600.0)


@pytest.fixture
def client(deps):
    return TestClient(create_app(deps=deps, verify_token=lambda token: "u1"))


@pytest.fixture
def auth():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def firestore_safe():
    def _check(store) -> None:
        assert isinstance(store, CheckedStore)
        assert not store.problems, store.problems[:3]
    return _check
