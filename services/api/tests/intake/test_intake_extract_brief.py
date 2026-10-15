import pytest

from kirchhoff.agents.runner import ReplayRunner
from kirchhoff.agents.trust import is_clean
from kirchhoff.contracts import Citation, Requirement
from kirchhoff.intake.brief import UNVERIFIED_TEMPLATE, _topology_backstop, build_brief, canonical_topology
from kirchhoff.intake.extract import ExtractedContradiction, TenderExtraction, extract_tender, read_drawing
from kirchhoff.intake.verify import PdfText, QuoteCheck, clause_on_page, verify_quote
from kirchhoff.runs.fakes import FAKE_REPLIES

AGREES = {"agrees": True, "differences": []}


def _brief(tender_pdf, extraction):
    """The production checks: quotes verified on their page, clause labels printed on their page."""
    with PdfText(tender_pdf) as pdf:
        return build_brief("hall-b", "tender-hall-a", extraction,
                           lambda p, q, v, u=None: verify_quote(pdf, p, q, v, u), AGREES, set(),
                           clause_printed=lambda page, label: clause_on_page(pdf, page, label))


def test_extract_and_build_brief(tender_pdf):
    extraction, res = extract_tender(ReplayRunner(FAKE_REPLIES), tender_pdf.read_bytes())
    assert res.tokens_in == 9000
    brief = _brief(tender_pdf, extraction)
    assert len(brief.requirements) == 8 and sum(r.verified for r in brief.requirements) == 7
    bad = next(r for r in brief.requirements if not r.verified)
    assert bad.id == "REQ-ups_autonomy_min" and bad.value is None and bad.text == UNVERIFIED_TEMPLATE
    dv = next(r for r in brief.requirements if r.id == "REQ-dv_max_pct")
    assert dv.value == 2.0 and dv.citation.page == 4 and dv.citation.clause == "§4.6" and dv.citation.bbox
    assert dv.text == "shall not exceed 2.0% at the worst-case design current"
    (q,) = brief.open_questions
    assert q.id == "Q-redundancy" and q.default_resolution == "2N" and q.options == ["2N", "compare_all"]
    assert [c.clause for c in q.citations] == ["§4.2", "App. B"] and all(c.bbox for c in q.citations)
    assert q.text == "§4.2 requires 2N but App. B accepts block or distributed redundancy."
    assert q.resolution is None and brief.drawing_check == AGREES


def test_read_drawing_returns_structured_read():
    read, _ = read_drawing(ReplayRunner(FAKE_REPLIES), b"%PDF-1.4")
    assert read.grid_x == ["1", "2", "3", "4", "5", "6"] and read.overall_mm == [60000, 36000]


def test_contradiction_with_unverifiable_quote_is_dropped(tender_pdf):
    c = ExtractedContradiction(topic="redundancy", clause_a="§4.2", page_a=4, quote_a="The system shall be 3N",
                               value_a="3N", clause_b="App. B", page_b=7,
                               quote_b="Block or distributed redundancy acceptable", value_b="DR",
                               summary="x")
    assert _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions == []


def test_appendix_listed_first_still_defaults_to_main_body(tender_pdf):
    c = ExtractedContradiction(topic="Power redundancy", clause_a="App. B", page_a=7,
                               quote_a="Block or distributed redundancy acceptable", value_a="BLOCK",
                               clause_b="§4.2", page_b=4, quote_b="The critical power distribution shall be 2N",
                               value_b="2N redundancy", summary="They disagree in 2 places.")
    (q,) = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions
    assert q.id == "Q-power-redundancy" and q.default_resolution == "2N"
    assert q.text == "App. B and §4.2 disagree; the main body governs by default."


def test_duplicate_keys_get_suffixes(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "tx_loading", "clause": "§4.3", "page": 4, "value": 80, "unit": "%",
         "verbatim_quote": "Transformer loading shall not exceed 80% of rating in normal operation"},
        {"key": "tx_loading", "clause": "§4.3", "page": 4, "value": 100, "unit": "%",
         "verbatim_quote": "100% of rating under any single failure"}]})
    assert [r.id for r in _brief(tender_pdf, ex).requirements] == ["REQ-tx_loading", "REQ-tx_loading-2"]


def test_canonical_topology():
    assert canonical_topology("2N redundancy") == "2N"
    assert canonical_topology("distributed redundant") == "DR"
    assert canonical_topology("Block redundant") == "BLOCK"
    assert canonical_topology("N+1") is None


