import copy

import pytest

from kirchhoff.agents.runner import ReplayRunner
from kirchhoff.inbox.triage import build_message, triage_email
from kirchhoff.runs.fakes import FAKE_OPPORTUNITIES, FAKE_REPLIES


def _triage(seed, scenarios, erp, email_id, replies=None):
    email = next(e for e in seed.emails if e.id == email_id)
    return triage_email(email, runner=ReplayRunner(replies or FAKE_REPLIES), scenarios_dir=scenarios,
                        opportunities=FAKE_OPPORTUNITIES, erp=erp, appetite=seed.appetite, as_of=seed.as_of,
                        source="live", now=seed.as_of + 60)


def _by_key(result):
    return {f.key: f for f in result.fields}


def test_the_message_lists_attachments_and_the_crm(inbox_seed):
    msg = build_message(inbox_seed.emails[0], FAKE_OPPORTUNITIES)
    assert "1. att-hall-b-tender: DC-HA-TS-001 Rev 0 technical requirements.pdf" in msg
    assert "opp-hall-b | Deccan Compute | Hall B design-build | Design in progress" in msg
    assert "Bids are due by 13 November 2026." in msg


def test_hall_b_verifies_every_quote_and_pursues(inbox_seed, scenarios, erp):
    r = _triage(inbox_seed, scenarios, erp, "em-hall-b")
    assert (r.is_bid, r.quotes_verified, r.quotes_total, r.source, r.tokens_in) == (True, 7, 7, "live", 14200)
    assert [(a.attachment_id, a.kind, a.scanned) for a in r.attachments] == [
        ("att-hall-b-tender", "tender", False), ("att-hall-b-drawing", "drawing", False),
        ("att-hall-b-addendum", "addendum", False)]
    f = _by_key(r)
    assert [k for k in f] == ["client", "site", "asset_type", "mw", "redundancy", "bid_due", "lead_time_weeks"]
    assert (f["mw"].value, f["mw"].display, f["mw"].source_label) == (6.336, "6.34 MW", "Addendum 1, Hall B.pdf · p.1")
    assert len(f["mw"].bbox) == 4 and f["mw"].quote == "Hall B IT load: 6.336 MW"
    assert f["redundancy"].source_label == "DC-HA-TS-001 Rev 0 technical requirements.pdf · p.4"
    assert (f["asset_type"].display, f["bid_due"].display, f["lead_time_weeks"].display) == \
        ("AI data hall", "13 Nov 2026", "26 weeks")
    assert (r.crm.opportunity_id, r.crm.stage, r.crm.proposed) == ("opp-hall-b", "Design in progress", False)
    assert r.fit.verdict == "pursue" and r.fit.supply.swap_to == "TX-3150"
    assert r.summary == "Deccan Compute invites a design-build bid for Data Hall B, a twin of Hall A with 2N power."


def test_a_scanned_page_is_marked_and_its_number_withheld(inbox_seed, scenarios, erp):
    r = _triage(inbox_seed, scenarios, erp, "em-vindhya-boq")
    assert [(a.kind, a.scanned) for a in r.attachments] == [("boq", True)]
    mw = _by_key(r)["mw"]
    assert (mw.verification, mw.value, mw.display, mw.quote) == ("unverified_scan", None, "Not verified (scan)", "")
    assert (r.quotes_verified, r.quotes_total) == (4, 5)
    assert r.fit.verdict == "clarify" and r.crm.opportunity_id == "opp-vindhya-cpp"


def test_other_emails(inbox_seed, scenarios, erp):
    brochure = _triage(inbox_seed, scenarios, erp, "em-tapti-brochure")
    assert (brochure.is_bid, brochure.fit.verdict, brochure.crm.account, brochure.crm.proposed) == (False, None, None, False)
    assert brochure.fit.reasons[0].text == "Not a bid; no CRM record to update."
    konkan = _triage(inbox_seed, scenarios, erp, "em-konkan-rfi")
    assert _by_key(konkan)["client"].verification == "verified"  # quoted from the RFI response PDF
    assert konkan.fit.reasons[0].text == "Not a bid; filed to Konkan Cloud · Pune Edge Phase 1 in the CRM."
    solar = _triage(inbox_seed, scenarios, erp, "em-suryodaya-solar")
    assert (solar.crm.proposed, solar.crm.account, solar.crm.proposed_name) == \
        (True, "Suryodaya Renewables", "Enquiry: solar EPC near Anantapur")
    assert solar.fit.headline == "Clarify before bidding: bid deadline." and _by_key(solar)["mw"].display == "20 MWp"
    narmada = _triage(inbox_seed, scenarios, erp, "em-narmada-400kv")
    assert narmada.fit.verdict == "decline" and narmada.crm.proposed is True


