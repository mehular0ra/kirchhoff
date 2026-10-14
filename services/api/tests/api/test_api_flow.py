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
    # Task 10's documented deviation from the brief (test_runs_orchestrator.py): next_seq gaps by
    # SEQ_GAP on every attempt increase, clean gate resume or not, so seqs are strictly increasing
    # across a gate resume but not contiguous (they stay contiguous within one attempt/phase).
    seqs = [e["seq"] for e in events]
    assert seqs[0] == 1 and all(b > a for a, b in zip(seqs, seqs[1:]))
    assert any(e["kind"] == "ledger" and e["title"].startswith("Approval ") for e in events)
    firestore_safe(deps.store)


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


class NoFixEngine(FakeEngine):
    def apply_fix(self, model, candidate):
        return model


def test_approve_is_blocked_while_findings_are_open(client, deps, auth):
    deps.engine = NoFixEngine()
    rid = _ask_to_review(client, auth)
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
