"""Task 11 controller ruling: run P1 and P2 against the REAL kirchhoff.engine.api facade (not FakeEngine),
with the ReplayRunner and FAKE_REPLIES standing in for agent calls (no network). Exercises the real Hall A
scenario end to end through the run machinery, asserting the R15 swap, the real 2N loading figures, the
Auto-mode §6.1 pick, and that merging `size_cooling` output into a model that already carries cooling nodes
(ruling P2-R2) never raises ValueError from validate_model's duplicate-id guard."""
from pathlib import Path

import pytest

from kirchhoff.agents.ports import load_erp_seed
from kirchhoff.agents.runner import ReplayRunner
from kirchhoff.contracts import DesignModel, RunRecord
from kirchhoff.engine import api as real_engine
from kirchhoff.runs.blobs import MemoryBlobStore
from kirchhoff.runs.deps import Deps
from kirchhoff.runs.fakes import FAKE_REPLIES, FakeEnterprise
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.orchestrator import start_phase
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.runs.phase2 import run_p2
from kirchhoff.runs.phase3 import run_p3
from kirchhoff.runs.revisions import run_revisions
from kirchhoff.runs.steps import PhaseContext, PhaseOutcome
from kirchhoff.store.memory import MemoryStore

REPO_ROOT = Path(__file__).resolve().parents[4]
SCENARIOS_DIR = REPO_ROOT / "scenarios"


def _review_stub(ctx: PhaseContext) -> PhaseOutcome:
    return PhaseOutcome(gate="review")


def _real_deps(phases: dict) -> Deps:
    """Fix round 1, Minor: shared by `real_deps` and `real_deps_p3`, which differed only in `phases['p3']`."""
    if not (SCENARIOS_DIR / "hall_a" / "tender.yaml").exists():
        pytest.skip("real scenarios/hall_a fixtures not found")
    materials = load_erp_seed(SCENARIOS_DIR / "hall_a" / "erp_seed.yaml")
    return Deps(store=MemoryStore(), engine=real_engine, runner=ReplayRunner(dict(FAKE_REPLIES)),
               enterprise=FakeEnterprise(materials=materials), blobs=MemoryBlobStore(),
               scenarios_dir=SCENARIOS_DIR, seed_dir=SCENARIOS_DIR, spawn=lambda fn: fn(), heartbeat_s=3600.0,
               phases=phases)


@pytest.fixture
def real_deps():
    return _real_deps({"p1": run_p1, "p2": run_p2, "p3": _review_stub})


@pytest.fixture
def real_deps_p3():
    """Same as `real_deps`, but with the real `run_p3` wired in instead of the review stub -- Task 13's
    controller ruling: P1 -> P2 -> P3 against the REAL engine, checker and fix loop included."""
    return _real_deps({"p1": run_p1, "p2": run_p2, "p3": run_p3})


def _make_run(deps, uid="u1", autonomy="auto") -> str:
    rid = "real-engine-1"
    rec = RunRecord(id=rid, project_id="hall-b", status="running", autonomy=autonomy, phase="p1",
                    started_at=deps.clock())
    deps.store.set_doc(run_path(uid, rid), rec.model_dump(mode="json"))
    return rid