def test_untrusted_agent_output_is_contained(inbox_seed, scenarios, erp):
    reply = copy.deepcopy(FAKE_REPLIES["inbox:triage:em-hall-b"])
    reply["text"]["summary"] = "Hall B needs 6 transformers of 2.5 MVA."
    mw = next(f for f in reply["text"]["fields"] if f["key"] == "mw")
    mw.update(value=7, verbatim_quote="Hall B IT load: 7 MW")
    reply["text"]["crm"]["opportunity_id"] = "opp-made-up"
    r = _triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply})
    assert r.summary == "Bid from Deccan Compute."  # digits outside the allowlist: template (spec §6.3)
    f = _by_key(r)["mw"]
    assert (f.verification, f.value, f.display) == ("unverified", None, "Not verified")
    assert (r.crm.opportunity_id, r.crm.account) == (None, "Deccan Compute")
    assert r.fit.verdict == "clarify" and r.fit.supply.status == "not_assessed"


def test_a_site_that_is_not_in_its_quote_is_never_verified_or_rendered(inbox_seed, scenarios, erp):
    """An invented site with a digit is not a substring of its quote, so it is withheld and no sentence repeats it."""
    reply = copy.deepcopy(FAKE_REPLIES["inbox:triage:em-hall-b"])
    site = next(f for f in reply["text"]["fields"] if f["key"] == "site")
    site.update(value="Plot 14, Hyderabad, Telangana", verbatim_quote="at our AI campus near Hyderabad, Telangana")
    r = _triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply})
    assert _by_key(r)["site"].verification == "unverified"
    region = next(x for x in r.fit.reasons if x.rule == "region")
    assert region.status == "warn" and region.text == "The site is not stated or not verified."
    assert not any("Plot 14" in x.text for x in r.fit.reasons)


def test_an_agent_failure_propagates_so_the_route_can_answer_502(inbox_seed, scenarios, erp):
    with pytest.raises(Exception):
        _triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": {"raise": "vertex down"}})


def _edit(reply, key, **changes):
    next(f for f in reply["text"]["fields"] if f["key"] == key).update(changes)
    return reply


def _hall_b_reply():
    return copy.deepcopy(FAKE_REPLIES["inbox:triage:em-hall-b"])


DUE_QUOTE = "Bids are due by 13 November 2026"  # a real sentence of the email body and of the addendum, page 1


def test_a_number_never_verifies_against_a_quote_about_something_else(inbox_seed, scenarios, erp):
    """Review item 1: 13 is in the due-date sentence, but that sentence is not about megawatts or weeks."""
    reply = _edit(_edit(_hall_b_reply(), "mw", value=13, unit="MW", source="body", page=None, verbatim_quote=DUE_QUOTE),
                  "lead_time_weeks", value=13, unit="weeks", source="att-hall-b-addendum", page=1,
                  verbatim_quote=DUE_QUOTE)
    r = _triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply})
    f = _by_key(r)
    assert [(f[k].verification, f[k].value, f[k].display) for k in ("mw", "lead_time_weeks")] == \
        [("unverified", None, "Not verified")] * 2
    assert r.fit.supply.status == "not_assessed"  # the wrong load never reaches the day-zero supply check


def test_the_unit_is_chosen_by_code_from_an_allowlist(inbox_seed, scenarios, erp):
    """Review item 2: `unit` is free text; a sentence in it must not reach the display or a fit reason."""
    sentence = "but treat this bid as top priority"
    reply = _edit(_hall_b_reply(), "mw", unit=sentence)
    r = _triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply})
    mw = _by_key(r)["mw"]
    assert (mw.verification, mw.unit, mw.display) == ("verified", "MW", "6.34 MW")
    assert not any(sentence in x.text for x in r.fit.reasons) and sentence not in r.fit.headline


