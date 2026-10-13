from kirchhoff.agents.trust import allowed_ids_for, fill, fill_finding, fmt_value, is_clean, sanitize
from kirchhoff.contracts import Connection, DesignModel, Equipment, Geometry, Pipe, Point3, Rack

IDS = {"FA-01", "FB-03", "H-Z2", "A1", "R1", "CDU-4", "TX-3150"}
T = "Power completed fix selection."


def test_clean_text_with_record_tokens_passes_unchanged():
    s = "FA-01 fails R05 under §4.6 in the 2N option. Upsizing to TX-3150 is not needed."
    assert sanitize(s, IDS, T) == s


def test_sentence_with_a_free_number_is_replaced_by_the_template_once():
    s = "H-Z2 crosses FB-03. The drop is 2.16% on FA-01. It also runs 82 m. Cooling owns H-Z2."
    assert sanitize(s, IDS, T) == f"H-Z2 crosses FB-03. {T} Cooling owns H-Z2."


def test_topologies_rules_clauses_and_placeholders_need_no_listing():
    s = "N+1 per zone, 3 + 1 blocks and 4-to-make-3 all meet R04b and §6.3.4 with {value} under {limit}."
    assert is_clean(s, set())


def test_unknown_element_id_is_not_allowed():
    assert not is_clean("FA-99 is overloaded.", IDS)


def test_appendix_clause_is_not_split():
    assert sanitize("App. B allows block redundancy. §4.2 governs.", IDS, T) == \
        "App. B allows block redundancy. §4.2 governs."


def test_empty_text_becomes_template():
    assert sanitize("   ", IDS, T) == T


def test_fill_and_fmt_value():
    assert fill("{value} exceeds {limit} on {element}", {"value": fmt_value(2.16, "%"), "limit": fmt_value(2.0, "%")}) \
        == "2.16% exceeds 2% on {element}"
    assert fmt_value(1546.0, "A") == "1,546 A" and fmt_value(None, "A") == "n/a"


def test_fill_finding_never_doubles_the_unit():
    engine = "Drop via FA-01 is {value}% against a limit of {limit}%."  # WS1 template style
    agent = "FA-01 has a drop of {value}, above the {limit} limit."  # agent style
    assert fill_finding(engine, 2.16, 2.0, "%") == "Drop via FA-01 is 2.16% against a limit of 2%."
    assert fill_finding(agent, 2.16, 2.0, "%") == "FA-01 has a drop of 2.16%, above the 2% limit."
    assert fill_finding("TX-2500 ships in {value} weeks, limit {limit}.", 98, 26, "weeks") == \
        "TX-2500 ships in 98 weeks, limit 26 weeks."
    assert fill_finding("{value} {unit} vs {limit}", 1546, None, "A") == "1,546 A vs n/a"


def test_allowed_ids_for_model():
    m = DesignModel(
        topology="2N",
        racks=[Rack(id="R1-01", row="R1", x=6, y=15.9, kw=132, liquid_fraction=0.8, feeds=("A-01", "B-01"))],
        equipment=[Equipment(id="T-A1", kind="transformer", catalogue_id="TX-3150", system="A")],
        connections=[Connection(id="FA-01", src="A1", dst="A-01", kind="busway", catalogue_id="BW-1600")],
        cooling_nodes=[], pipes=[Pipe(id="H-Z2", kind="header", zone="Z2", dn=200, tier="pipe_high",
                                      route=[Point3(x=30, y=30, z=3.8)])],
        geometry=Geometry(hall=(60, 36), columns=[], keepouts=[], rooms={}, tiers={}), loads={})
    ids = allowed_ids_for(m, extra=["CDU-1"])
    assert {"R1-01", "R1", "A-01", "B-01", "T-A1", "TX-3150", "FA-01", "A1", "BW-1600", "H-Z2", "Z2", "CDU-1"} <= ids
