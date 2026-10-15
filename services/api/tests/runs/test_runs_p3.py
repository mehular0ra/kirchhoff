import pytest
import yaml

from kirchhoff.contracts import Citation, DesignModel, Finding
from kirchhoff.runs.fakes import FakeEngine
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.orchestrator import resume_from_gate, start_phase
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.runs.phase2 import run_p2
from kirchhoff.runs.phase3 import run_p3
from kirchhoff.runs.revisions import latest_revision, run_revisions, with_citation_boxes


@pytest.fixture
def p123(deps):
    deps.phases = {"p1": run_p1, "p2": run_p2, "p3": run_p3}
    return deps


def _to_review(d, make_run, autonomy="ask", option="2N") -> str:
    rid = make_run(autonomy=autonomy)
    start_phase(d, "u1", rid, "p1")
    if autonomy == "ask":
        resume_from_gate(d, "u1", rid, "plan")
        resume_from_gate(d, "u1", rid, "option", {"selected_option": option})
    return rid


def _run(d, rid):
    return d.store.get_doc(run_path("u1", rid))


def _findings(d, rev):
    return {f["id"]: f for f in d.store.list_docs(f"workspaces/u1/revisions/{rev}/findings")}


def _events(d, rid):
    return d.store.list_docs(f"{run_path('u1', rid)}/events")


def test_golden_path_two_revisions_and_fix_choices(p123, make_run, firestore_safe):
    rid = _to_review(p123, make_run)
    run = _run(p123, rid)
    assert (run["status"], run["gate"], run["selected_option"]) == ("at_gate", "review", "2N")
    r1, r2 = run_revisions(p123.store, "u1", rid)
    assert r1["check_summary"]["fail"] == 2 and r2["check_summary"]["fail"] == 0 and r2["parent"] == r1["id"]
    assert r1["model"] is None and r2["model_url"] == f"revisions/{r2['id']}/model.json"
    model = DesignModel.model_validate_json(p123.blobs.get(f"workspaces/u1/{r2['model_url']}"))
    assert r2["hash"] == p123.engine.model_hash(model) != r1["hash"]
    f1 = _findings(p123, r1["id"])
    assert f1["R05:FA-01"]["fix"]["candidate"] == "FA-01:cable-CBL-240-8P"
    assert f1["R05:FA-01"]["rejected_fix"]["candidate"] == "FA-01:upsize-BW-2000"
    assert f1["R11:H-Z2"]["fix"]["candidate"] == "H-Z2:local-drop"
    assert f1["R11:H-Z2"]["fix"]["criterion"].startswith("fewest changed pipe segments")
    assert "fewest pipe segments" in f1["R11:H-Z2"]["fix"]["reason"]
    assert f1["R05:FA-01"]["fix"]["deltas"]["cost_delta"] == f1["R05:FA-01"]["fix"]["cost_delta"]
    assert "cost_delta" in f1["R05:FA-01"]["rejected_fix"]["deltas"]
    revs = [e["payload"] for e in _events(p123, rid) if e["kind"] == "artifact" and e["payload"]["type"] == "revision"]
    assert {"FA-01", "H-Z2"} <= set(revs[-1]["changed"])
    art = next(e for e in _events(p123, rid) if e["kind"] == "artifact" and e["step"] == "p3.check.1")
    fails = [e for e in _events(p123, rid) if e["kind"] == "finding" and e["step"] == "p3.check.1"]
    assert len(fails) == 2 and all(e["seq"] > art["seq"] and e["payload"]["rev"] == r1["id"] for e in fails)
    assert run["metrics"]["time_to_clean_s"] > 0
    assert latest_revision(p123.store, "u1", rid)["id"] == r2["id"]
    firestore_safe(p123.store)


