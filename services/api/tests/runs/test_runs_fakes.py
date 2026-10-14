import ast
import inspect

from kirchhoff.agents.ports import ErpSnapshot
from kirchhoff.contracts import PRLine
from kirchhoff.runs.compat import ClashReport, FixCandidate
from kirchhoff.runs.fakes import FAKE_MATERIALS, FakeEngine, FakeEnterprise


def _golden_model(eng):
    scn = eng.load_scenario("hall_a", None)
    erp = ErpSnapshot(FAKE_MATERIALS)
    racks = eng.place_racks(scn)
    opts = eng.annotate_options(scn, eng.power_options(scn, racks), erp)
    opt, model = next((o, m) for o, m in opts if o.id == "2N")
    return scn, erp, opt, eng.route(scn, model)


def test_golden_first_pass_fails_exactly_r05_and_r11_then_fixes_clear_them():
    eng = FakeEngine()
    scn, erp, opt, model = _golden_model(eng)
    assert opt.swaps[0]["to"] == "TX-3150" and opt.max_lead_time_weeks <= 26
    fails = sorted(f.id for f in eng.check(scn, model, erp) if f.status == "fail")
    assert fails == ["R05:FA-01", "R11:H-Z2"]
    r11 = next(f for f in eng.check(scn, model, erp) if f.id == "R11:H-Z2")
    assert r11.inputs["above"] == "FB-03"
    for f in [f for f in eng.check(scn, model, erp) if f.status == "fail"]:
        cands = eng.fix_candidates(scn, model, f, erp)
        assert len(cands) == 2 and all(isinstance(c, FixCandidate) for c in cands)
        model = eng.apply_fix(model, cands[0])
    assert all(f.status != "fail" for f in eng.check(scn, model, erp))
    assert isinstance(eng.detect_clashes(model), ClashReport)


def test_what_if_200kw_fails_r01_r02_r08():
    eng = FakeEngine()
    scn, erp, _, model = _golden_model(eng)
    res = eng.what_if(scn, model, "rack_kw", 200.0, "ws:x-r2", erp)
    assert {"R01", "R02", "R08"} <= {f.rule_id for f in res.findings if f.status == "fail"}
    assert all(f.status in ("fail", "warn") for f in res.findings) and res.impact_chain
    assert [f.rule_id for f in eng.power_recheck(scn, model)] == ["R01", "R04", "R04b"]


def test_model_hash_is_stable_and_sensitive():
    eng = FakeEngine()
    _, _, _, model = _golden_model(eng)
    assert eng.model_hash(model) == eng.model_hash(model.model_copy(deep=True))
    assert eng.model_hash(model) != eng.model_hash(model.model_copy(update={"loads": {"rack_kw": 1.0}}))


def test_r12_compares_submitted_pr_lines():
    eng = FakeEngine()
    scn, erp, _, model = _golden_model(eng)
    lines = eng.derive_pr_lines(scn, model, erp)
    ok = next(f for f in eng.check(scn, model, erp, pr_lines=lines) if f.rule_id == "R12")
    short = lines[:-1] + [PRLine(**{**lines[-1].model_dump(), "qty": lines[-1].qty - 1})]
    bad = next(f for f in eng.check(scn, model, erp, pr_lines=short) if f.rule_id == "R12")
    assert ok.status == "pass" and bad.status == "fail"


def test_fake_enterprise_idempotency_and_reset():
    ent = FakeEnterprise()
    lines = [PRLine(material_id="TX-3150", description="t", qty=1, unit_price=1.0, lead_time_weeks=12)]
    a = ent.create_pr("u1", "hall-b", "x-r2", lines, idempotency_key="k1")
    b = ent.create_pr("u1", "hall-b", "x-r2", lines, idempotency_key="k1")
    assert a.id == b.id and a.status == "submitted"
    ent.set_pr_status("u1", a.id, "blocked")
    assert ent.prs[("u1", a.id)].status == "blocked"
    assert ent.set_opportunity_stage("u1", "opp-hall-b", "Design approved").stage == "Design approved"
    ent.reset_visitor("u1")
    assert not ent.prs and not ent.stages


def test_erp_snapshot():
    erp = ErpSnapshot(FAKE_MATERIALS)
    assert erp.get("TX-2500").lead_time_weeks == 98
    assert [m.id for m in erp.search("transformer")] == ["TX-2500", "TX-3150"]


def test_fake_engine_matches_real_engine_facade():
    """Drift guard (Task 7): every public facade function kirchhoff.engine.api defines itself, or
    deliberately re-exports (marked `# noqa: F401`), must have a same-named method on FakeEngine, so the
    fake can never silently fall behind the real engine. Plain classes/Protocols (Scenario, ErpView,
    YamlErp, FixCandidate, ClashReport) and incidental, non-re-exported names (e.g. `run_rules`, used only
    internally by `check`) are excluded."""
    from kirchhoff.engine import api as real_api

    source = inspect.getsource(real_api)
    lines = source.splitlines()
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            names.add(node.name)
        elif isinstance(node, ast.ImportFrom) and "noqa: F401" in lines[node.lineno - 1]:
            names.update(alias.asname or alias.name for alias in node.names)
    facade_names = sorted(n for n in names if inspect.isfunction(getattr(real_api, n, None)))
    assert facade_names, "expected at least one facade function on kirchhoff.engine.api"
    eng = FakeEngine()
    missing = [name for name in facade_names if not callable(getattr(eng, name, None))]
    assert missing == [], f"FakeEngine is missing facade methods: {missing}"
