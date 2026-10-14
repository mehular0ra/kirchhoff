from collections import defaultdict

from kirchhoff.runs.fakes import FakeEngine, FakeEnterprise
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.revisions import latest_revision

NEW = {"project_id": "hall-b", "autonomy": "ask"}


def _run(d, rid):
    return d.store.get_doc(run_path("u1", rid))


def _ask_to_review(client, auth) -> str:
    rid = client.post("/api/runs", json=NEW, headers=auth).json()["run_id"]
    assert client.post(f"/api/runs/{rid}/gates/plan", json={"answers": {"Q-redundancy": "2N"}},
                       headers=auth).status_code == 202
    assert client.post(f"/api/runs/{rid}/gates/option", json={"option_id": "2N"}, headers=auth).status_code == 202
    return rid


def _review(client, auth, rid, decision="approved"):
    return client.post(f"/api/runs/{rid}/gates/review", json={"decision": decision, "comment": "ok"}, headers=auth)


def test_full_ask_flow_signs_creates_prs_and_moves_crm(client, deps, auth, firestore_safe):
    rid = _ask_to_review(client, auth)
    assert _run(deps, rid)["gate"] == "review"
    assert _review(client, auth, rid).status_code == 202
    run = _run(deps, rid)
    assert run["status"] == "done" and run["metrics"]["p4_blocked"] == 0.0
    rev = latest_revision(deps.store, "u1", rid)
    assert rev["status"] == "signed"
    (appr,) = deps.store.list_docs("workspaces/u1/approvals")
    assert (appr["revision"], appr["approver_name"], appr["decision"]) == (rev["id"], "You (Demo Reviewer)", "approved")
    prs = deps.store.list_docs("workspaces/u1/prs")
    assert prs and all(p["status"] == "submitted" and p["revision"] == rev["id"] for p in prs)
    vendors = {deps.erp().get(line["material_id"]).vendor for p in prs for line in p["lines"]}
    assert len(prs) == len(vendors)
    assert deps.store.get_doc("workspaces/u1/crm/opp-hall-b")["stage"] == "Design approved"
    events = deps.store.list_docs(f"{run_path('u1', rid)}/events")
    steps = {s["id"]: s for s in deps.store.list_docs(f"{run_path('u1', rid)}/steps")}
    # Task 10's documented deviation from the brief (test_runs_orchestrator.py): next_seq gaps by
    # SEQ_GAP on every attempt increase, clean gate resume or not, so seqs are strictly increasing
    # across a gate resume but not contiguous (they stay contiguous within one attempt/phase). A plain
    # "seqs == range(1, n+1)" check is a tautology against MemoryStore (which always returns docs
    # sorted by their zero-padded {seq:06d} id), so assert the real invariants instead:
    # (a) the attempt number recorded on events never decreases along seq order;
    attempts = [e["attempt"] for e in events]
    assert attempts == sorted(attempts)
    # (b) within each attempt, the seqs form one contiguous range;
    by_attempt: dict[int, list[int]] = defaultdict(list)
    for e in events:
        by_attempt[e["attempt"]].append(e["seq"])
    for att, seqs in by_attempt.items():
        assert seqs == list(range(seqs[0], seqs[0] + len(seqs))), (att, seqs)
    # (c) every event's step has a step doc, and that step doc's own attempt matches the event's (the
    # UI visibility rule, R4: show an event iff steps[event.step].attempt == event.attempt);
    assert all(e["step"] in steps and steps[e["step"]]["attempt"] == e["attempt"] for e in events)
    # (d) exactly one "Approval ..." audit ledger entry, and one erp_create_pr tool_call per PR.
    approval_ledgers = [e for e in events if e["kind"] == "ledger" and e["title"].startswith("Approval ")]
    assert len(approval_ledgers) == 1
    pr_tool_calls = [e for e in events if e["kind"] == "tool_call" and e["payload"].get("tool") == "erp_create_pr"]
    assert len(pr_tool_calls) == len(prs)
    firestore_safe(deps.store)