def test_unverified_digit_free_quote_still_gets_the_template(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "x", "clause": "§9.9", "page": 4, "value": None, "unit": None,
         "verbatim_quote": "This sentence is not present on this page at all."}]})
    (r,) = _brief(tender_pdf, ex).requirements
    assert not r.verified and r.value is None and r.text == UNVERIFIED_TEMPLATE


def test_unverified_quote_with_only_allowlisted_tokens_still_gets_the_template(tender_pdf):
    # §4.2's real text on the wrong page: no digits outside allowed tokens (2N, §4.2), so a naive
    # sanitize() pass-through would leave the raw LLM text in place. It must still be the template.
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "redundancy", "clause": "§4.2", "page": 7, "value": "2N", "unit": None,
         "verbatim_quote": "The critical power distribution shall be 2N, with each rack fed from two "
                           "independent systems."}]})
    (r,) = _brief(tender_pdf, ex).requirements
    assert not r.verified and r.value is None and r.text == UNVERIFIED_TEMPLATE


def test_unverified_quote_with_digits_still_gets_the_template(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "y", "clause": "§9.9", "page": 4, "value": 99, "unit": None,
         "verbatim_quote": "This made-up sentence claims 99 units that are not on this page."}]})
    (r,) = _brief(tender_pdf, ex).requirements
    assert not r.verified and r.value is None and r.text == UNVERIFIED_TEMPLATE


def test_wrong_unit_requirement_is_unverified(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "dv_max_pct", "clause": "§4.6", "page": 4, "value": 2.0, "unit": "A",
         "verbatim_quote": "shall not exceed 2.0% at the worst-case design current"}]})
    (r,) = _brief(tender_pdf, ex).requirements
    assert not r.verified and r.value is None and r.text == UNVERIFIED_TEMPLATE


def test_correct_unit_requirement_verifies(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "dv_max_pct", "clause": "§4.6", "page": 4, "value": 2.0, "unit": "%",
         "verbatim_quote": "shall not exceed 2.0% at the worst-case design current"}]})
    (r,) = _brief(tender_pdf, ex).requirements
    assert r.verified and r.value == 2.0


def _redundancy_reqs():
    return TenderExtraction.model_validate({"requirements": [
        {"key": "redundancy", "clause": "§4.2", "page": 4, "value": "2N", "unit": None,
         "verbatim_quote": "The critical power distribution shall be 2N, with each rack fed from two "
                           "independent systems."},
        {"key": "redundancy_alt", "clause": "App. B", "page": 7, "value": "BLOCK", "unit": None,
         "verbatim_quote": "Block or distributed redundancy acceptable, subject to the loading limits of "
                           "§4.3."}]})


def test_backstop_derives_the_redundancy_question_when_the_model_found_no_contradiction(tender_pdf):
    # Ruling P2-R13: the model's contradictions list is EMPTY, but the verified §4.2 and App. B
    # requirements disagree on topology, so the deterministic backstop must derive Q-redundancy.
    brief = _brief(tender_pdf, _redundancy_reqs())
    assert sum(r.verified for r in brief.requirements) == 2
    (q,) = brief.open_questions
    assert q.id == "Q-redundancy" and q.default_resolution == "2N"
    assert [c.clause for c in q.citations] == ["§4.2", "App. B"]
    assert all(c.bbox for c in q.citations)
    assert q.text == "§4.2 requires 2N but App. B allows BLOCK or DR."


_MAIN_42 = ("§4.2", 4, "The critical power distribution shall be 2N")
_APP_B = ("App. B", 7, "Block or distributed redundancy acceptable")


def _contradiction(a, b, topic="redundancy", summary="§4.2 requires 2N but App. B accepts block or distributed "
                                                    "redundancy."):
    return ExtractedContradiction(topic=topic, clause_a=a[0], page_a=a[1], quote_a=a[2], value_a=a[2],
                                  clause_b=b[0], page_b=b[1], quote_b=b[2], value_b=b[2], summary=summary)


@pytest.mark.parametrize("pair", [(_MAIN_42, _APP_B), (_APP_B, _MAIN_42), (_MAIN_42, ("App.B",) + _APP_B[1:])],
                         ids=["main-first", "appendix-first", "label-spacing"])
def test_backstop_does_not_duplicate_the_models_own_verified_contradiction(tender_pdf, pair):
    # The matching verified question (citing BOTH §4.2 and App. B, in either order, however the label is
    # spaced) still suppresses it.
    ex = _redundancy_reqs()
    ex.contradictions.append(_contradiction(*pair))
    brief = _brief(tender_pdf, ex)
    assert len(brief.open_questions) == 1
    assert brief.open_questions[0].id == "Q-redundancy"


