"""P2 final fix wave, Important 4: Deps.erp() has its own lock, serves the last good snapshot when a refresh
fails, and P1 fetches it before the long intake LLM call."""
import logging
import threading
import time

import pytest

from kirchhoff.runs.leases import run_path
from kirchhoff.runs.orchestrator import resume_from_gate, start_phase
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.runs.phase2 import run_p2
from kirchhoff.runs.steps import PhaseOutcome


class FlakyEnterprise:
    """Delegates to the fake ERP until `down` is set, then every list_materials() call fails."""

    def __init__(self, inner) -> None:
        self.inner, self.down, self.calls = inner, False, 0

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def list_materials(self):
        self.calls += 1
        if self.down:
            raise ConnectionError("ERP sandbox unreachable")
        return self.inner.list_materials()


@pytest.fixture
def flaky(deps):
    deps.enterprise = FlakyEnterprise(deps.enterprise)
    return deps


def test_a_failed_refresh_serves_the_last_snapshot_and_logs_a_warning(flaky, caplog):
    first = flaky.erp()
    flaky.erp_ttl_s, flaky.enterprise.down = 0.0, True
    with caplog.at_level(logging.WARNING, logger="kirchhoff.runs"):
        assert flaky.erp() is first
    assert any(r.levelno == logging.WARNING and "ERP refresh failed" in r.getMessage() for r in caplog.records)


def test_a_failed_refresh_backs_off_instead_of_retrying_on_every_call(flaky):
    flaky.erp()
    flaky.erp_ttl_s, flaky.enterprise.down = 0.0, True
    flaky.erp()
    calls = flaky.enterprise.calls
    for _ in range(5):
        flaky.erp()
    assert flaky.enterprise.calls == calls  # a down ERP costs one slow call per back-off window, not one per call


def test_a_failed_first_fetch_still_raises(flaky):
    flaky.enterprise.down = True
    with pytest.raises(ConnectionError):
        flaky.erp()


def test_scenario_never_waits_behind_a_slow_erp_refresh(flaky):
    release, entered = threading.Event(), threading.Event()

    class SlowEnterprise:
        def list_materials(self):
            entered.set()
            release.wait(5)
            return []

    flaky.enterprise = SlowEnterprise()
    t = threading.Thread(target=flaky.erp, daemon=True)
    t.start()
    try:
        assert entered.wait(2)
        start = time.monotonic()
        flaky.scenario()
        assert time.monotonic() - start < 1.0
    finally:
        release.set()
        t.join(5)


def _review_stub(ctx):
    return PhaseOutcome(gate="review")


def test_a_failing_refresh_with_a_cached_snapshot_lets_the_run_continue(flaky, make_run):
    flaky.phases = {"p1": run_p1, "p2": run_p2, "p3": _review_stub}
    flaky.erp()  # a good snapshot from before the outage
    flaky.erp_ttl_s, flaky.enterprise.down = 0.0, True
    rid = make_run()
    start_phase(flaky, "u1", rid, "p1")
    resume_from_gate(flaky, "u1", rid, "plan")
    run = flaky.store.get_doc(run_path("u1", rid))
    assert (run["status"], run["gate"]) == ("at_gate", "option")


def test_intake_fetches_the_erp_before_the_llm_call(flaky, make_run):
    """An ERP outage with no snapshot fails P1 fast, before the 60-240 s intake call spends any tokens."""
    flaky.phases = {"p1": run_p1}
    flaky.enterprise.down = True
    rid = make_run()
    start_phase(flaky, "u1", rid, "p1")
    assert flaky.store.get_doc(run_path("u1", rid))["status"] == "failed"  # resumable once the ERP is back
    assert not [k for k in flaky.runner.calls if k.startswith("intake:")]
