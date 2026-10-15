"""A check for free-text prose an agent writes for the page (spec §6.3: every number shown comes from the engine). The
digit rule lives in trust.sanitize. This catches what it does not catch on every tree: a `{slot}` that nothing will
fill, and a quantity spelled out in words ("twelve percent"). Callers fall back to a template sentence when it fails."""
import re

_NUMBER_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                 "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety "
                 "hundred thousand million billion trillion lakh crore dozen half double triple twice thrice").split()
_WORD = re.compile(r"\b(?:" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)


def prose_is_safe(text: str) -> bool:
    """False when the text has a brace or a number in words. (Whole words only: "someone" and "none" pass.)"""
    return "{" not in text and "}" not in text and _WORD.search(text) is None
