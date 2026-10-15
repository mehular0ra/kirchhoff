import threading
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from kirchhoff.agents import copilot as copilot_mod
from kirchhoff.agents.copilot import load_seed_bundle
from kirchhoff.agents.runner import AgentResult, AgentSpec
from kirchhoff.api import copilot_routes
from kirchhoff.api.app import create_app
from kirchhoff.contracts import Finding
from kirchhoff.enterprise.client import EnterpriseUnavailable
from kirchhoff.runs.fakes import FakeEngine, FakeEnterprise


def _post(client, auth, path, body):
    return client.post(path, json=body, headers=auth)


def test_what_if_on_a_seed_revision(client, seeded, auth):
    r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})
    assert r.status_code == 200
    body = r.json()
    assert body["revision_ref"] == "seed:hall-a@r2" and body["impact_chain"]
    assert {"R01", "R02", "R08"} <= {f["rule_id"] for f in body["findings"] if f["status"] == "fail"}


def test_what_if_on_a_workspace_revision(client, seeded, auth):
    model = load_seed_bundle(seeded.seed_dir, "hall-a").revisions[1].model
    seeded.store.set_doc("workspaces/u1/revisions/x-r2", {"id": "x-r2", "model": None,
                                                          "model_url": "revisions/x-r2/model.json"})
    seeded.blobs.put("workspaces/u1/revisions/x-r2/model.json", model.model_dump_json().encode(), "application/json")
    r = _post(client, auth, "/api/what-if", {"revision_ref": "ws:x-r2", "param": "rack_kw", "value": 150})
    assert r.status_code == 200 and r.json()["findings"] == []


def test_what_if_on_a_workspace_revision_with_a_missing_model_blob_is_404(client, seeded, auth):
    seeded.store.set_doc("workspaces/u1/revisions/x-r3", {"id": "x-r3", "model": None,
                                                          "model_url": "revisions/x-r3/model.json"})
    r = _post(client, auth, "/api/what-if", {"revision_ref": "ws:x-r3", "param": "rack_kw", "value": 1})
    assert r.status_code == 404 and r.json() == {"detail": "revision_not_found"}


def test_what_if_on_another_users_workspace_revision_is_404(client, seeded, auth):
    model = load_seed_bundle(seeded.seed_dir, "hall-a").revisions[1].model
    seeded.store.set_doc("workspaces/u1/revisions/x-r2", {"id": "x-r2", "model": None,
                                                          "model_url": "revisions/x-r2/model.json"})
    seeded.blobs.put("workspaces/u1/revisions/x-r2/model.json", model.model_dump_json().encode(), "application/json")
    client2 = TestClient(create_app(deps=seeded, verify_token=lambda token: "u2"))
    r = _post(client2, auth, "/api/what-if", {"revision_ref": "ws:x-r2", "param": "rack_kw", "value": 1})
    assert r.status_code == 404 and r.json() == {"detail": "revision_not_found"}


def test_what_if_errors(client, seeded, auth):
    assert _post(client, auth, "/api/what-if", {"revision_ref": "foo", "param": "rack_kw", "value": 1}).json() == \
        {"detail": "bad_revision_ref"}
    r9 = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r9", "param": "rack_kw", "value": 1})
    assert r9.status_code == 404 and r9.json() == {"detail": "revision_not_found"}
    assert _post(client, auth, "/api/what-if", {"revision_ref": "ws:nope", "param": "rack_kw",
                                                "value": 1}).status_code == 404
    assert _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "voltage",
                                                "value": 1}).status_code == 422


def test_what_if_on_a_corrupt_seed_bundle_is_not_labelled_bad_revision_ref(client, seeded, auth):
    """A bad_revision_ref ValueError is only ever raised for a ref matching neither `ws:` nor `seed:`; a
    structurally invalid bundle (ValidationError, also a ValueError subclass) must not be mislabelled."""
    (seeded.seed_dir / "broken.json").write_text('{"project": 1}', encoding="utf-8")
    with pytest.raises(ValidationError):
        _post(client, auth, "/api/what-if", {"revision_ref": "seed:broken@r1", "param": "rack_kw", "value": 1})


class SlowEngine(FakeEngine):
    def what_if(self, *args, **kwargs):
        time.sleep(0.3)
        return super().what_if(*args, **kwargs)


def test_what_if_times_out(client, seeded, auth, monkeypatch):
    seeded.engine = SlowEngine()
    monkeypatch.setattr(copilot_routes, "WHAT_IF_TIMEOUT_S", 0.05)
    r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})
    assert r.status_code == 504 and r.json() == {"detail": "timeout"}


class RaisingEngine(FakeEngine):
    def what_if(self, *args, **kwargs):
        raise ValueError("rack_kw must be within [1.0, 400.0]")


