"""
Shared text-metric helpers used by both CLI tools and the GUI.

Character counting rules (subtitle-oriented):
  - CJK characters: 1 unit each
  - Latin / alphabetic characters: 0.5 units each
  - Spaces and everything else: ignored
"""

import re
import unicodedata

_CJK_KEYWORDS = frozenset(("CJK", "HIRAGANA", "KATAKANA", "HANGUL", "IDEOGRAPH"))


def is_cjk(char: str) -> bool:
    """Return True if *char* is a CJK / kana / hangul character."""
    try:
        name = unicodedata.name(char, "")
        return any(kw in name for kw in _CJK_KEYWORDS)
    except ValueError:
        return False


def calc_length(text: str) -> float:
    """Weighted display-length of *text*.

    CJK = 1, Latin letter = 0.5, everything else = 0.
    """
    length = 0.0
    for ch in text:
        if ch.isspace():
            continue
        elif is_cjk(ch):
            length += 1.0
        elif ch.isalpha():
            length += 0.5
    return length


# Regex: one or more leading groups that look like a float (possibly negative)
# separated by whitespace, followed by the "text body".
_LEADING_FLOATS_RE = re.compile(
    r"^(?:[\-]?\d+(?:\.\d+)?\s+)+(.+)$"
)


def extract_body_text(line: str) -> str:
    """Return the trailing text portion after leading float columns.

    For a line like ``12.34 56.78 hello world`` returns ``hello world``.
    If no leading floats are detected the whole line is returned.
    """
    m = _LEADING_FLOATS_RE.match(line)
    if m:
        return m.group(1)
    return line