def test_global_cap_blocks_approval_without_writing_anything(client, deps, auth):
    """Important 1: claim first, record second. A 429 at the gate must leave no approval, no signed
    revision, and the run still parked at the review gate -- not a signed revision a later Reject can
    contradict."""
    rid = _ask_to_review(client, auth)
    deps.store.set_doc("ops/live_runs", {"runs": {f"x__{i}": deps.clock() for i in range(3)}})
    r = _review(client, auth, rid)
    assert r.status_code == 429 and r.json() == {"detail": "global_cap", "offer": "replay"}
    run = _run(deps, rid)
    assert (run["status"], run["gate"]) == ("at_gate", "review")
    assert deps.store.list_docs("workspaces/u1/approvals") == []
    assert latest_revision(deps.store, "u1", rid)["status"] == "checked"


def test_double_approve_writes_exactly_one_approval(client, deps, auth):
    rid = _ask_to_review(client, auth)
    assert _review(client, auth, rid).status_code == 202
    r2 = _review(client, auth, rid)
    assert r2.status_code == 409 and r2.json() == {"detail": "wrong_state"}
    assert len(deps.store.list_docs("workspaces/u1/approvals")) == 1


def test_reject_after_a_blocked_approval_leaves_a_clean_rejected_state(client, deps, auth):
    """A 429-blocked approve followed by a reject must not leave a contradictory approved+rejected
    pair on a signed revision (the bug the reviewer's probe B found)."""
    rid = _ask_to_review(client, auth)
    deps.store.set_doc("ops/live_runs", {"runs": {f"x__{i}": deps.clock() for i in range(3)}})
    assert _review(client, auth, rid).status_code == 429
    deps.store.set_doc("ops/live_runs", {"runs": {}})
    assert _review(client, auth, rid, "rejected").status_code == 202
    run = _run(deps, rid)
    assert (run["status"], run["gate"]) == ("done", None)
    approvals = deps.store.list_docs("workspaces/u1/approvals")
    assert [a["decision"] for a in approvals] == ["rejected"]
    assert latest_revision(deps.store, "u1", rid)["status"] == "checked"


def test_auto_flow_waits_only_at_review(client, deps, auth):
    rid = client.post("/api/runs", json={"project_id": "hall-b", "autonomy": "auto"}, headers=auth).json()["run_id"]
    run = _run(deps, rid)
    assert (run["status"], run["gate"], run["selected_option"]) == ("at_gate", "review", "2N")
    assert _review(client, auth, rid).status_code == 202 and _run(deps, rid)["status"] == "done"


def test_reject_ends_the_run_without_p4(client, deps, auth):
    rid = _ask_to_review(client, auth)
    assert _review(client, auth, rid, "rejected").status_code == 202
    run = _run(deps, rid)
    assert (run["status"], run["gate"]) == ("done", None)
    assert deps.store.list_docs("workspaces/u1/prs") == []
    assert latest_revision(deps.store, "u1", rid)["status"] == "checked"
    (appr,) = deps.store.list_docs("workspaces/u1/approvals")
    assert appr["decision"] == "rejected"


class NoFixEngine(FakeEngine):
    def apply_fix(self, model, candidate):
        return model


def test_approve_is_blocked_while_findings_are_open(client, deps, auth):
    deps.engine = NoFixEngine()
    rid = _ask_to_review(client, auth)
    r = _review(client, auth, rid)
    assert r.status_code == 409 and r.json() == {"detail": "open_findings"}
    assert deps.store.list_docs("workspaces/u1/approvals") == []
    run = _run(deps, rid)
    assert (run["status"], run["gate"]) == ("at_gate", "review")
    assert latest_revision(deps.store, "u1", rid)["status"] == "checked"


