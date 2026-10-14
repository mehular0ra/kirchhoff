"""Follow-up hardening (2026-10-13, ruling P1-R7): forged-fix guards closing the two Important
residuals from the re-review, plus the cheap Minors. See
.superpowers/sdd/2026-10-13-p1-engine/followup-brief.md."""
import copy
import threading
import time
from dataclasses import replace

import pytest

from kirchhoff.contracts.extra import FixCandidate
from kirchhoff.engine import api


def _finding(scn, erp, model, fid):
    return next(f for f in api.check(scn, model, erp) if f.id == fid)


# ------------------------------------------------------------- Important 1 ----

def test_apply_fix_set_feeder_rejects_non_busway_cable_kind(scn, erp, routed):
    m = routed["2N"]
    for bad_kind in ("internal", "teleport"):
        bad = FixCandidate(id="x", finding_id="R05:FA-01", label="x", cost_delta=0, metrics={},
                           patch={"op": "set_feeder", "feeder": "FA-01", "kind": bad_kind,
                                  "catalogue_id": "BW-2000"})
        with pytest.raises(ValueError):
            api.apply_fix(m, bad)


def test_apply_fix_set_feeder_rejects_non_feeder_target(scn, erp, routed):
    """A forged patch naming an 'internal' connection (never a feeder, dst is never a busway) as the
    'feeder' must be rejected even if the requested new kind is legitimate."""
    m = routed["2N"]
    internal_id = next(c.id for c in m.connections if c.kind == "internal")
    bad = FixCandidate(id="x", finding_id="R05:FA-01", label="x", cost_delta=0, metrics={},
                       patch={"op": "set_feeder", "feeder": internal_id, "kind": "busway",
                              "catalogue_id": "BW-2000"})
    with pytest.raises(ValueError):
        api.apply_fix(m, bad)


def test_forged_set_feeder_kind_cannot_hide_findings_via_validate_model(scn, erp, routed):
    """Forging FA-01's connection kind directly (bypassing apply_fix entirely) must still be caught the
    moment the model reaches any facade entry point, so R02/R03/R05:FA-01 can never silently disappear."""
    m = routed["2N"]
    for bad_kind in ("internal", "teleport"):
        forged = m.model_copy(update={"connections": [
            c.model_copy(update={"kind": bad_kind}) if c.id == "FA-01" else c for c in m.connections]})
        with pytest.raises(ValueError):
            api.check(scn, forged, erp)


def test_validate_model_rejects_connection_into_busway_with_bad_kind(scn, erp, routed):
    m = routed["2N"]
    forged = m.model_copy(update={"connections": [
        c.model_copy(update={"kind": "internal"}) if c.id == "FA-01" else c for c in m.connections]})
    with pytest.raises(ValueError):
        api.validate_model(scn, forged)


def test_validate_model_accepts_every_engine_produced_model(scn, annotated, routed):
    for _topo, model in routed.items():
        api.validate_model(scn, model)
    for _topo, (_opt, model) in annotated.items():
        api.validate_model(scn, model)


# ------------------------------------------------------------- Important 2 ----

def test_validate_model_rejects_joint_stub_that_strands_a_sibling_branch(scn, erp, routed):
    """Cutting H-Z2 to a short riser and moving BR-R3's take-off with it (a consistent joint, so apply_fix
    lets it through) must still be caught: BR-R4's take-off, left untouched, no longer lands on H-Z2's
    (now much shorter) polyline."""
    m = routed["2N"]
    stub = FixCandidate(id="x", finding_id="R11:H-Z2", label="x", cost_delta=0, metrics={},
                        patch={"op": "set_pipe_routes",
                               "routes": {"H-Z2": [[31.0, 30.5, 1.2], [31.0, 30.5, 2.6]],
                                         "BR-R3": [[31.0, 30.5, 2.6], [28.0, 21.0, 2.6], [28.0, 15.6, 2.6]]}})
    forged = api.apply_fix(m, stub)  # apply_fix itself accepts: it's a consistent joint
    with pytest.raises(ValueError):
        api.validate_model(scn, forged)
    with pytest.raises(ValueError):
        api.check(scn, forged, erp)


def test_validate_model_accepts_every_branch_pipe_on_golden_and_fixed_models(scn, erp, annotated, routed):
    from kirchhoff.engine.benchmark import golden_fixed

    for _topo, model in routed.items():
        api.validate_model(scn, model)
    for topo in ("2N", "DR", "BLOCK"):
        fixed = golden_fixed(scn, erp, topology=topo)
        api.validate_model(scn, fixed)


def test_validate_model_accepts_every_fix_candidate_applied(scn, erp, routed):
    m = routed["2N"]
    base = {f.id for f in api.check(scn, m, erp) if f.status == "fail"}
    for fid in sorted(base):
        finding = _finding(scn, erp, m, fid)
        for cand in api.fix_candidates(scn, m, finding, erp):
            after = api.apply_fix(m, cand)
            api.validate_model(scn, after)


def test_validate_model_accepts_every_what_if_shadow(scn, erp):
    from kirchhoff.engine.benchmark import golden_fixed

    fixed = golden_fixed(scn, erp)
    for param, value in api.CHIP_WHAT_IFS:
        res = api.what_if(scn, fixed, param, value, "x", erp)
        assert res is not None  # what_if validates the frozen base model internally; no raise means pass