def test_revision_ledger_and_stub_docs(p123, make_run):
    rid = _to_review(p123, make_run)
    r2 = latest_revision(p123.store, "u1", rid)
    texts = [e["text"] for e in r2["ledger"]]
    assert "2N: TX-2500 replaced by TX-3150 (R15)" in texts
    assert "Spoken Gemini Live audio is not digit-filtered; on-screen transcripts are." in texts
    assert any(e["kind"] == "not_checked" and e["text"] == "Selectivity" for e in r2["ledger"])
    docs = load_outputs(p123.store, p123.blobs, run_path("u1", rid), "p3.docs")
    assert [f["status"] for f in docs["files"]] == ["pending", "pending"] and docs["order"][0] == "summary"
    assert docs["summary"] == "The 2N design passes every check after fixes to FA-01 and H-Z2."
    evs = _events(p123, rid)
    assert not [e for e in evs if e["kind"] == "artifact" and e["payload"]["type"] == "export"]
    assert [e["title"] for e in evs if e["step"] == "p3.docs" and e["kind"] == "status"] == \
        ["calc-report.pdf pending", "boq.csv pending"]


class FailingExporter:
    def export(self, **_):
        raise RuntimeError("blob store is unreachable")


def test_docs_export_failure_degrades_to_a_failed_status_without_failing_the_run(p123, make_run):
    p123.exporter = FailingExporter()
    rid = _to_review(p123, make_run)
    run = _run(p123, rid)
    assert (run["status"], run["gate"]) == ("at_gate", "review")
    docs = load_outputs(p123.store, p123.blobs, run_path("u1", rid), "p3.docs")
    assert [f["status"] for f in docs["files"]] == ["failed", "failed"]
    evs = _events(p123, rid)
    assert [e["title"] for e in evs if e["step"] == "p3.docs" and e["kind"] == "status"] == \
        ["calc-report.pdf failed", "boq.csv failed"]


def test_tender_refs_get_pdfplumber_boxes(deps):
    tender = yaml.safe_load((deps.scenarios_dir / "hall_a" / "tender.yaml").read_text(encoding="utf-8"))
    c = next(c for c in tender["clauses"] if c.get("quote"))
    f = Finding(id="R05:FA-01", rule_id="R05", element_id="FA-01", status="fail", title="Voltage drop",
                tender_refs=[Citation(doc_id="tender-hall-a", page=c["page"], quote=c["quote"], clause=c["id"]),
                             Citation(doc_id="tender-hall-a", page=1, quote="", clause="§2.3")])
    (out,) = with_citation_boxes([f], deps.inputs().tender_pdf)
    assert out.tender_refs[0].bbox is not None and out.tender_refs[1].bbox is None
    assert with_citation_boxes([f], deps.scenarios_dir / "missing.pdf") == [f]


def test_auto_picks_2n_by_the_resolved_clause(p123, make_run):
    rid = _to_review(p123, make_run, autonomy="auto")
    run = _run(p123, rid)
    assert (run["gate"], run["selected_option"]) == ("review", "2N")
    assert any(e["title"].startswith("Auto mode chose 2N") for e in _events(p123, rid) if e["kind"] == "ledger")


def test_auto_picks_2n_when_the_model_writes_appendix_b_first(p123, make_run):
    """P2 final fix wave, Important 2: the tender prints "App. B Appendix B: ..." on page 7, so the model may
    label the appendix "Appendix B" and list it first. The default must still come from the verified §4.2
    quote (2N), or choose_option skips the topology filter and Auto mode picks the cheaper DR."""
    import copy

    from kirchhoff.runs.fakes import FAKE_REPLIES

    reply = copy.deepcopy(FAKE_REPLIES["intake:p1.extract"])
    reply["text"]["contradictions"] = [{
        "topic": "redundancy", "clause_a": "Appendix B", "page_a": 7,
        "quote_a": "Block or distributed redundancy acceptable", "value_a": "BLOCK or DR",
        "clause_b": "Section 4.2", "page_b": 4, "quote_b": "The critical power distribution shall be 2N",
        "value_b": "2N", "summary": "Appendix B accepts block or distributed redundancy."}]
    p123.runner.replies["intake:p1.extract"] = reply
    rid = _to_review(p123, make_run, autonomy="auto")
    run = _run(p123, rid)
    (q,) = run["open_questions"]
    assert q["default_resolution"] == q["resolution"] == "2N" and "2N" in q["options"]
    assert [c["clause"] for c in q["citations"]] == ["App. B", "§4.2"]
    assert (run["gate"], run["selected_option"]) == ("review", "2N")


