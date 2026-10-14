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


from kirchhoff.contracts import Project, ProjectBundle, Revision


@pytest.fixture
def seeded(deps):
    """Writes seed:hall-a@r1 (2 fails) and seed:hall-a@r2 (all pass) as a static ProjectBundle."""
    eng, erp, scn = deps.engine, deps.erp(), deps.scenario()
    racks = eng.place_racks(scn)
    _, model = next(p for p in eng.annotate_options(scn, eng.power_options(scn, racks), erp) if p[0].id == "2N")
    r1 = eng.route(scn, model)
    f1 = eng.check(scn, r1, erp)
    r2 = r1
    for f in [f for f in f1 if f.status == "fail"]:
        r2 = eng.apply_fix(r2, eng.fix_candidates(scn, r2, f, erp)[0])
    bundle = ProjectBundle(
        project=Project(id="hall-a", name="Deccan AI Campus · Hall A", client="Deccan Compute", asset_pack="datahall",
                        state="signed", sample=True, updated_at=0.0),
        revisions=[Revision(id="r1", project_id="hall-a", author="Priya Raman", hash=eng.model_hash(r1), model=r1,
                            status="checked", created_at=0.0),
                   Revision(id="r2", project_id="hall-a", parent="r1", author="Priya Raman", hash=eng.model_hash(r2),
                            model=r2, status="signed", created_at=0.0)],
        findings={"r1": f1, "r2": eng.check(scn, r2, erp)})
    (deps.seed_dir / "hall-a.json").write_text(bundle.model_dump_json(), encoding="utf-8")
    return deps
