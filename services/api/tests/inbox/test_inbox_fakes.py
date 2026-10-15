import inspect

import pytest

from kirchhoff.agents import ports
from kirchhoff.contracts import Opportunity
from kirchhoff.runs.fakes import FAKE_OPPORTUNITIES, FakeEnterprise


def _opp(**kw):
    return Opportunity(**{"id": "opp-em-x", "account": "X Corp", "name": "Enquiry X", "stage": "Qualification",
                          "value": 0.0, **kw})


def test_the_fake_crm_lists_the_seed_sorted_by_id():
    fake = FakeEnterprise()
    assert [o.id for o in fake.list_opportunities(None)] == sorted(o.id for o in FAKE_OPPORTUNITIES)
    assert {o.id for o in FAKE_OPPORTUNITIES} >= {"opp-hall-a", "opp-hall-b", "opp-pune-edge-1", "opp-grid-132kv",
                                                  "opp-solar-5mwp", "opp-vindhya-cpp"}


def test_created_opportunities_are_per_visitor_and_idempotent():
    fake = FakeEnterprise()
    opp = _opp()
    assert fake.create_opportunity("u1", opp) == opp
    assert fake.create_opportunity("u1", opp.model_copy(update={"name": "changed"})).name == "Enquiry X"
    assert "opp-em-x" in {o.id for o in fake.list_opportunities("u1")}
    assert "opp-em-x" not in {o.id for o in fake.list_opportunities("u2")}
    assert "opp-em-x" not in {o.id for o in fake.list_opportunities(None)}


def test_a_seed_opportunity_cannot_be_recreated():
    with pytest.raises(ValueError):
        FakeEnterprise().create_opportunity("u1", _opp(id="opp-hall-b"))


def test_a_stage_set_by_a_visitor_shows_in_their_list_only():
    fake = FakeEnterprise()
    fake.set_opportunity_stage("u1", "opp-hall-b", "Qualification")

    def stage(uid):
        return next(o.stage for o in fake.list_opportunities(uid) if o.id == "opp-hall-b")

    assert (stage("u1"), stage("u2")) == ("Qualification", "Design in progress")


def test_the_fake_matches_the_enterprise_port_names():
    """#4's parity test covers the two real clients; the fake must agree with the port as well."""
    names = [n for n in vars(ports.EnterpriseClient) if not n.startswith("_")]
    assert {"list_opportunities", "create_opportunity"} <= set(names)
    for name in names:
        want = list(inspect.signature(getattr(ports.EnterpriseClient, name)).parameters)
        assert list(inspect.signature(getattr(FakeEnterprise, name)).parameters) == want, name
    assert ports.STAGE_QUALIFYING == "Qualification"
