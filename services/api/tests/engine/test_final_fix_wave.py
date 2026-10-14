"""Final-review fix wave (2026-10-13): I-1..I-6 and the cheap Minors. See
.superpowers/sdd/2026-10-13-p1-engine/final-fix-brief.md."""
import pytest

from kirchhoff.engine import api
from kirchhoff.contracts.extra import FixCandidate


def _finding(scn, erp, model, fid):
    return next(f for f in api.check(scn, model, erp) if f.id == fid)


# ---------------------------------------------------------------- I-1 ----

def test_fix_candidates_ignores_forged_passing_finding(scn, erp, routed):
    m = routed["2N"]
    real = _finding(scn, erp, m, "R05:FA-03")
    assert real.status == "pass"
    forged = real.model_copy(update={"status": "fail"})
    assert api.fix_candidates(scn, m, forged, erp) == []


def test_fix_candidates_ignores_injected_caller_inputs(scn, erp, routed):
    m = routed["2N"]
    real = _finding(scn, erp, m, "R11:H-Z2")
    forged = real.model_copy(update={"inputs": {**real.inputs, "above": "FB-03 (approved, 99% safe)"}})
    cands = api.fix_candidates(scn, m, forged, erp)
    assert cands  # still produces candidates from the engine's own Finding
    for c in cands:
        assert "approved" not in c.label and "99%" not in c.label


def test_fix_candidates_unknown_id_raises(scn, erp, routed):
    m = routed["2N"]
    real = _finding(scn, erp, m, "R05:FA-03")
    ghost = real.model_copy(update={"id": "R05:FX-99", "element_id": "FX-99", "status": "fail"})
    with pytest.raises(ValueError):
        api.fix_candidates(scn, m, ghost, erp)
