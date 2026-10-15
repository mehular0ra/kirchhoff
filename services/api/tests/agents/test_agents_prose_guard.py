import pytest

from kirchhoff.agents.prose_guard import prose_is_safe


@pytest.mark.parametrize("text", ["Zebra meets the ampacity need with the lowest losses.",
                                  "STR-28 clears the inverter window.", "Someone none the wiser, honestly.", "",
                                  "The option with the best margin per dollar."])
def test_plain_prose_passes(text):
    assert prose_is_safe(text)


@pytest.mark.parametrize("text", ["It stays at {value} against {limit}.", "Use {unit} here", "a } stray brace",
                                  "It cuts losses by twelve percent.", "Twenty-five percent cheaper.",
                                  "THIRTEEN weeks", "about a hundred", "two options", "nearly double the margin",
                                  "one option is clearly better"])
def test_slots_braces_and_numbers_in_words_are_rejected(text):
    """What sanitize (spec 6.3) does not catch on every tree: a {slot} nothing will fill, and a number spelled out."""
    assert not prose_is_safe(text)
