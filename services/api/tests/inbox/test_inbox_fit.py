import re
from datetime import date

from kirchhoff.inbox.fit import assess_fit, day_zero_supply, days_to_due, parse_due, region_of, supply_for
from kirchhoff.inbox.models import CrmLink, ExtractedField

AS_OF = 1792132200.0  # 2026-10-16 12:00 IST
SWAP = ("26-week limit; the 2.5 MVA unit TX-2500 is 98 weeks with none in stock; "
        "expect an in-stock swap to TX-3150 (3.15 MVA, 6 in stock).")


def F(key, value, display=None, verification="verified", source_label="Email body"):
    return ExtractedField(key=key, label=key, value=value, display=display or str(value), source="body",
                          source_label=source_label, verification=verification)


HALL_B = {"client": F("client", "Deccan Compute"), "site": F("site", "AI campus near Hyderabad, Telangana"),
          "asset_type": F("asset_type", "datahall", "AI data hall"), "mw": F("mw", 6.336, "6.34 MW"),
          "redundancy": F("redundancy", "2N"), "bid_due": F("bid_due", "13 November 2026", "13 Nov 2026"),
          "lead_time_weeks": F("lead_time_weeks", 26.0, "26 weeks")}


def _fit(fields, appetite, supply=None, is_bid=True, crm=None):
    return assess_fit(is_bid=is_bid, fields=fields, crm=crm or CrmLink(), appetite=appetite, as_of=AS_OF,
                      supply=supply)


def test_dates_are_counted_from_the_world_anchor():
    assert parse_due("13 November 2026") == parse_due("13th Nov 2026") == parse_due("2026-11-13") == date(2026, 11, 13)
    assert parse_due("next month") is None and parse_due(None) is None
    assert days_to_due(date(2026, 11, 13), AS_OF) == 28


def test_region_of(inbox_seed):
    a = inbox_seed.appetite
    assert region_of("AI campus near Hyderabad, Telangana", a) == "Telangana"
    assert region_of("Satna mill, Madhya Pradesh", a) == "Madhya Pradesh"
    assert region_of("Bharuch, Gujarat", a) is None


def test_supply_uses_the_engine_internals_it_names():
    """Ruling B7: these engine internals are not on the facade; a rename in WS1 must fail here first."""
    from kirchhoff.engine import erp, options, scenario
    assert callable(options.r15_swap) and callable(scenario.with_limit) and callable(erp.effective_lead_weeks)


def test_day_zero_supply_for_hall_b_expects_the_in_stock_swap(erp):
    s = day_zero_supply(6.336, "2N", 26.0, erp)
    assert (s.status, s.topology, s.material_id, s.lead_time_weeks, s.stock, s.swap_to, s.swap_stock) == \
        ("swap", "2N", "TX-2500", 98, 0, "TX-3150", 6)
    assert s.text == SWAP
    assert day_zero_supply(6.336, "distributed redundant", 26.0, erp).topology == "DR"


def test_day_zero_supply_other_outcomes(erp):
    ok = day_zero_supply(6.336, "2N", 100.0, erp)
    assert ok.status == "ok" and ok.text == "100-week limit; the 2.5 MVA unit TX-2500 ships in time (98 weeks to order)."
    assumed = day_zero_supply(6.336, None, 26.0, erp)
    assert assumed.status == "swap" and assumed.text.startswith("Redundancy not stated; assumed 2N. 26-week limit;")
    big = day_zero_supply(30.0, "2N", 26.0, erp)
    assert big.status == "not_assessed" and "No catalogue transformer passes R01 for 30 MW in 2N" in big.text
    assert day_zero_supply(None, "2N", 26.0, erp).status == "not_assessed"
    assert day_zero_supply(6.336, "2N", None, erp).status == "not_assessed"


def test_hall_b_is_pursue_with_the_supply_line(inbox_seed, erp):
    supply = supply_for(HALL_B, inbox_seed.appetite, erp)
    fit = _fit(HALL_B, inbox_seed.appetite, supply)
    assert fit.verdict == "pursue"
    assert fit.headline == "Pursue: inside our appetite; plan the transformer swap the lead-time limit needs."
    assert [(r.rule, r.status) for r in fit.reasons] == [("asset_pack", "pass"), ("mw_range", "pass"),
                                                         ("region", "pass"), ("deadline", "pass"), ("supply", "pass")]
    assert [r.text for r in fit.reasons] == [
        "AI data hall is one of our asset packs.", "6.34 MW is inside our 2–120 MW range.",
        "AI campus near Hyderabad, Telangana is in Telangana, one of our regions.",
        "Bid due 13 Nov 2026: 28 days from 16 Oct 2026 (minimum 10).", SWAP]


def test_a_scanned_load_means_clarify(inbox_seed, erp):
    fields = {"site": F("site", "Satna mill, Madhya Pradesh"), "asset_type": F("asset_type", "grid", "Grid"),
              "mw": F("mw", None, "Not verified (scan)", "unverified_scan", "Switchyard BOQ (scan).pdf · p.1"),
              "bid_due": F("bid_due", "30 October 2026", "30 Oct 2026")}
    supply = supply_for(fields, inbox_seed.appetite, erp)
    assert supply.status == "not_assessed" and supply.text == "The day-zero supply check covers AI data halls only."
    fit = _fit(fields, inbox_seed.appetite, supply)
    assert fit.verdict == "clarify" and fit.headline == "Clarify before bidding: load (MW)."
    mw = next(r for r in fit.reasons if r.rule == "mw_range")
    assert mw.status == "warn" and "scanned page (Switchyard BOQ (scan).pdf · p.1)" in mw.text
    assert next(r for r in fit.reasons if r.rule == "supply").status == "n/a"