def test_unrelated_topology_question_does_not_suppress_the_backstop(tender_pdf):
    # Fix round 4, finding 3: a verified question whose default is a topology (2N) but which cites §4.2
    # against §6.2, not App. B, must not suppress the §4.2/App. B backstop -- and the two questions must
    # not share an id (the plan gate keys questions by id, so a clash would silently drop one).
    ex = _redundancy_reqs()
    ex.contradictions.append(_contradiction(
        _MAIN_42, ("§6.2", 6, "CDUs shall be provided N+1 per hydraulic zone"),
        summary="§4.2 asks for 2N power but §6.2 asks for N+1 CDUs."))
    brief = _brief(tender_pdf, ex)
    model_q, backstop = brief.open_questions
    assert [c.clause for c in model_q.citations] == ["§4.2", "§6.2"] and model_q.default_resolution == "2N"
    assert [c.clause for c in backstop.citations] == ["§4.2", "App. B"] and backstop.default_resolution == "2N"
    assert model_q.id == "Q-redundancy" and backstop.id == "Q-redundancy-2"


@pytest.mark.parametrize("main_clause,alt_clause", [("Clause 12345", "App. B"), ("§4.2", "App. 12345")])
def test_forged_clause_label_never_reaches_the_backstop_text(tender_pdf, main_clause, alt_clause):
    # Fix round 4, finding 1: clause labels are LLM free text that verify_quote never checks, so a forged
    # label with raw digits verifies alongside a genuine quote. P2 final fix wave: such a label is not printed
    # on its page, so it is dropped (None) -- the chip shows "Tender · p.N" -- and no text can carry it.
    ex = _redundancy_reqs()
    ex.requirements[0].clause, ex.requirements[1].clause = main_clause, alt_clause
    brief = _brief(tender_pdf, ex)
    assert [r.citation.clause for r in brief.requirements] == [
        None if "12345" in main_clause else "§4.2", None if "12345" in alt_clause else "App. B"]
    assert all("12345" not in q.text and is_clean(q.text, set()) for q in brief.open_questions)


def test_forged_clause_label_never_reaches_a_model_question_text(tender_pdf):
    # The same hole in _question(): its clause-naming fallback template was built from the raw labels.
    c = _contradiction(("Clause 12345",) + _MAIN_42[1:], _APP_B,
                       summary="Clause 12345 requires 2N but App. B accepts block or distributed redundancy.")
    (q,) = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions
    assert "12345" not in q.text and is_clean(q.text, set()), q.text


def _req(rid: str, clause: str | None, text: str, value: str | None = None) -> Requirement:
    return Requirement(id=rid, text=text, value=value, verified=True,
                       citation=Citation(doc_id="tender-hall-a", page=4, quote=text, clause=clause))


@pytest.mark.parametrize("main_clause,alt_clause", [(None, "App. B"), ("§4.2", None)])
def test_requirement_without_clause_label_never_drives_the_backstop(main_clause, alt_clause):
    # Fix round 4, finding 2: no clause label means neither main body nor appendix.
    reqs = [_req("REQ-redundancy", main_clause, "The critical power distribution shall be 2N", "2N"),
            _req("REQ-redundancy_alt", alt_clause, "Block or distributed redundancy acceptable")]
    assert _topology_backstop(reqs, "tender-hall-a") is None


def test_blank_clause_label_never_drives_the_backstop(tender_pdf):
    ex = _redundancy_reqs()
    ex.requirements[0].clause = "  "
    brief = _brief(tender_pdf, ex)
    assert sum(r.verified for r in brief.requirements) == 2 and brief.open_questions == []


def _brief_all_verified(extraction):
    return build_brief("hall-b", "tender-hall-a", extraction,
                       lambda p, q, v, u=None: QuoteCheck(True, "ok", (0.0, 0.0, 1.0, 1.0)), AGREES, set(),
                       clause_printed=lambda page, label: True)


def _topology_reqs(alt_c_key: str, alt_b_key: str, main_key: str = "redundancy"):
    return TenderExtraction.model_validate({"requirements": [
        {"key": main_key, "clause": "§4.2", "page": 4, "value": "2N",
         "verbatim_quote": "The critical power distribution shall be 2N"},
        {"key": alt_c_key, "clause": "App. C", "page": 8, "value": None,
         "verbatim_quote": "A distributed CDU arrangement is acceptable"},
        {"key": alt_b_key, "clause": "App. B", "page": 7, "value": None,
         "verbatim_quote": "Block or distributed redundancy acceptable"}]})