def test_p1_p2_against_the_real_engine_auto_mode(real_deps):
    uid = "u1"
    rid = _make_run(real_deps, uid, autonomy="auto")
    start_phase(real_deps, uid, rid, "p1")
    rp = run_path(uid, rid)
    run = real_deps.store.get_doc(rp)

    # The run must not have failed -- in particular, merging `size_cooling` output into a power_options
    # model that already carries cooling_nodes (R20/P2-R2) must never hit validate_model's duplicate-id
    # ValueError guard.
    assert run is not None and run["status"] != "failed", run

    # Auto mode runs straight through the plan and option gates (both in AUTO_GATES) and parks at the
    # review gate the p3 stub returns.
    assert (run["status"], run["gate"]) == ("at_gate", "review"), run

    ann = load_outputs(real_deps.store, real_deps.blobs, rp, "p2.annotate_options")
    options = {o["option"]["id"]: o["option"] for o in ann["options"]}

    # §6.1 Auto rule: the redundancy question's default resolution is "2N" (main body over appendix), so
    # the recommended option must be 2N even though DR is the cheaper option after the swap.
    assert ann["recommended"] == "2N"

    # R15 swap: TX-2500 (0 stock, 98-week lead) is replaced by TX-3150 (in stock, 12-week lead) on every
    # option that carried it.
    two_n_swaps = options["2N"]["swaps"]
    assert two_n_swaps and two_n_swaps[0]["from"] == "TX-2500" and two_n_swaps[0]["to"] == "TX-3150"

    # The real engine's post-swap 2N loading figures (controller ruling): 38.07% normal, 76.15% failover.
    assert options["2N"]["normal_loading_pct"] == 38.07
    assert options["2N"]["failover_loading_pct"] == 76.15

    # Ik'' before/after the swap, from the engine's own short-circuit re-run inside r15_swap.
    assert round(two_n_swaps[0]["ikss_ka_before"], 2) == 60.45
    assert round(two_n_swaps[0]["ikss_ka_after"], 2) == 65.42

    recheck = load_outputs(real_deps.store, real_deps.blobs, rp, "p2.power_recheck")["recheck"]
    assert recheck["2N"]["fail"] == 0
    assert round(recheck["2N"]["ikss_ka_after"], 2) == 65.42

    # The Procurement ledger narrates the swap (R15); Power never puts a free number in its own
    # narration (that's the point of ctx.narrate's digit allowlist, exercised here against real model ids).
    events = real_deps.store.list_docs(f"{rp}/events")
    ledger_titles = [e["title"] for e in events if e["kind"] == "ledger"]
    assert any("TX-2500 replaced by TX-3150 (R15)" in t for t in ledger_titles)


def test_p1_p2_p3_against_the_real_engine_checker_beat(real_deps_p3):
    """Task 13 controller ruling: run P1 -> P2 -> P3 against the REAL engine with `ReplayRunner(FAKE_REPLIES)`
    standing in for the agent calls. This is the demo's checker beat -- the first revision fails exactly
    R05:FA-01 and R11:H-Z2, the fix loop applies the R23 choices (FA-01 -> cable-CBL-240-8P, H-Z2 ->
    local-drop), the second revision is all pass, each revision's `hash` is the engine's own `model_hash`,
    and the run parks at the review gate with Approve enabled (no open findings)."""
    uid = "u1"
    rid = _make_run(real_deps_p3, uid, autonomy="auto")
    start_phase(real_deps_p3, uid, rid, "p1")
    rp = run_path(uid, rid)
    run = real_deps_p3.store.get_doc(rp)
    assert run is not None and run["status"] != "failed", run
    assert (run["status"], run["gate"]) == ("at_gate", "review"), run

    revs = run_revisions(real_deps_p3.store, uid, rid)
    assert len(revs) == 2
    r1, r2 = revs

    fail_ids = {f["id"] for f in real_deps_p3.store.list_docs(f"workspaces/{uid}/revisions/{r1['id']}/findings")
               if f["status"] == "fail"}
    assert fail_ids == {"R05:FA-01", "R11:H-Z2"}
    assert r1["check_summary"]["fail"] == 2

    f1 = {f["id"]: f for f in real_deps_p3.store.list_docs(f"workspaces/{uid}/revisions/{r1['id']}/findings")}
    assert f1["R05:FA-01"]["fix"]["candidate"] == "FA-01:cable-CBL-240-8P"
    assert f1["R11:H-Z2"]["fix"]["candidate"] == "H-Z2:local-drop"

    assert r2["check_summary"]["fail"] == 0 and r2["parent"] == r1["id"]

    # R22: each revision's `hash` is always `engine.model_hash(model)`, recomputed from the blob-stored model.
    r2_model = None
    for rev in (r1, r2):
        assert rev["model"] is None
        model = DesignModel.model_validate_json(real_deps_p3.blobs.get(f"workspaces/{uid}/{rev['model_url']}"))
        assert rev["hash"] == real_engine.model_hash(model)
        r2_model = model
    assert r1["hash"] != r2["hash"]

    # Fix round 1, Minor: also assert `warn == 0` (no open findings of any severity on the latest
    # revision -- Approve must not be disabled, WS3 rule), and that the applied FA-01 fix's own real
    # candidate patch (not a forged one) landed on r2's model, reloaded from the blob store.
    assert r2["check_summary"]["fail"] == 0 and r2["check_summary"]["warn"] == 0
    fa = next(c for c in r2_model.connections if c.id == "FA-01")
    assert fa.catalogue_id == "CBL-240-8P"
