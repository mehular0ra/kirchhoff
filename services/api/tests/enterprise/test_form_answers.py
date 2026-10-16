"""The paste-ready answers for the Hack2skill form (docs/submission/form-answers.md, issue #32): the brief description has a
hard limit of 1024 characters on the form and must name the Google services the form asks about, and the file may carry no
personal data. A later edit that breaks one of these fails here instead of on the submission day."""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ANSWERS = REPO / "docs" / "submission" / "form-answers.md"
LIMIT = 1024  # "0/1024" on the form's Brief Description field


def _text() -> str:
    assert ANSWERS.is_file(), "docs/submission/form-answers.md is missing (issue #32)"
    return ANSWERS.read_text(encoding="utf-8")


def _brief() -> str:
    m = re.search(r"<!-- BRIEF START -->\n(.*?)\n<!-- BRIEF END -->", _text(), re.S)
    assert m, "the brief description must sit between the BRIEF START and BRIEF END markers"
    return m.group(1).strip()


def test_the_brief_description_fits_the_form_limit():
    brief = _brief()
    assert len(brief) <= LIMIT, f"the brief description is {len(brief)} characters, the form allows {LIMIT}"
    assert len(brief) > 400, "the brief description is suspiciously short"


def test_the_stated_character_count_is_the_real_one():
    stated = re.search(r"the text below \((\d+) characters\)", _text())
    assert stated, "the field table must state the character count of the brief description"
    assert int(stated.group(1)) == len(_brief())


def test_the_brief_names_the_services_the_form_asks_about():
    brief = _brief()
    missing = [s for s in ("Firebase", "Firestore", "Cloud Run", "Gemini") if s not in brief]
    assert not missing, f"the form wants these named in the description: {missing}"


def test_every_form_field_has_an_answer_row():
    text = _text()
    for field in ("Challenges", "Prototype Link Deployed on GCP or Cloud run", "Final Prototype PPT/Deck converted into PDF",
                  "GitHub Repository Link (Public Access)", "Demo Video Link (3-4 minutes)", "Brief Description of Your Solution"):
        assert f"| {field}" in text, f"no row for the form field {field!r}"


def test_the_closing_time_is_recorded_and_no_personal_data_is_in_the_file():
    text = _text()
    assert "18/10/2026 11:59:00 PM (IST)" in text
    # the organisers' support address is public and named on purpose; any other address would be personal data
    others = [e for e in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text) if e != "support+aibuildercup@hack2skill.com"]
    assert not others, f"personal data in the answers file: {others}"