def test_what_if_value_error_from_the_engine_is_422_invalid_value(client, seeded, auth):
    seeded.engine = RaisingEngine()
    r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 1})
    assert r.status_code == 422 and r.json() == {"detail": "invalid_value"}


def test_what_if_out_of_range_value_with_the_real_engine_is_422(real_client, auth):
    client, _bundle = real_client
    r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 1000})
    assert r.status_code == 422 and r.json() == {"detail": "invalid_value"}


class DownEnterprise:
    def list_materials(self):
        raise EnterpriseUnavailable("sandbox down")


def test_what_if_returns_503_when_the_enterprise_sandbox_is_unavailable(client, seeded, auth):
    seeded.enterprise = DownEnterprise()
    seeded._erp = None  # force deps.erp() to re-fetch instead of serving the fixture's cached snapshot
    r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})
    assert r.status_code == 503 and r.json() == {"detail": "enterprise_unavailable"}


# --- Task 15 residual (b): `except ValueError` in /api/what-if must not mislabel a server bug
# (pydantic ValidationError, also a ValueError subclass) or an unrelated enterprise error as 422
# invalid_value, which is reserved for the what-if value genuinely being out of range.
class ValidationErrorEngine(FakeEngine):
    def what_if(self, *args, **kwargs):
        Finding.model_validate({})  # missing required fields: raises pydantic.ValidationError


def test_what_if_validation_error_from_the_engine_is_not_mislabelled_422(client, seeded, auth):
    seeded.engine = ValidationErrorEngine()
    with pytest.raises(ValidationError):
        _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})


class ValueErrorEnterprise(FakeEnterprise):
    def list_materials(self):
        raise ValueError("422 from the sandbox: bad material query")  # mirrors HttpEnterpriseClient._call


def test_what_if_enterprise_value_error_is_not_mislabelled_422_invalid_value(client, seeded, auth):
    seeded.enterprise = ValueErrorEnterprise()
    seeded._erp = None  # force deps.erp() to re-fetch instead of serving the fixture's cached snapshot
    with pytest.raises(ValueError):
        _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})


def test_explain_fills_placeholders_from_the_engine_record(client, seeded, auth):
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    assert r.json() == {"text": "FA-01 has a voltage drop of 2.16%, above the 2% limit in §4.6. It is the longest "
                                "A-side feeder from A1."}


def test_explain_with_free_numbers_uses_the_rule_template(client, seeded, auth):
    seeded.runner.replies["copilot:explain:R05:FA-01"] = {"text": "The drop is 2.16% because it is 82 m long."}
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    assert r.json() == {"text": "Voltage drop: 2.16% against a limit of 2%."}


def test_explain_survives_a_model_failure(client, seeded, auth):
    seeded.runner.replies["copilot:explain:R05:FA-01"] = {"raise": "vertex down"}
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    assert r.json() == {"text": "Voltage drop: 2.16% against a limit of 2%."}


def test_explain_with_raw_digits_never_leaks_them_into_the_response(client, seeded, auth):
    """Trust rule (spec §6.3): raw LLM digits must never reach the response, even disguised inside a
    sentence that also carries the correct-looking number."""
    seeded.runner.replies["copilot:explain:R05:FA-01"] = {"text": "Careful review shows the drop is 9.99% here."}
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    body = r.json()
    assert "9.99" not in body["text"]
    assert body == {"text": "Voltage drop: 2.16% against a limit of 2%."}


@pytest.mark.parametrize("reply", ["FA-01 is at {rack_kw} kW of load.", "The drop is two point one six percent."],
                         ids=["unfillable-placeholder", "number-words"])
def test_explain_never_shows_an_unfillable_placeholder_or_a_quantity_in_words(client, seeded, auth, reply):
    """P2 final fix wave, Important 1: explain fills only {value}, {limit} and {unit} from the finding record;
    any other placeholder would reach the UI literally, and a quantity in words is still an LLM number."""
    seeded.runner.replies["copilot:explain:R05:FA-01"] = {"text": reply}
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    assert r.json() == {"text": "Voltage drop: 2.16% against a limit of 2%."}


def test_explain_unknown_finding(client, seeded, auth):
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R99:X"})
    assert r.status_code == 404 and r.json() == {"detail": "finding_not_found"}


def test_explain_on_a_workspace_revision(client, seeded, auth):
    bundle = load_seed_bundle(seeded.seed_dir, "hall-a")
    model = bundle.revisions[0].model
    finding = next(f for f in bundle.findings["r1"] if f.id == "R05:FA-01")
    seeded.store.set_doc("workspaces/u1/revisions/x-r1", {"id": "x-r1", "model": None,
                                                          "model_url": "revisions/x-r1/model.json"})
    seeded.blobs.put("workspaces/u1/revisions/x-r1/model.json", model.model_dump_json().encode(), "application/json")
    seeded.store.set_doc(f"workspaces/u1/revisions/x-r1/findings/{finding.id}", finding.model_dump(mode="json"))
    r = _post(client, auth, "/api/explain", {"revision_ref": "ws:x-r1", "finding_id": finding.id})
    assert r.json() == {"text": "FA-01 has a voltage drop of 2.16%, above the 2% limit in §4.6. It is the longest "
                                "A-side feeder from A1."}


