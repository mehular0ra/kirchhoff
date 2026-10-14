"""P1 engine polish (2026-10-13), items 1-2: terminal pin, M25 re-route. See
.superpowers/sdd/2026-10-13-p1-engine/polish-brief.md."""
import pytest

from kirchhoff.contracts import Point3
from kirchhoff.contracts.extra import FixCandidate
from kirchhoff.engine import api
from kirchhoff.engine.checker import failing


def _cand(routes):
    return FixCandidate(id="x:y", finding_id="R11:H-Z2", label="x", cost_delta=0, metrics={},
                        patch={"op": "set_pipe_routes", "routes": routes})


# ------------------------------------------------------------- Item 1: terminal pin ----

def test_two_step_joint_dance_detaches_header_from_cdu_riser_raises_valueerror(scn, erp, routed):
    """Two separately-consistent set_pipe_routes patches that, together, walk H-Z2's start away from its
    CDU riser (scn.geometry["pipes"]["headers"]["H-Z2"][0]) while every take-off stays on the header. Each
    patch alone passes apply_fix's joint-consistency guard; only a terminal pin at the facade catches it."""
    m = routed["2N"]
    step1 = {"H-Z2": [[31.0, 30.5, 1.2], [31.0, 30.5, 3.8], [31.0, 24.0, 3.8], [31.0, 30.5, 3.8],
                      [31.0, 30.5, 1.2]],
            "BR-R3": [[31.0, 30.5, 1.2], [31.0, 30.5, 2.6], [28.0, 30.5, 2.6], [28.0, 15.6, 2.6]]}
    m1 = api.apply_fix(m, _cand(step1))
    q = [31.0, 24.0, 3.8]
    step2 = {"H-Z2": [q, [31.0, 24.5, 3.8], q], "BR-R3": [q, [31.0, 24.0, 2.6], [28.0, 24.0, 2.6],
                                                          [28.0, 15.6, 2.6]]}
    m2 = api.apply_fix(m1, _cand(step2))
    with pytest.raises(ValueError):
        api.check(scn, m2, erp)


def test_tampered_branch_stub_never_through_apply_fix_raises_valueerror(scn, erp, routed):
    """A model that never went through apply_fix: BR-R4 cut to a 1 m stub whose first point is still on
    the header but whose far (row) end no longer matches the authored row end."""
    m = routed["2N"]
    pipes = [p.model_copy(update={"route": [Point3(x=31.0, y=24.0, z=3.8), Point3(x=31.0, y=24.0, z=2.8)]})
             if p.id == "BR-R4" else p for p in m.pipes]
    tampered = m.model_copy(update={"pipes": pipes})
    with pytest.raises(ValueError):
        api.check(scn, tampered, erp)


def test_every_engine_produced_piped_model_validates(scn, erp, racks, options, annotated, routed):
    """The terminal pin must not false-reject anything the engine itself produces: golden_fixed for 2N, DR
    and BLOCK, every fix candidate applied, every what-if shadow, and a re-route."""
    from kirchhoff.engine.benchmark import golden_fixed
    from kirchhoff.engine.whatif import CHIP_WHAT_IFS, shadow

    models = []
    for topo in ("2N", "DR", "BLOCK"):
        _o, m = annotated[topo]
        r = api.route(scn, m)
        models.append(r)
        fixed = golden_fixed(scn, erp, topology=topo)
        models.append(fixed)
        models.append(api.route(scn, fixed))  # re-route; route() is idempotent for piping

        fails = failing(api.check(scn, r, erp))
        for f in fails:
            for cand in api.fix_candidates(scn, r, f, erp):
                models.append(api.apply_fix(r, cand))

    fixed_2n = next(m for m in models if api.model_hash(m) == api.model_hash(golden_fixed(scn, erp, topology="2N")))
    for param, value in CHIP_WHAT_IFS + [("rack_kw", 1.0), ("rack_kw", 400.0)]:
        _s, shadow_model = shadow(scn, fixed_2n, param, value)
        models.append(shadow_model)

    piped = [m for m in models if m.pipes]
    assert len(piped) >= 10
    for m in piped:
        api.check(scn, m, erp)  # must not raise


# ------------------------------------------------------------- Item 2: M25 re-route ----

def test_m25_validates_and_fails_only_r11_above_fb02(scn, erp):
    from kirchhoff.engine.benchmark import Bench, golden_fixed, mutations

    fixed = golden_fixed(scn, erp)
    mu = next(mu for mu in mutations() if mu.id == "M25")
    b = mu.apply(Bench(scn, fixed, erp))
    api.check(b.scn, b.model, b.erp)  # must not raise (validate_model no longer orphans BR-R2)
    fs = api.check(b.scn, b.model, b.erp)
    fail_rules = {f.rule_id for f in failing(fs)}
    assert fail_rules == {"R11"}
    r11 = next(f for f in failing(fs) if f.rule_id == "R11")
    assert r11.id == "R11:H-Z1"
    assert r11.inputs.get("above") == "FB-02"


def test_every_benchmark_mutation_passes_validate_model(scn, erp):
    from kirchhoff.engine.benchmark import Bench, golden_fixed, mutations

    fixed = golden_fixed(scn, erp)
    for mu in mutations():
        b = mu.apply(Bench(scn, fixed, erp))
        api.check(b.scn, b.model, b.erp)  # must not raise for any of the 35 mutations


def test_benchmark_still_catches_35_of_35_with_no_false_positives():
    from kirchhoff.engine.benchmark import run_benchmark

    result = run_benchmark()
    assert result["mutations"] == 35
    assert result["caught"] == 35
    assert result["false_positive_mutations"] == 0