@pytest.mark.parametrize("alt_c_key,alt_b_key", [("cdu_arrangement_alt", "redundancy_alt"),
                                                  ("redundancy_cooling_alt", "redundancy")],
                         ids=["shared-key-word", "identical-key"])
def test_backstop_prefers_the_key_matched_pair_over_the_first_match(alt_c_key, alt_b_key):
    # Fix round 4, finding 4: App. C comes first, but App. B's key matches §4.2's key "redundancy" (shares
    # the word, or is identical -- which outranks merely sharing a word), so App. B is the pair.
    (q,) = _brief_all_verified(_topology_reqs(alt_c_key, alt_b_key)).open_questions
    assert [c.clause for c in q.citations] == ["§4.2", "App. B"]
    assert q.text == "§4.2 requires 2N but App. B allows BLOCK or DR."


@pytest.mark.parametrize("main_key,alt_b_key", [("power_topology", "appendix_b"), ("_", "-")],
                         ids=["no-shared-word", "wordless-keys"])
def test_backstop_falls_back_to_the_first_match_without_a_key_match(main_key, alt_b_key):
    # Two keys with no words at all are not "identical keys": that must not outrank the first match.
    (q,) = _brief_all_verified(_topology_reqs("cdu_arrangement", alt_b_key, main_key=main_key)).open_questions
    assert [c.clause for c in q.citations] == ["§4.2", "App. C"]
    assert q.text == "§4.2 requires 2N but App. C allows DR."


def test_backstop_ignores_fabricated_contradictions_and_requirements(tender_pdf):
    # The live diagnostics' fabricated examples: quotes that are not on the cited page at all.
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "lead_time_alt", "clause": "§1.3", "page": 1, "value": 20, "unit": "weeks",
         "verbatim_quote": "Alternative equipment may be delivered within 20 weeks."},
        {"key": "redundancy_alt", "clause": "§5.4", "page": 5, "value": "N+1", "unit": None,
         "verbatim_quote": "An N+1 arrangement is also acceptable."}],
        "contradictions": [{"topic": "clearance", "clause_a": "§5.1", "page_a": 5,
                            "quote_a": "clear height shall be 3.5 m", "value_a": "3.5",
                            "clause_b": "App. B", "page_b": 7, "quote_b": "clear height shall be 3.0 m",
                            "value_b": "3.0", "summary": "x"}]})
    brief = _brief(tender_pdf, ex)
    assert all(not r.verified for r in brief.requirements)
    assert brief.open_questions == []


def test_neither_clause_main_body_defaults_to_clause_a(tender_pdf):
    # Both sides cite an appendix: clause_a wins (no main body present to prefer).
    c = ExtractedContradiction(topic="redundancy", clause_a="App. A", page_a=7,
                               quote_a="Block or distributed redundancy acceptable", value_a="BLOCK",
                               clause_b="App. B", page_b=7,
                               quote_b="Block or distributed redundancy acceptable", value_b="DR",
                               summary="Two appendices disagree.")
    (q,) = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions
    assert q.default_resolution == "BLOCK"


@pytest.mark.parametrize("leak", ["§4.2 sets {value} but App. B sets {limit}.",
                                  "§4.2 needs two independent systems but App. B accepts one point five.",
                                  "§4.2 needs 2 x 100% but App. B accepts 150%."],
                         ids=["placeholder", "number-words", "digits"])
def test_question_text_never_shows_a_placeholder_or_an_llm_quantity(tender_pdf, leak):
    # P2 final fix wave, Important 1: the plan-gate question text is shown verbatim at the gate.
    c = _contradiction(_MAIN_42, _APP_B, summary=leak)
    (q,) = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions
    assert q.text == "§4.2 and App. B disagree; the main body governs by default."


# --- P2 final fix wave, Important 2 (trust sweep, P2-R16): every clause label, question id, default and option
# shown at the plan gate is built from verified data, never from the model's free text ------------------------

from kirchhoff.intake.textnorm import normalize_clause  # noqa: E402


@pytest.mark.parametrize("raw,label", [
    ("App. B", "App. B"), ("Appendix B", "App. B"), ("App B", "App. B"), ("App.B", "App. B"), ("Annex B", "App. B"),
    ("appendix b: acceptable alternatives", "App. B"), ("App. B Appendix B", "App. B"), ("§4.2", "§4.2"),
    ("§ 4.2", "§4.2"), ("Section 4.2", "§4.2"), ("Clause 6.3.4", "§6.3.4"), ("4.2", "§4.2"),
    ("§4.2 (450 kW per row)", "§4.2"), ("§4.2.", "§4.2"),
    ("Application", None), ("26 weeks", None), ("Table 3", None), ("App. 12345", None), ("  ", None), (None, None)])
