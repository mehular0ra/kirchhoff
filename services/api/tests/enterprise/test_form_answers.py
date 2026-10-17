"""The paste-ready answers for the Hack2skill form (docs/submission/form-answers.md, issue #32) and the checklist beside it
(docs/submission/checklist.md): the brief description has a hard limit of 1024 characters on the form and must name the Google
services the form asks about, every form field has a non-empty answer, the facts decided on 17 Oct (the form's closing time, the
3:00 to 4:00 video, the Sun 18 Oct 18:00 target) stay recorded and the old ones do not creep back, and neither document carries an
email address other than the organisers', or a key. A later edit that breaks one of these fails here instead of on the submission day."""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ANSWERS = REPO / "docs" / "submission" / "form-answers.md"
CHECKLIST = REPO / "docs" / "submission" / "checklist.md"
LIMIT = 1024  # "0/1024" on the form's Brief Description field


def _text() -> str:
    assert ANSWERS.is_file(), "docs/submission/form-answers.md is missing (issue #32)"
    return ANSWERS.read_text(encoding="utf-8")


def _brief() -> str:
    m = re.search(r"<!-- BRIEF START -->[ \t]*\n(.*?)\n[ \t]*<!-- BRIEF END -->", _text(), re.S)
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
    lines = _text().splitlines()
    for field in ("Challenges", "Prototype Link Deployed on GCP or Cloud run", "Final Prototype PPT/Deck converted into PDF",
                  "GitHub Repository Link (Public Access)", "Demo Video Link (3-4 minutes)", "Brief Description of Your Solution"):
        row = next((ln for ln in lines if ln.startswith(f"| {field}")), None)
        assert row, f"no row for the form field {field!r}"
        cells = [c.strip() for c in row.strip().strip("|").split("|")]  # field | limit | our answer | status
        assert len(cells) >= 4 and cells[2], f"the row for {field!r} has no answer"


def test_the_decided_facts_are_recorded_in_both_documents_and_the_old_ones_are_gone():
    assert "18/10/2026 11:59:00 PM (IST)" in _text()
    for path in (ANSWERS, CHECKLIST):
        text = path.read_text(encoding="utf-8")
        assert "11:59" in text, f"{path.name}: the form's closing time is not recorded"
        assert "3:00 to 4:00" in text, f"{path.name}: the decided video length (3:00 to 4:00) is not recorded"
        assert "18:00" in text, f"{path.name}: the Sun 18 Oct 18:00 submit target is not recorded"
        # decisions of 15-16 Oct that 17 Oct replaced; the T&C wording "strictly under three (3) minutes" is quoted on purpose and is not listed here
        for stale in ("20:00 IST", "2:55"):
            assert stale not in text, f"{path.name} still says {stale!r}, which the 17 Oct decisions replaced"


def test_no_other_email_address_and_no_key_is_in_the_submission_documents():
    for path in (ANSWERS, CHECKLIST):
        text = path.read_text(encoding="utf-8")
        # the organisers' support address is public and named on purpose; any other address would be personal data
        others = [e for e in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text) if e != "support+aibuildercup@hack2skill.com"]
        assert not others, f"personal data in {path.name}: {others}"
        assert not re.search(r"AIza[0-9A-Za-z_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY", text), f"a key is in {path.name}"
