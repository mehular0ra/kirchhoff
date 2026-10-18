"""The caption glossary of docs/submission/video/transcribe.py: the narration of the longer video cut says "BOQ" (the scanned bill of
quantities in the bids inbox) and "5 MWp" (the solar plant), and a speech-to-text engine writes those as "B O Q" or "5 megawatt peak".
The glossary must put them right, and leave the units and names it already handled alone. transcribe.py imports its Google libraries
only inside the engine functions, so the glossary can be tested here with the standard library."""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "docs" / "submission" / "video" / "transcribe.py"


@pytest.fixture(scope="module")
def glossary():
    spec = importlib.util.spec_from_file_location("kirchhoff_video_transcribe", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # a dataclass in the script looks its module up by name
    try:
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.modules.pop(spec.name, None)


@pytest.mark.parametrize("spoken, caption", [
    ("a 132 kilovolt grid intake and a 5 megawatt peak solar plant", "a 132 kV grid intake and a 5 MWp solar plant"),
    ("a 5 MWp solar plant", "a 5 MWp solar plant"),
    ("a 5 MW p solar site", "a 5 MWp solar site"),
    ("a 5 megawatt-peak plant", "a 5 MWp plant"),
    ("a decline for the scanned B O Q", "a decline for the scanned BOQ"),
    ("the scanned boq is not verified", "the scanned BOQ is not verified"),
])
def test_the_new_terms_of_the_longer_cut_are_written_right(glossary, spoken, caption):
    assert glossary.glossary(spoken) == caption


@pytest.mark.parametrize("spoken, caption", [
    ("a 6.336 megawatt hall of 132 kilowatts a rack and 3.15 MVA", "a 6.336 MW hall of 132 kW a rack and 3.15 MVA"),
    ("5 megawatts per hall", "5 MW per hall"),
    ("the bob and the boxes", "the bob and the boxes"),
])
def test_the_units_it_already_handled_and_ordinary_words_are_left_alone(glossary, spoken, caption):
    assert glossary.glossary(spoken) == caption


def test_the_speech_engine_is_hinted_with_the_new_terms(glossary):
    assert {"BOQ", "MWp"} <= set(glossary.STT_PHRASES)
