import pytest

from kirchhoff.engine.boq import boq_cost, boq_quantities, derive_boq, derive_pr_lines
from kirchhoff.engine.checker import run_rules


def test_boq_quantities_2n(scn, models):
    q = boq_quantities(scn, models[("2N", "TX-3150")])
    assert q["TX-3150"] == 6 and q["UPS-500"] == 30 and q["CDU-1200"] == 9
    assert q["ACB-1600"] == 12 and q["ACB-5000"] == 6 and q["ACB-4000"] == 12
    assert q["LVB-415"] == 6 and q["CRB-415"] == 6 and q["MVS-33"] == 1
    assert q["BW-1600"] == pytest.approx(340.0 + 220.0 + 12 * 4.8, abs=0.01)  # FA + FB feeders + row busways


def test_derive_boq_and_cost(scn, models):
    lines = derive_boq(scn, models[("2N", "TX-3150")])
    assert [ln["material_id"] for ln in lines] == sorted(ln["material_id"] for ln in lines)
    tx = next(ln for ln in lines if ln["material_id"] == "TX-3150")
    assert tx == {"material_id": "TX-3150", "description": "Cast-resin transformer 3.15 MVA 33/0.415 kV Dyn11",
                  "qty": 6, "unit": "ea", "unit_price": 118000.0, "total": 708000.0}
    assert boq_cost(scn, models[("2N", "TX-3150")]) == sum(ln["total"] for ln in lines)


def test_pr_lines_use_erp_stock(scn, erp, models):
    prs = {p.material_id: p for p in derive_pr_lines(scn, models[("2N", "TX-2500")], erp)}
    assert prs["TX-2500"].lead_time_weeks == 98 and prs["TX-2500"].qty == 6
    assert prs["CDU-1200"].lead_time_weeks == 14  # 9 needed, 5 in stock
    assert prs["UPS-500"].lead_time_weeks == 0


def test_r15_only_transformer_fails_before_swap(scn, erp, models):
    for topo in ("2N", "DR"):
        fails = [f.element_id for f in run_rules(scn, models[(topo, "TX-2500")], erp, only=["R15"])
                 if f.status == "fail"]
        assert fails == ["TX-2500"], topo
    f = next(x for x in run_rules(scn, models[("2N", "TX-2500")], erp, only=["R15"]) if x.element_id == "TX-2500")
    assert (f.value, f.limit, f.tender_refs[0].clause) == (98.0, 26.0, "§2.3")
    for topo in ("2N", "DR", "BLOCK"):
        assert all(x.status == "pass" for x in run_rules(scn, models[(topo, "TX-3150")], erp, only=["R15"]))


def test_r12_consistency(scn, erp, models):
    m = models[("2N", "TX-3150")]
    assert run_rules(scn, m, erp, only=["R12"])[0].status == "pass"
    prs = derive_pr_lines(scn, m, erp)
    missing = [p for p in prs if p.material_id != "CDU-1200"]
    bad = run_rules(scn, m, erp, pr_lines=missing, only=["R12"])[0]
    assert bad.status == "fail" and bad.inputs["mismatched"] == "CDU-1200"
    short = [p.model_copy(update={"qty": p.qty - 10}) if p.material_id == "BW-1600" else p for p in prs]
    assert run_rules(scn, m, erp, pr_lines=short, only=["R12"])[0].status == "fail"