def test_clause_labels_are_normalised_or_dropped(raw, label):
    assert normalize_clause(raw) == label


def test_a_clause_label_must_be_printed_on_its_page(tender_pdf):
    with PdfText(tender_pdf) as pdf:
        assert clause_on_page(pdf, 4, "§4.2") and clause_on_page(pdf, 7, "App. B") and clause_on_page(pdf, 6, "§6.3.4")
        assert not clause_on_page(pdf, 7, "§4.2") and not clause_on_page(pdf, 4, "§12345")
        assert not clause_on_page(pdf, 4, "§4.25") and not clause_on_page(pdf, 4, "App. B")


def test_appendix_b_written_first_still_defaults_to_2n_and_offers_it(tender_pdf):
    # The tender prints "App. B Appendix B: acceptable alternatives" on page 7, so the model may write either.
    c = ExtractedContradiction(topic="redundancy", clause_a="Appendix B", page_a=7,
                               quote_a="Block or distributed redundancy acceptable", value_a="BLOCK or DR",
                               clause_b="Section 4.2", page_b=4, quote_b="The critical power distribution shall be 2N",
                               value_b="2N", summary="Appendix B accepts block or distributed redundancy.")
    (q,) = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions
    assert q.default_resolution == "2N" and q.options == ["2N", "compare_all"]
    assert [x.clause for x in q.citations] == ["App. B", "§4.2"]


def test_default_and_options_come_from_the_verified_main_body_quote_not_the_models_value(tender_pdf):
    c = ExtractedContradiction(topic="redundancy", clause_a="§4.2", page_a=4,
                               quote_a="The critical power distribution shall be 2N, with each rack fed from two "
                                       "independent systems.", value_a="two independent systems (2 x 100%)",
                               clause_b="App. B", page_b=7, quote_b="Block or distributed redundancy acceptable",
                               value_b="BLOCK", summary="x")
    (q,) = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions
    assert q.default_resolution == "2N" and q.options == ["2N", "compare_all"]


def test_question_ids_use_letters_only_and_a_numeric_default_must_be_in_the_quote():
    lead = dict(topic="lead time 26", clause_a="§2.3", page_a=2, quote_a="no later than 26 weeks from contract award",
                clause_b="App. B", page_b=7, quote_b="Alternatives may ship within thirty weeks", value_b="30 weeks",
                summary="x")
    ok = ExtractedContradiction(value_a="26 weeks", **lead)
    forged = ExtractedContradiction(value_a="20 weeks", **{**lead, "topic": "lead"})  # not what the quote says
    (q,) = _brief_all_verified(TenderExtraction(requirements=[], contradictions=[ok, forged])).open_questions
    assert q.id == "Q-lead-time" and q.default_resolution == "26 weeks" and q.options == ["26 weeks", "compare_all"]


def test_every_question_id_is_unique(tender_pdf):
    c1 = _contradiction(_MAIN_42, _APP_B, topic="redundancy")
    c2 = _contradiction(_MAIN_42, ("§6.2", 6, "CDUs shall be provided N+1 per hydraulic zone"), topic="Redundancy!")
    qs = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c1, c2])).open_questions
    assert [q.id for q in qs] == ["Q-redundancy", "Q-redundancy-2"]


def test_clause_chip_with_extra_text_shows_only_the_verified_clause_id(tender_pdf):
    c = _contradiction(("§4.2 (450 kW per row)",) + _MAIN_42[1:], _APP_B)
    (q,) = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions
    assert [x.clause for x in q.citations] == ["§4.2", "App. B"]


def test_requirement_ids_clauses_and_unverified_units_carry_no_model_digits(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "rack_kw_132", "clause": "Section 3.1", "page": 3, "value": 132, "unit": "kW",
         "verbatim_quote": "each rack rated 132 kW"},
        {"key": "made_up", "clause": "Clause 12345", "page": 4, "value": 99, "unit": "99 kW",
         "verbatim_quote": "This made-up sentence claims 99 units that are not on this page."},
        {"key": "dv_max_pct", "clause": "§4.6", "page": 7, "value": 2.0, "unit": "%",
         "verbatim_quote": "shall not exceed 2.0% at the worst-case design current"}]})
    good, bad, wrong_page = _brief(tender_pdf, ex).requirements
    assert good.id == "REQ-rack_kw" and good.verified and good.citation.clause == "§3.1"
    assert bad.id == "REQ-made_up" and not bad.verified and bad.unit is None and bad.citation.clause is None
    assert not wrong_page.verified and wrong_page.citation.clause is None  # §4.6 is not printed on page 7