# ------------------------------------------------------------- Minor 3 -------

def test_shortcircuit_and_grid_share_one_warnings_lock():
    from kirchhoff.engine import grid, shortcircuit

    assert shortcircuit._LOCK is grid._LOCK


# ------------------------------------------------------------- Minor 4 -------

def test_sc_cache_lookup_move_to_end_and_read_are_lock_guarded(scn, racks, monkeypatch):
    """Deterministic repro of the reviewer's race: widen the window between the 'key in _CACHE' check and
    the subsequent move_to_end/read with an instrumented dict, and have a concurrent writer evict that exact
    key while the window is open. Pre-fix this raises KeyError; once the lookup, move_to_end and read all
    happen under the same lock as the writer's eviction, the window can never overlap a write."""
    from collections import OrderedDict

    from kirchhoff.engine import shortcircuit
    from kirchhoff.engine.shortcircuit import short_circuit
    from kirchhoff.engine.topology import build_model

    class GapDict(OrderedDict):
        def __contains__(self, key):
            result = super().__contains__(key)
            if result:
                gap.set()  # let the writer proceed to evict this exact key
                time.sleep(0.2)
            return result

    monkeypatch.setattr(shortcircuit, "_CACHE_MAX", 1)
    gap_cache = GapDict()
    monkeypatch.setattr(shortcircuit, "_CACHE", gap_cache)
    m = build_model(scn, racks, "2N", "TX-3150")
    short_circuit(scn, m)  # primes gap_cache with the target key (cache was empty, at capacity 1)

    gap = threading.Event()
    errors: list[BaseException] = []

    def reader() -> None:
        try:
            short_circuit(scn, m)  # hits the primed key, opening the race window via GapDict.__contains__
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    def evictor() -> None:
        gap.wait(timeout=5.0)
        cat = copy.deepcopy(scn.catalogue)
        for t in cat["transformers"]:
            if t["id"] == "TX-3150":
                t["p0_kw"] = 999.0
        scn_other = replace(scn, name="v-other", catalogue=cat)
        try:
            short_circuit(scn_other, m)  # a different key: at _CACHE_MAX=1, this evicts the primed key
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    t_reader, t_evictor = threading.Thread(target=reader), threading.Thread(target=evictor)
    t_reader.start()
    t_evictor.start()
    t_reader.join()
    t_evictor.join()
    assert errors == []


# ------------------------------------------------------------- Minor 5 -------

def test_warm_up_primes_the_post_r15_swap_seed_model(scn, erp, racks):
    """warm_up must compute the short-circuit result for the 2N model AFTER the R15 swap (the 3.15 MVA
    seed revision), not the raw 2.5 MVA pre-swap model: only the post-swap key is what the first real
    what-if/chip_what_ifs call on the seed revision will look up."""
    from kirchhoff.engine.options import annotate_options, power_options
    from kirchhoff.engine.shortcircuit import _CACHE, _key, short_circuit

    annotated = annotate_options(scn, power_options(scn, racks), erp)
    seed_model = next(m for o, m in annotated if o.id == "2N")
    seed_key = _key(scn, seed_model)

    _CACHE.clear()
    api._WARMED_UP = False
    api.warm_up()
    assert seed_key in _CACHE, "warm_up did not pre-cache the post-R15-swap 2N (3.15 MVA) seed model"


# ------------------------------------------------------------- Minor 6 -------

def test_no_mv_and_no_mv_links_raises_valueerror(scn, erp, routed):
    m = routed["2N"]
    stripped = m.model_copy(update={
        "equipment": [e for e in m.equipment if e.id != "MV"],
        "connections": [c for c in m.connections if c.src != "MV" and c.dst != "MV"]})
    with pytest.raises(ValueError):
        api.check(scn, stripped, erp)


def test_unknown_pipe_dn_raises_valueerror(scn, erp, routed):
    m = routed["2N"]
    bad = m.model_copy(update={"pipes": [p.model_copy(update={"dn": 9999}) if p.id == "H-Z1" else p
                                         for p in m.pipes]})
    with pytest.raises(ValueError):
        api.check(scn, bad, erp)


def test_set_feeder_patch_without_kind_raises_valueerror(scn, erp, routed):
    m = routed["2N"]
    bad = FixCandidate(id="x", finding_id="R05:FA-01", label="x", cost_delta=0, metrics={},
                       patch={"op": "set_feeder", "feeder": "FA-01", "catalogue_id": "BW-2000"})
    with pytest.raises(ValueError):
        api.apply_fix(m, bad)


def test_set_feeder_patch_with_none_catalogue_id_raises_valueerror(scn, erp, routed):
    m = routed["2N"]
    bad = FixCandidate(id="x", finding_id="R05:FA-01", label="x", cost_delta=0, metrics={},
                       patch={"op": "set_feeder", "feeder": "FA-01", "kind": "busway", "catalogue_id": None})
    with pytest.raises(ValueError):
        api.apply_fix(m, bad)


def test_set_pipe_routes_patch_with_non_dict_routes_raises_valueerror(scn, erp, routed):
    m = routed["2N"]
    bad = FixCandidate(id="x", finding_id="R11:H-Z2", label="x", cost_delta=0, metrics={},
                       patch={"op": "set_pipe_routes", "routes": ["H-Z2", [[31.0, 30.5, 1.2]]]})
    with pytest.raises(ValueError):
        api.apply_fix(m, bad)
