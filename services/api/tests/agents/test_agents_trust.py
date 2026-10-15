import pytest

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
    assert is_clean(s, set(), placeholders=True)


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


def test_superscript_digit_triggers_template():
    assert sanitize("The area is five mm².", IDS, T) == T


def test_superscript_digit_in_word_fails_is_clean():
    assert not is_clean("flow of three m³ per hour", IDS)


def test_vulgar_fraction_fails_is_clean():
    assert not is_clean("½ load", IDS)


def test_allowlisted_sentence_still_passes_with_unicode_digit_check():
    s = "FA-01 fails R05 under §4.6 in the 2N option. Upsizing to TX-3150 is not needed."
    assert sanitize(s, IDS, T) == s


# --- P2 final fix wave, Important 1: no unfilled placeholder and no LLM-written quantity reaches a user ---------

LEAKS = ["The drop is {value}, above the {limit} limit.",  # an unfilled placeholder
         "The drop is two point one six percent.",  # a quantity in words
         "The drop is 7.77 percent."]  # raw digits


@pytest.mark.parametrize("leak", LEAKS, ids=["placeholder", "number-words", "digits"])
def test_a_leaking_sentence_is_replaced_by_the_template(leak):
    assert sanitize(f"FA-01 fails R05. {leak} Cooling owns H-Z2.", IDS, T) == f"FA-01 fails R05. {T} Cooling owns H-Z2."


def test_placeholders_pass_only_when_the_caller_fills_them():
    s = "FA-01 has a drop of {value}, above the {limit} limit."
    assert sanitize(s, IDS, T) == T  # narration, fix reasons, voice: never filled, so never shown
    assert sanitize(s, IDS, T, placeholders=True) == s  # explain fills {value}/{limit}/{unit} afterwards
    assert sanitize("FA-01 is at {rack_kw} now.", IDS, T, placeholders=True) == T  # nothing fills other names
    assert sanitize("FA-01 is at { value } now.", IDS, T, placeholders=True) == T  # nor a malformed token
    assert not is_clean("FA-01 is fine {value}", IDS)


@pytest.mark.parametrize("text", [
    "Layout placed sixty-four racks in four rows.", "There are Twelve CDUs.", "One hundred racks fit.",
    "Loading is half the rating.", "The margin is one point five.", "The lead time is one week.",
    "It is eighty percent loaded.", "Losses are a few thousand watts.", "Zero single points of failure remain."])
def test_quantities_in_words_are_not_clean(text):
    assert not is_clean(text, IDS)


@pytest.mark.parametrize("text", [
    "Power chose the one with the largest margin per dollar.", "Often the tenant prefers the 2N option.",
    "Cooling sized the CDUs on behalf of each zone.", "The weight of FA-01 is within the limit.",
    "FA-01 fails R05 under §4.6; the fourth row is fine."])
def test_ordinary_words_are_not_number_words(text):
    assert is_clean(text, IDS)


def test_narration_agents_are_told_never_to_state_a_quantity_and_only_explain_gets_placeholders():
    from kirchhoff.agents import specs

    narrators = [specs.ORCHESTRATOR, specs.LAYOUT, specs.POWER, specs.COOLING, specs.PROCUREMENT, specs.DOCS,
                 specs.ASSET]
    for spec in narrators:
        assert specs.NARRATION_RULE in spec.instruction, spec.name
        assert "{value}" not in spec.instruction and "{limit}" not in spec.instruction, spec.name
    assert "{value}" in specs.COPILOT.instruction and "{limit}" in specs.COPILOT.instruction
    # Issue #36: the voice model no longer narrates (the answer is the code-authored engine_summary); it only
    # transcribes and picks a tool, so it gets no NARRATION_RULE, which would forbid the digits it transcribes.
    voice = specs.COPILOT_VOICE.instruction
    assert specs.NARRATION_RULE not in voice
    assert all(f'"{key}"' in voice for key in ("transcript", "tool", "args"))
    assert "{value}" not in voice and "{limit}" not in voice
