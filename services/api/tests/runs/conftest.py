import uuid
from pathlib import Path

import pytest

from kirchhoff.contracts import RunRecord
from kirchhoff.runs.fakes import CheckedStore, build_fake_deps, build_fake_scenarios

INTAKE_FIX = Path(__file__).resolve().parents[1] / "intake" / "fixtures"
GROUND_TRUTH = Path(__file__).resolve().parents[4] / "scenarios" / "hall_a" / "ground_truth.yaml"


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls real Vertex AI; run with KIRCHHOFF_LIVE=1")


@pytest.fixture(scope="session")
def scen_dir(tmp_path_factory):
    return build_fake_scenarios(tmp_path_factory.mktemp("scenarios"), INTAKE_FIX / "tender.yaml",
                                INTAKE_FIX / "geometry.yaml", GROUND_TRUTH)


@pytest.fixture
def deps(scen_dir, tmp_path):
    return build_fake_deps(CheckedStore(), scen_dir, seed_dir=tmp_path, spawn=lambda fn: fn(), heartbeat_s=3600.0)


@pytest.fixture
def make_run(deps):
    def _make(uid: str = "u1", autonomy: str = "ask") -> str:
        rid = uuid.uuid4().hex[:12]
        rec = RunRecord(id=rid, project_id="hall-b", status="running", autonomy=autonomy, phase="p1",
                        started_at=deps.clock())
        deps.store.set_doc(f"workspaces/{uid}/runs/{rid}", rec.model_dump(mode="json"))
        return rid
    return _make


@pytest.fixture
def firestore_safe():
    def _check(store) -> None:
        assert isinstance(store, CheckedStore)
        assert not store.problems, store.problems[:3]
    return _check