def test_invalid_agent_choice_falls_back_to_the_stated_criterion(p123, make_run):
    p123.runner.replies["power:p3.fix.1:R05:FA-01"] = {"text": {"candidate_id": "nope", "reason": "x"}}
    rid = _to_review(p123, make_run)
    fix = _findings(p123, run_revisions(p123.store, "u1", rid)[0]["id"])["R05:FA-01"]["fix"]
    assert fix["candidate"] == "FA-01:cable-CBL-240-8P"
    assert fix["reason"] == ("Power chose FA-01:cable-CBL-240-8P for R05:FA-01: largest voltage-drop margin per "
                             "dollar, that is the limit minus the resulting drop, divided by the cost delta.")


def test_forged_candidate_id_and_patch_from_the_agent_are_never_trusted(p123, make_run):
    """P1-R7, trust-critical: the fix loop only ever applies a candidate id found in a FRESH
    `engine.fix_candidates(...)` call for the finding on the CURRENT model. A reply carrying both an
    unknown candidate id and a forged patch (one that would, if ever honoured, zero out FA-01's voltage
    drop with an engine-made-up catalogue id) must still resolve to the engine's own preferred candidate,
    never to anything built from the LLM's output."""
    p123.runner.replies["power:p3.fix.1:R05:FA-01"] = {
        "text": {"candidate_id": "FA-01:forged-free-lunch",
                  "reason": "x", "patch": {"connection": "FA-01", "catalogue_id": "MADE-UP-WIRE", "dv_pct": 0.0}}}
    rid = _to_review(p123, make_run)
    r1 = run_revisions(p123.store, "u1", rid)[0]
    fix = _findings(p123, r1["id"])["R05:FA-01"]["fix"]
    assert fix["candidate"] == "FA-01:cable-CBL-240-8P"  # the engine's own `preferred_candidate` fallback
    # Fix round 1, Important 1(a): assert the EXACT fallback-template reason too, which only ever fires
    # when the forged reply was actually delivered to `_fix` and then rejected by the id lookup -- a test
    # where the reply never arrived (or was swallowed by `agent_json`'s `except Exception -> None`) would
    # produce this exact same candidate (it's also the deterministic R23 fallback) but a DIFFERENT reason
    # (the plain template fires only when `reply is not None` but its id didn't match).
    assert fix["reason"] == ("Power chose FA-01:cable-CBL-240-8P for R05:FA-01: largest voltage-drop margin "
                             "per dollar, that is the limit minus the resulting drop, divided by the cost "
                             "delta.")
    r2 = latest_revision(p123.store, "u1", rid)
    model = DesignModel.model_validate_json(p123.blobs.get(f"workspaces/u1/{r2['model_url']}"))
    fa = next(c for c in model.connections if c.id == "FA-01")
    assert fa.catalogue_id == "CBL-240-8P"  # the real engine candidate's own patch, not the forged one


def test_matched_real_candidate_id_ignores_a_forged_patch_in_the_same_reply(p123, make_run):
    """Fix round 1, Important 1(b): the matched-id path (where a patch-merge regression would actually
    live) was never exercised by the forged-UNKNOWN-id test above. Here the agent legitimately picks a
    REAL, non-preferred candidate id (`FA-01:upsize-BW-2000`, not the R23-preferred cable) alongside a
    forged `patch` in the very same reply. The id match must be honoured (it's a real engine candidate),
    but the forged patch must never be read: applying a fix always means
    `engine.apply_fix(model, <the matched engine FixCandidate>)`, so the model ends up with that
    candidate's own catalogue id (BW-2000), never the forged one (MADE-UP-WIRE)."""
    p123.runner.replies["power:p3.fix.1:R05:FA-01"] = {
        "text": {"candidate_id": "FA-01:upsize-BW-2000", "reason": "x",
                 "patch": {"connection": "FA-01", "catalogue_id": "MADE-UP-WIRE", "dv_pct": 0.0}}}
    rid = _to_review(p123, make_run)
    r1 = run_revisions(p123.store, "u1", rid)[0]
    fix = _findings(p123, r1["id"])["R05:FA-01"]["fix"]
    assert fix["candidate"] == "FA-01:upsize-BW-2000"  # the agent's matched (real) id, honoured
    r2 = latest_revision(p123.store, "u1", rid)
    model = DesignModel.model_validate_json(p123.blobs.get(f"workspaces/u1/{r2['model_url']}"))
    fa = next(c for c in model.connections if c.id == "FA-01")
    assert fa.catalogue_id == "BW-2000"  # the matched candidate's own patch, not the forged one