def test_outside_the_appetite_declines(inbox_seed):
    fields = {"site": F("site", "Bharuch, Gujarat"), "asset_type": F("asset_type", "substation", "Substation"),
              "bid_due": F("bid_due", "20 November 2026", "20 Nov 2026")}
    fit = _fit(fields, inbox_seed.appetite)
    assert fit.verdict == "decline" and fit.headline == "Decline: outside our appetite on asset type, region."
    assert fit.reasons[0].text == "Substation is not one of our asset packs (AI data hall, Grid, Solar)."


def test_deadline_rules(inbox_seed):
    def deadline(value):
        fields = {**HALL_B, "bid_due": F("bid_due", value)} if value else {k: v for k, v in HALL_B.items()
                                                                           if k != "bid_due"}
        return next(r for r in _fit(fields, inbox_seed.appetite).reasons if r.rule == "deadline")

    short = deadline("20 October 2026")
    assert short.status == "fail" and short.text == "Bid due 20 Oct 2026: 4 days from 16 Oct 2026, under our 10-day minimum."
    assert deadline("1 October 2026").status == "fail"
    assert deadline(None).status == "warn"


def test_not_a_bid_says_where_it_was_filed(inbox_seed):
    crm = CrmLink(account="Konkan Cloud", opportunity_id="opp-pune-edge-1", opportunity_name="Pune Edge Phase 1")
    fit = _fit({}, inbox_seed.appetite, is_bid=False, crm=crm)
    assert fit.verdict is None and fit.headline == "Not a bid: no fit check."
    assert [(r.rule, r.status, r.text) for r in fit.reasons] == [
        ("not_a_bid", "n/a", "Not a bid; filed to Konkan Cloud · Pune Edge Phase 1 in the CRM.")]


# ---- review carry-in (#4/#5): every sentence the client renders goes through trust.sanitize --------------------------
def _reason(fit, rule):
    return next(r for r in fit.reasons if r.rule == rule)


def test_a_digit_in_the_site_text_cannot_reach_a_sentence(inbox_seed):
    """The site is quoted from the document, so its field keeps the exact text. Reason sentences are rendered
    verbatim by the web app, so a digit that did not come from code is replaced by a digit-free sentence."""
    inside = _reason(_fit({**HALL_B, "site": F("site", "Plot 14, Hyderabad, Telangana")}, inbox_seed.appetite),
                     "region")
    assert (inside.status, inside.text) == ("pass", "The stated site is in Telangana, one of our regions.")
    outside = _reason(_fit({**HALL_B, "site": F("site", "Plot 7, Bharuch, Gujarat")}, inbox_seed.appetite), "region")
    assert outside.status == "fail" and outside.text == (
        "The stated site is outside our regions (Telangana, Andhra Pradesh, Karnataka, Maharashtra, Madhya Pradesh).")


def test_a_placeholder_in_the_site_text_is_not_filled_from_our_numbers(inbox_seed):
    text = _reason(_fit({**HALL_B, "site": F("site", "Hyderabad {limit} {mw}, Telangana")}, inbox_seed.appetite),
                   "region").text
    assert "{" not in text and "}" not in text and not any(c.isdigit() for c in text)


def test_code_numbers_are_the_only_digits_in_a_sentence(inbox_seed, erp):
    """Every number in Hall B's reasons is one the code formatted (a value, a date, the appetite or the ERP)."""
    fit = _fit(HALL_B, inbox_seed.appetite, supply_for(HALL_B, inbox_seed.appetite, erp))
    allowed = {"6.34", "2", "120", "13", "2026", "28", "16", "10", "26", "2.5", "2500", "98", "3150", "3.15", "6"}
    for r in fit.reasons:
        for token in re.findall(r"\d+(?:\.\d+)?", r.text):
            assert token in allowed, (r.rule, token, r.text)


def test_fit_sentences_render_even_when_sanitize_rejects_braces(monkeypatch):
    """Review of #8: the P2 fix wave removes {name} from sanitize's always-allowed tokens and rejects braces. Our
    sentences are templates with {placeholders} that the code fills, so they must not depend on sanitize at all."""
    import kirchhoff.inbox.fit as fit

    def strict(text, allowed, template):  # what the wave's sanitize does with a brace
        return template if "{" in text or any(c.isdigit() for c in text) else text

    monkeypatch.setattr(fit, "sanitize", strict, raising=False)
    assert fit._say("{mw} is {where} our {lo}–{hi} MW range.", "The load is checked against our range.",
                    mw="6.34 MW", where="inside", lo=2, hi=120) == "6.34 MW is inside our 2–120 MW range."
    assert fit._say("Needs 3 weeks.", "fallback") == "fallback"  # a digit in the template itself still falls back