# --- Task 15 residual (a): the explain deadline must be a single clock taken at submit time, so a slow
# ERP fetch doesn't let the total exceed the LLM budget (reviewer measured 11.02s: a 3s ERP fetch stacked
# on top of the full 8s LLM timeout, against the service's ~10s-per-/api budget).
def test_explain_deadline_is_measured_from_submit_not_after_a_slow_erp_fetch(client, seeded, auth, monkeypatch):
    """Fix round 1, Minor: event-based, not a fixed time.sleep(5.0) -- the LLM-pool worker is released as
    soon as the assertions are done, instead of staying busy for the rest of the test run regardless."""
    monkeypatch.setattr(copilot_mod, "COPILOT", AgentSpec("copilot", "x", timeout_s=1.5))
    release = threading.Event()

    class SlowEnterprise(FakeEnterprise):
        def list_materials(self):
            time.sleep(1.0)
            return super().list_materials()

    class HungRunner:
        def run(self, spec, key, message, tools=(), attachments=()):
            release.wait(10)  # never returns within the (short, patched) budget until released below
            return AgentResult(text="too late")

    seeded.enterprise = SlowEnterprise()
    seeded._erp = None  # force deps.erp() to re-fetch (pays the slow ERP cost) instead of the cached snapshot
    seeded.runner = HungRunner()
    bundle = load_seed_bundle(seeded.seed_dir, "hall-a")
    model = bundle.revisions[0].model
    finding = next(f for f in bundle.findings["r1"] if f.id == "R05:FA-01")
    start = time.monotonic()
    try:
        text = copilot_mod.explain_text(seeded, model, finding)
        elapsed = time.monotonic() - start
        assert text == "Voltage drop: 2.16% against a limit of 2%."
        # Fixed: one deadline (submit time + timeout_s + 1 = 2.5s) covers the ERP fetch and the LLM wait
        # together, so elapsed lands near 2.5s. Buggy: the LLM wait alone gets the full 2.5s *after* the 1.0s
        # ERP fetch already elapsed, landing near 3.5s. 3.0s cleanly separates the two.
        assert elapsed < 3.0
    finally:
        release.set()


def test_explain_saturating_the_llm_pool_does_not_delay_what_if(client, seeded, auth, monkeypatch):
    """A burst of slow explain calls must not starve what-if: the two use separate executors. Event-based
    (not wall-clock), so it cannot flake under load: SlowRunner blocks on an Event until released, and the
    what-if request is only sent once enough calls have actually started to saturate the LLM pool."""
    release = threading.Event()
    started = 0
    lock = threading.Lock()

    class SlowRunner:
        def run(self, spec, key, message, tools=(), attachments=()):
            nonlocal started
            with lock:
                started += 1
            release.wait(10)
            return AgentResult(text="slow reply")

    seeded.runner = SlowRunner()
    monkeypatch.setattr(copilot_routes, "WHAT_IF_TIMEOUT_S", 2.0)
    bundle = load_seed_bundle(seeded.seed_dir, "hall-a")
    model = bundle.revisions[0].model
    finding = next(f for f in bundle.findings["r1"] if f.status == "fail")
    threads = [threading.Thread(target=copilot_mod.explain_text, args=(seeded, model, finding))
               for _ in range(8)]  # exactly the LLM pool's worker count: fully saturates it
    for t in threads:
        t.start()
    deadline = time.monotonic() + 5.0
    while True:
        with lock:
            if started >= 8:
                break
        assert time.monotonic() < deadline, "explain threads never saturated the LLM pool"
        time.sleep(0.01)
    try:
        r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})
        assert r.status_code == 200
    finally:
        release.set()
        for t in threads:
            t.join(timeout=5)


# --- Real-engine verification (controller's measured 200 kW what-if beat): the `real_client` fixture
# (tests/api/conftest.py) wires the real engine and the production ERP catalogue to the real WS4 hall-a
# seed bundle, so this runs the actual demo-world numbers end to end through the live API.
def test_what_if_matches_every_precomputed_what_if_on_the_production_catalogue(real_client, auth):
    client, bundle = real_client
    assert len(bundle.what_ifs) == 5
    for wi in bundle.what_ifs:
        r = _post(client, auth, "/api/what-if", {"revision_ref": wi.revision_ref, "param": wi.param,
                                                 "value": wi.value})
        assert r.status_code == 200
        assert r.json() == wi.model_dump(mode="json")
