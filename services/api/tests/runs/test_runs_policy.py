from kirchhoff.contracts import TopologyOption
from kirchhoff.runs.compat import FixCandidate
from kirchhoff.runs.policy import choose_option, lead_limit_weeks, preferred_candidate
from kirchhoff.runs.fakes import FakeScenario


def _opt(i, cost, lead=12, spof=0):
    return TopologyOption(id=i, installed_mva=1, normal_loading_pct=1, failover_loading_pct=1, cost=cost,
                          losses_kw=1, max_lead_time_weeks=lead, spof_count=spof)


def test_choose_option_follows_the_auto_rule():
    opts = [_opt("2N", 5.0), _opt("DR", 4.0), _opt("BLOCK", 3.0, lead=98)]
    assert choose_option(opts, {"Q-redundancy": "2N"}, 26).id == "2N"
    assert choose_option(opts, {"Q-redundancy": "compare_all"}, 26).id == "DR"  # BLOCK breaks §2.3
    assert choose_option([_opt("2N", 5.0, spof=1)], {}, 26) is None
    assert choose_option([_opt("DR", 4.0), _opt("2N", 4.0)], {}, 26).id == "2N"  # tie: §4.2 governs


def _c(i, cost, **m):
    return FixCandidate(id=i, finding_id="f", label=i, cost_delta=cost, metrics=m, patch={})


def test_preferred_candidate_criteria():
    drop, reroute = _c("H-Z2:local-drop", 420.0, changed_pipes=1.0), _c("H-Z2:reroute", -910.0, changed_pipes=2.0)
    assert preferred_candidate("cooling", [reroute, drop]).id == "H-Z2:local-drop"
    up = _c("FA-01:upsize-BW-2000", 11480.0, dv_pct=1.66, dv_limit_pct=2.0)
    cable = _c("FA-01:cable-CBL-240-8P", 26900.0, dv_pct=0.84, dv_limit_pct=2.0)
    assert preferred_candidate("power", [up, cable]).id == "FA-01:cable-CBL-240-8P"
    assert preferred_candidate("procurement", [cable, up]).id == "FA-01:upsize-BW-2000"


def test_lead_limit_reads_the_tender():
    assert lead_limit_weeks(FakeScenario("hall_a", {"clauses": [{"id": "§2.3", "limits": {"max_lead_time_weeks": 20}}]})) == 20
    assert lead_limit_weeks(FakeScenario("hall_a", {"clauses": []})) == 26
