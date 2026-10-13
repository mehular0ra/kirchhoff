import pytest

from kirchhoff.contracts import PRLine
from kirchhoff.enterprise.model import FICTIONAL_NOTICE, fallback_seed, seed_hash
from kirchhoff.enterprise.sandbox import NotFound

LINES = [PRLine(material_id="TX-3150", description="TX-3150 item", qty=6, unit_price=100.0, lead_time_weeks=12)]


def test_seed_loads_and_lists_sorted(sandbox, small_seed):
    assert [m.id for m in sandbox.list_materials()] == ["BW-1600", "TX-2500", "TX-3150"]
    assert [p.id for p in sandbox.list_prs(None)] == ["PR-2026-0142"]
    assert [o.id for o in sandbox.list_opportunities(None)] == ["opp-hall-a", "opp-hall-b"]
    meta = sandbox.meta()
    assert meta["hash"] == seed_hash(small_seed) and meta["materials"] == 3 and meta["notice"] == FICTIONAL_NOTICE


def test_reloading_the_seed_replaces_stale_documents(sandbox, small_seed):
    smaller = small_seed.model_copy(update={"materials": small_seed.materials[:1]})
    assert sandbox.load_seed(smaller) == {"materials": 1, "prs": 1, "opportunities": 2}
    assert [m.id for m in sandbox.list_materials()] == ["TX-3150"]


def test_create_pr_is_idempotent_and_numbered_from_0301(sandbox):
    a = sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="x:x-r2:Tapti Transformers")
    b = sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="x:x-r2:Tapti Transformers")
    c = sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="x:x-r2:Indus Busbar Systems")
    assert a == b and a.id == "PR-2026-0301" and a.status == "submitted"
    assert c.id == "PR-2026-0302"


def test_idempotency_keys_are_scoped_per_visitor(sandbox):
    a = sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="k")
    b = sandbox.create_pr("u2", "hall-b", "y-r2", LINES, idempotency_key="k")
    assert a.id != b.id
    assert [p.id for p in sandbox.list_prs("u1") if p.project_id == "hall-b"] == [a.id]


def test_list_prs_merges_seed_and_visitor_newest_first(sandbox):
    mine = sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="k")
    assert [p.id for p in sandbox.list_prs("u1")] == [mine.id, "PR-2026-0142"]
    assert [p.id for p in sandbox.list_prs("u2")] == ["PR-2026-0142"]


def test_set_pr_status(sandbox):
    pr = sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="k")
    sandbox.set_pr_status("u1", pr.id, "blocked")
    assert next(p for p in sandbox.list_prs("u1") if p.id == pr.id).status == "blocked"
    with pytest.raises(NotFound):
        sandbox.set_pr_status("u2", pr.id, "blocked")
    with pytest.raises(ValueError):
        sandbox.set_pr_status("u1", pr.id, "cancelled")


def test_crm_overlay_is_per_visitor(sandbox):
    ov = sandbox.set_opportunity_stage("u1", "opp-hall-b", "Design approved")
    assert ov.opportunity_id == "opp-hall-b" and ov.stage == "Design approved"

    def stage(uid):
        return next(o.stage for o in sandbox.list_opportunities(uid) if o.id == "opp-hall-b")

    assert stage("u1") == "Design approved" and stage("u2") == "Design in progress"
    with pytest.raises(NotFound):
        sandbox.set_opportunity_stage("u1", "opp-nope", "Design approved")
    with pytest.raises(ValueError):
        sandbox.set_opportunity_stage("u1", "opp-hall-b", "Shipped")


def test_reset_clears_only_that_visitor_and_never_reuses_numbers(sandbox):
    a = sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="k")
    sandbox.create_pr("u2", "hall-b", "y-r2", LINES, idempotency_key="k")
    sandbox.set_opportunity_stage("u1", "opp-hall-b", "Design approved")
    assert sandbox.reset_visitor("u1") >= 3
    assert [p.id for p in sandbox.list_prs("u1")] == ["PR-2026-0142"]
    assert next(o.stage for o in sandbox.list_opportunities("u1") if o.id == "opp-hall-b") == "Design in progress"
    assert len(sandbox.list_prs("u2")) == 2
    assert sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="k").id != a.id


def test_stock_is_never_decremented(sandbox):
    before = {m.id: m.stock for m in sandbox.list_materials()}
    sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="k")
    assert {m.id: m.stock for m in sandbox.list_materials()} == before


def test_bad_inputs_are_rejected(sandbox):
    for uid in ("", "a/b"):
        with pytest.raises(ValueError):
            sandbox.create_pr(uid, "hall-b", "x-r2", LINES, idempotency_key="k")
    with pytest.raises(ValueError):
        sandbox.create_pr("u1", "hall-b", "x-r2", [], idempotency_key="k")
    with pytest.raises(ValueError):
        sandbox.create_pr("u1", "hall-b", "x-r2", LINES, idempotency_key="")


def test_fallback_seed_from_erp_yaml(tmp_path):
    p = tmp_path / "erp_seed.yaml"
    p.write_text("materials:\n  - {id: TX-3150, category: transformer, description: t, rating: 3150, unit: kVA, "
                 "voltage: '33/0.415 kV', stock: 6, lead_time_weeks: 12, unit_price: 1.0, vendor: v}\n",
                 encoding="utf-8")
    seed = fallback_seed(p)
    assert [m.id for m in seed.materials] == ["TX-3150"]
    assert {o.id for o in seed.opportunities} == {"opp-hall-a", "opp-hall-b"}
    assert fallback_seed(tmp_path / "missing.yaml").materials == []
