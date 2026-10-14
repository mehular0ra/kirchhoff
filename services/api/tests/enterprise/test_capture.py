import pytest
from .ws4_fakes import RID, UID, make_hall_b_workspace

from kirchhoff.enterprise.capture import (PUNE_EDGE, CaptureError, RawCapture, export_run, render_capture_docs,
                                          to_hall_a, to_static)
from kirchhoff.enterprise.world.enterprise_data import MaterialsErp

SIGNED = 1791873600.0


@pytest.fixture
def workspace(stub_engine):
    return make_hall_b_workspace(stub_engine)


def test_export_reads_the_workspace_and_anonymises_the_uid(workspace):
    raw = export_run(*workspace, UID, RID)
    b = raw.bundle
    assert [e.seq for e in b.events] == [1, 2, 4, 5, 6, 7]  # the stale attempt is dropped (P2 R4)
    assert [r.id for r in b.revisions] == [f"{RID}-r1", f"{RID}-r2"]
    assert all(r.model is not None and r.model_url is None for r in b.revisions)
    assert b.brief.project_id == "hall-b" and raw.docs_order == ["summary", "findings", "boq"]
    text = raw.model_dump_json()
    assert UID not in text and "workspaces/visitor/" in text


def test_export_refuses_an_unfinished_run(workspace):
    store, blobs = workspace
    store.update_doc(f"workspaces/{UID}/runs/{RID}", {"status": "at_gate"})
    with pytest.raises(CaptureError, match="finished Hall B run"):
        export_run(store, blobs, UID, RID)


def test_to_hall_a_rewrites_ids_people_times_and_refs(workspace, stub_engine):
    cap = to_hall_a(export_run(*workspace, UID, RID), stub_engine, None, None, signed_at=SIGNED)
    b = cap.bundle
    assert (b.project.id, b.project.state, b.runs[0].id, b.runs[0].lease) == ("hall-a", "signed", "run-hall-a-1", None)
    assert [(r.id, r.parent, r.status) for r in b.revisions] == [("r1", None, "checked"), ("r2", "r1", "signed")]
    assert all(r.author == "Kirchhoff agents for Arjun Mehta" and r.hash == stub_engine.model_hash(r.model)
               for r in b.revisions)
    a = b.approvals[0]
    assert (a.revision, a.approver_name, a.role, a.ts) == ("r2", "Priya Raman", "Lead Electrical Engineer (Reviewer)",
                                                           SIGNED)
    assert [(p.id, p.lines[0].description) for p in b.prs] == [("PR-2026-0142", "Tapti"), ("PR-2026-0143", "Indus")]
    assert all(p.project_id == "hall-a" and p.revision == "r2" for p in b.prs)
    assert b.crm.opportunity_id == "opp-hall-a" and [e.seq for e in b.events] == [1, 2, 3, 4, 5, 6]
    # the 680 s plan-gate wait between "Brief ready" (T0+19) and "Placing racks" (T0+701) shrinks to 2 s:
    # T0+19 → T0+20 (step end, 1 s) → T0+700 (next step start, 680 s → 2 s) → T0+701 (1 s)
    assert b.events[2].ts - b.events[1].ts == 4.0
    refs = {e.payload["ref"] for e in b.events if e.kind == "artifact"}
    assert refs == {"seed/hall-a/runs/run-hall-a-1/outputs/p1.intake", "seed/hall-a/revisions/r1",
                    "/demo/files/hall-a/calc-report.pdf"}
    assert b.events[-1].title == "Priya Raman approved; PRs to ERP for Hall A"
    assert [w.revision_ref for w in b.what_ifs] == ["seed:hall-a@r2"] * 5
    dump = b.model_dump_json()
    assert all(leak not in dump for leak in ("hall-b", "Hall B", "Demo Reviewer", RID, UID))
    assert cap.docs_summary == "Hall A passes every check after the FA-01 fix."


def test_a_second_run_becomes_pune_edge(workspace, stub_engine):
    b = to_static(export_run(*workspace, UID, RID), stub_engine, None, None, target=PUNE_EDGE, signed_at=SIGNED).bundle
    assert (b.project.id, b.project.name, b.runs[0].id) == ("pune-edge-1", "Konkan Cloud · Pune Edge Phase 1",
                                                            "run-pune-edge-1")
    assert [p.id for p in b.prs] == ["PR-2026-0121", "PR-2026-0122"] and b.crm.opportunity_id == "opp-pune-edge-1"
    assert b.events[-1].title == "Priya Raman approved; PRs to ERP for Pune Edge Phase 1"
    assert {e.payload["ref"] for e in b.events if e.payload.get("type") == "export"} == {
        "/demo/files/pune-edge-1/calc-report.pdf"}
    assert [w.revision_ref for w in b.what_ifs] == ["seed:pune-edge-1@r2"] * 5
    dump = b.model_dump_json()
    assert all(leak not in dump for leak in ("hall-b", "Hall B", "Demo Reviewer", RID, UID))


def test_capture_is_deterministic(workspace, stub_engine):
    raw = export_run(*workspace, UID, RID)
    first = to_hall_a(raw, stub_engine, None, None, signed_at=SIGNED).model_dump_json()
    reloaded = RawCapture.model_validate_json(raw.model_dump_json())
    assert to_hall_a(reloaded, stub_engine, None, None, signed_at=SIGNED).model_dump_json() == first


def test_hash_drift_is_refused(workspace, stub_engine):
    raw = export_run(*workspace, UID, RID)
    raw.bundle.revisions[0].hash = "0" * 64
    with pytest.raises(CaptureError, match="R22"):
        to_hall_a(raw, stub_engine, None, None, signed_at=SIGNED)


def test_capture_documents_are_deterministic(workspace, stub_engine, small_seed):
    cap = to_hall_a(export_run(*workspace, UID, RID), stub_engine, None, None, signed_at=SIGNED)
    erp = MaterialsErp(small_seed.materials)
    docs = render_capture_docs(cap, stub_engine, None, erp)
    assert set(docs) == {"calc-report.pdf", "boq.csv"} and docs["calc-report.pdf"].startswith(b"%PDF")
    assert docs == render_capture_docs(cap, stub_engine, None, erp)