class NoFixEngine(FakeEngine):
    def apply_fix(self, model, candidate):
        self._log("apply_fix")
        return model


def test_fix_loop_exhaustion_stops_at_review_with_open_findings(p123, make_run):
    p123.engine = NoFixEngine()
    rid = _to_review(p123, make_run)
    revs = run_revisions(p123.store, "u1", rid)
    assert len(revs) == 3 and revs[-1]["check_summary"]["fail"] == 2
    stop_text = "Fix loop stopped after 2 iterations; open findings: R05:FA-01, R11:H-Z2. Approval is disabled."
    ledger = [e["title"] for e in _events(p123, rid) if e["kind"] == "ledger"]
    assert stop_text in ledger
    # spec §6.1: the open findings are listed, both as the ledger's run-level event and as findings
    # actually re-emitted on the last check step, naming the final revision.
    fails = [e for e in _events(p123, rid) if e["kind"] == "finding" and e["step"] == "p3.check.3"]
    assert {e["payload"]["finding_id"] for e in fails} == {"R05:FA-01", "R11:H-Z2"}
    assert all(e["payload"]["rev"] == revs[-1]["id"] for e in fails)
    assert _run(p123, rid)["gate"] == "review"
    # Fix round 1, Minor: the stop ledger entry must also land in the sign-off ledger of the final
    # revision itself (not just as a run-level event), since the ledger IS the audit trail (R16).
    assert stop_text in [e["text"] for e in revs[-1]["ledger"]]


class NoCandidateEngine(FakeEngine):
    """Every rule returns no fix candidate at all, even for a currently-failing finding -- distinct from
    `fix_candidates`'s normal `[]` once a finding has already passed (P2-R3b)."""
    def fix_candidates(self, scn, model, finding, erp):
        self._log("fix_candidates")
        return []


def test_fix_loop_stops_immediately_when_no_engine_candidate_clears_a_finding(p123, make_run):
    """Fix round 1, Important 3: when no failing finding has ANY engine candidate, the loop must break
    after the first fix attempt (never claiming an iteration count it didn't run), write accurate "no
    candidate" ledger text (not the exhaustion message, which would be false here), and still park the run
    at the review gate with the open findings intact."""
    p123.engine = NoCandidateEngine()
    rid = _to_review(p123, make_run)
    revs = run_revisions(p123.store, "u1", rid)
    assert len(revs) == 1 and revs[0]["check_summary"]["fail"] == 2  # one fix-free revision, nothing applied
    assert _run(p123, rid)["gate"] == "review"
    evs = _events(p123, rid)
    status_titles = {e["title"] for e in evs if e["kind"] == "status" and e["step"] == "p3.fix.1"}
    assert status_titles == {"No engine candidate clears R05:FA-01", "No engine candidate clears R11:H-Z2"}
    stop_text = ("No engine candidate clears the remaining open findings; fix loop stopped after 1 "
                "iteration(s); open findings: R05:FA-01, R11:H-Z2. Approval is disabled.")
    ledger = [e["title"] for e in evs if e["kind"] == "ledger"]
    assert stop_text in ledger
    assert not any(t.startswith("Fix loop stopped after 2 iterations") for t in ledger)  # would be false here
    assert stop_text in [e["text"] for e in revs[-1]["ledger"]]


class NoSwapEngine(FakeEngine):
    def annotate_options(self, scn, options, erp):
        self._log("annotate_options")
        return list(options)  # TX-2500 stays: 98 weeks breaks §2.3 for every option


def test_auto_parks_at_the_option_gate_when_no_option_qualifies(p123, make_run):
    p123.engine = NoSwapEngine()
    rid = make_run(autonomy="auto")
    start_phase(p123, "u1", rid, "p1")
    assert (_run(p123, rid)["status"], _run(p123, rid)["gate"]) == ("at_gate", "option")
    resume_from_gate(p123, "u1", rid, "option", {"selected_option": "2N"})
    assert _run(p123, rid)["gate"] == "review"