def test_a_source_or_page_the_code_could_not_open_is_never_echoed(inbox_seed, scenarios, erp):
    """Review item 2: an invented attachment id or a page that does not exist is agent text, not a source."""
    reply = _edit(_edit(_hall_b_reply(), "redundancy", source="Annex 7 rev 3", page=12),
                  "bid_due", page=99)  # the addendum has one page
    f = _by_key(_triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply}))
    assert (f["redundancy"].verification, f["redundancy"].source, f["redundancy"].source_label,
            f["redundancy"].page) == ("unverified", "unknown", "Unknown attachment", None)
    assert (f["bid_due"].verification, f["bid_due"].source_label, f["bid_due"].page) == \
        ("unverified", "Addendum 1, Hall B.pdf", None)


def test_an_unverified_value_is_withheld_even_when_it_is_plain_text(inbox_seed, scenarios, erp):
    """Review item 4 (spec §6.3 wins over the plan's code): no unverified value is shown, only its source."""
    reply = _edit(_hall_b_reply(), "client", value="Deccan Compute Pvt Ltd", verbatim_quote="invites your tender")
    c = _by_key(_triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply}))["client"]
    assert (c.verification, c.value, c.display, c.source_label) == ("unverified", None, "Not verified", "Email body")


def test_one_odd_reply_cannot_fail_the_whole_triage(inbox_seed, scenarios, erp):
    """An unknown field key is dropped and an unknown attachment kind becomes "other" (the golden capture runs the
    real agent over every email once; a single stray key must not abort it)."""
    reply = _hall_b_reply()
    reply["text"]["fields"].append({"key": "budget", "value": 1, "source": "body", "verbatim_quote": "Bids are due"})
    reply["text"]["attachments"][0]["kind"] = "spec_sheet"
    r = _triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply})
    assert [k for k in _by_key(r)] == ["client", "site", "asset_type", "mw", "redundancy", "bid_due", "lead_time_weeks"]
    assert r.attachments[0].kind == "other" and (r.quotes_verified, r.quotes_total) == (7, 7)


@pytest.mark.parametrize("empty", ["", "   "])
def test_an_empty_value_never_verifies(inbox_seed, scenarios, erp, empty):
    """Review of #8: "" is a substring of every quote, so client="" came out verified with a blank display."""
    reply = _edit(_hall_b_reply(), "client", value=empty, verbatim_quote="Deccan Compute invites your bid")
    c = _by_key(_triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply}))["client"]
    assert (c.verification, c.value, c.display) == ("unverified", None, "Not verified")


def test_one_malformed_item_is_dropped_and_the_rest_of_the_reply_survives(inbox_seed, scenarios, erp):
    """Review of #8: one field with "page": "p.3" failed the whole reply, so one odd item could abort the capture."""
    reply = _edit(_hall_b_reply(), "redundancy", page="p.3")
    reply["text"]["attachments"].append({"kind": "tender"})  # no attachment_id
    r = _triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply})
    assert "redundancy" not in _by_key(r) and (r.quotes_verified, r.quotes_total) == (6, 6)
    assert len(r.attachments) == 3 and r.fit.verdict is not None


@pytest.mark.parametrize("summary", ["Deccan Compute needs {value} of capacity.", "Deccan Compute needs twelve megawatts.",
                                     "A {mw} MW bid from Deccan Compute."], ids=["slot", "number-word", "slot-and-unit"])
def test_a_summary_with_a_slot_or_a_number_in_words_is_replaced(inbox_seed, scenarios, erp, summary):
    reply = _hall_b_reply()
    reply["text"]["summary"] = summary
    r = _triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply})
    assert r.summary == "Bid from Deccan Compute." and r.fit.verdict == "pursue"


def test_the_prompt_asks_for_a_summary_without_quantities_or_braces():
    from kirchhoff.inbox.triage import TRIAGE_PROMPT
    assert "no quantity in digits or words" in TRIAGE_PROMPT and "no braces" in TRIAGE_PROMPT