def test_sign_guard_fails_closed_when_check_summary_is_empty(client, deps, auth):
    """Minor 1: an empty/missing check_summary must not fail OPEN -- count the findings docs instead."""
    deps.engine = NoFixEngine()
    rid = _ask_to_review(client, auth)
    rev = latest_revision(deps.store, "u1", rid)
    deps.store.set_doc(f"workspaces/u1/revisions/{rev['id']}", {**rev, "check_summary": {}})
    r = _review(client, auth, rid)
    assert r.status_code == 409 and r.json() == {"detail": "open_findings"}
    assert deps.store.list_docs("workspaces/u1/approvals") == []


class LossyEnterprise(FakeEnterprise):
    """The sandbox changes quantities on submission, so R12 fails on the submitted PRs."""

    def create_pr(self, uid, project_id, revision, lines, idempotency_key):
        trimmed = [line.model_copy(update={"qty": max(0, line.qty - 1)}) for line in lines]
        return super().create_pr(uid, project_id, revision, trimmed, idempotency_key)


def test_r12_failure_blocks_submitted_prs(client, deps, auth):
    deps.enterprise = LossyEnterprise()
    rid = _ask_to_review(client, auth)
    assert _review(client, auth, rid).status_code == 202
    run = _run(deps, rid)
    assert run["status"] == "done" and run["metrics"]["p4_blocked"] == 1.0
    assert all(p["status"] == "blocked" for p in deps.store.list_docs("workspaces/u1/prs"))
    assert all(p.status == "blocked" for p in deps.enterprise.prs.values())
    rev = latest_revision(deps.store, "u1", rid)
    assert rev["status"] == "signed"
    assert deps.store.get_doc(f"workspaces/u1/revisions/{rev['id']}/findings/R12:submitted-prs")["status"] == "fail"
    (ev,) = [e for e in deps.store.list_docs(f"{run_path('u1', rid)}/events") if e["kind"] == "finding"
             and e["step"] == "p4.r12_recheck"]
    assert ev["payload"]["rev"] == rev["id"]
    assert deps.store.get_doc("workspaces/u1/crm/opp-hall-b") is None


def test_review_requires_the_review_gate(client, deps, auth):
    rid = client.post("/api/runs", json=NEW, headers=auth).json()["run_id"]
    r = _review(client, auth, rid)
    assert r.status_code == 409 and r.json() == {"detail": "wrong_state"}


class FlakyEnterprise(FakeEnterprise):
    """The ERP sandbox goes down on the 2nd create_pr call; a later /resume must retry without
    duplicating any already-submitted PR (Important 3: idempotency regression)."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0
        self.stage_calls = 0

    def create_pr(self, uid, project_id, revision, lines, idempotency_key):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("ERP down")
        return super().create_pr(uid, project_id, revision, lines, idempotency_key)

    def set_opportunity_stage(self, uid, opportunity_id, stage):
        self.stage_calls += 1
        return super().set_opportunity_stage(uid, opportunity_id, stage)


def test_resume_after_an_enterprise_outage_mid_pr_creation_is_idempotent(client, deps, auth):
    ent = FlakyEnterprise()
    deps.enterprise = ent
    rid = _ask_to_review(client, auth)
    assert _review(client, auth, rid).status_code == 202
    assert _run(deps, rid)["status"] == "failed"
    assert len(ent.prs) == 1  # the one vendor call that landed before the 2nd call raised

    assert client.post(f"/api/runs/{rid}/resume", headers=auth).json() == {"resumed": True}

    run = _run(deps, rid)
    assert run["status"] == "done"
    prs = deps.store.list_docs("workspaces/u1/prs")
    assert len(prs) == len(ent.prs)  # no duplicate sandbox PRs
    assert {p["id"] for p in prs} == {pr.id for pr in ent.prs.values()}  # mirror matches the sandbox
    assert ent.stage_calls == 1
    assert len(deps.store.list_docs("workspaces/u1/approvals")) == 1
