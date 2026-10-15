import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kirchhoff.api.app import create_app
from kirchhoff.enterprise.world.inbox import load_inbox, load_inbox_seed
from kirchhoff.inbox.fit import warm_engine
from kirchhoff.inbox.triage import triage_email
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


# --- Task 15 fix round 1 (Important #1): a client wired to the real engine and the production ERP
# catalogue, serving the real WS4 hall-a seed bundle, so the co-pilot's measured 200 kW what-if beat is
# verified end to end rather than against FakeEngine/FakeEnterprise fixtures.
from kirchhoff.engine import api as real_engine
from kirchhoff.engine.scenario import scenarios_root
from kirchhoff.enterprise.model import load_enterprise_seed
from kirchhoff.enterprise.paths import enterprise_seed_path, repo_root
from kirchhoff.runs.fakes import FakeEnterprise


@pytest.fixture
def real_client(tmp_path):
    """A TestClient wired to the real engine (not FakeEngine) and the production ERP catalogue
    (scenarios/demo_world/out/enterprise_seed.json), serving the real WS4 hall-a seed bundle checked into
    the repo. Fails loudly, not a skip, if either is missing."""
    root = repo_root()
    assert root is not None, "kirchhoff.enterprise.paths.repo_root() could not locate the repo checkout"
    bundle_path = root / "apps" / "web" / "public" / "demo" / "projects" / "hall-a.json"
    assert bundle_path.exists(), f"WS4 seed bundle is missing: {bundle_path}"
    raw = bundle_path.read_text(encoding="utf-8")
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "hall-a.json").write_text(raw, encoding="utf-8")
    catalogue = load_enterprise_seed(enterprise_seed_path()).materials
    deps = build_fake_deps(CheckedStore(), scenarios_root(), seed_dir=seed_dir, engine=real_engine,
                           enterprise=FakeEnterprise(catalogue), spawn=lambda fn: fn(), heartbeat_s=3600.0)
    client = TestClient(create_app(deps=deps, verify_token=lambda token: "u1"))
    return client, ProjectBundle.model_validate_json(raw)


REPO = Path(__file__).resolve().parents[4]


@pytest.fixture
def inbox_ready(deps):
    """I-1's inbox seed and rendered attachments in the fake scenarios dir (the API's file fallback). Precomputed
    triage is stripped, so the tests do not depend on whether the golden capture has been folded in yet."""
    warm_engine()  # the live-triage tests run the engine against the real 9.5 s budget: pay the cold import here
    out = deps.scenarios_dir / "demo_world" / "out"
    out.mkdir(parents=True, exist_ok=True)
    seed = load_inbox_seed(REPO / "scenarios" / "demo_world" / "out" / "inbox_seed.json")
    seed = seed.model_copy(update={"emails": [e.model_copy(update={"triage": None}) for e in seed.emails]})
    (out / "inbox_seed.json").write_text(seed.model_dump_json(indent=2), encoding="utf-8")
    shutil.copytree(REPO / "scenarios" / "demo_world" / "out" / "inbox", out / "inbox", dirs_exist_ok=True)
    return deps


@pytest.fixture
def inbox_precomputed(inbox_ready):
    """Firestore seed/inbox with every email's precomputed triage (replayed), as WS4's seed loader writes it."""
    deps = inbox_ready
    seed = load_inbox_seed(deps.scenarios_dir / "demo_world" / "out" / "inbox_seed.json")
    emails = [e.model_copy(update={"triage": triage_email(
        e, runner=deps.runner, scenarios_dir=deps.scenarios_dir, opportunities=deps.enterprise.list_opportunities(None),
        erp=deps.erp(), appetite=seed.appetite, as_of=seed.as_of, source="precomputed",
        now=seed.as_of).model_dump(mode="json")}) for e in seed.emails]
    load_inbox(deps.store, seed.model_copy(update={"emails": emails}))
    return deps
