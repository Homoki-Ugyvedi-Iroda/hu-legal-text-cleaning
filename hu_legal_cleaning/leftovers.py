"""Small mechanical fixes for leftovers that the earlier steps did not cover.

Each fix is a fixed pattern found while reviewing the open points of the BHGY corpus:

- a defendant or party label glued to the word before it ("vádlott neveI. r. vádlott",
  "ésII.rendű"): a space is inserted before the roman numeral, but only when the spell
  checker knows the word before it; otherwise the anonymiser wrote the label into the
  middle of a word ("terjeI. rendű alperesi érdekelttt elő" for "terjesztett elő"), which
  a space would not repair;
- two words written as one by the letter-spacing step because Hunspell accepts the
  compound ("KÖZTÁRSASÁGNEVÉBEN", "kijavítóvégzést"): split again;
- link code left by a legal database (`<cdp://1/95200003.TV/235/>`,
  `<javascript:LinkUgrik('A0900006.TV','','lawref')>`): removed;
- empty rows of a flattened table ("| | |"): removed;
- "�h" after a word ("forgalmazásához�h"): a closing quotation mark written in a
  wrong code page, replaced with "”".
"""

import re
from collections import Counter
from collections.abc import Callable

LOWER = "a-záéíóöőúüű"
ROMAN = r"(?:VIII|VII|VI|IV|IX|III|II|I|V|X)"
# The word before the label must be an ordinary word: "Il", "Xl" or "l" glued to "I." is a
# roman numeral with "l" misread for "I" ("IlI. r."), not a word.
GLUED_LABEL = re.compile(
    rf"(?<![\w.])(?P<word>[{LOWER}A-ZÁÉÍÓÖŐÚÜŰ]*[{LOWER}])(?P<label>{ROMAN}\. ?(?:r\.|rendű))"
)
NUMERAL_LOOKALIKE = re.compile(r"^[IVXl]*l$|^i$")
# Hunspell accepts every single letter, so a word shorter than this before a label counts
# only if it is one of the ordinary short words; other short ones are word fragments left
# by the anonymiser ("tX.rendű", "éIII.rendű").
MIN_WORD_LENGTH = 3
SHORT_WORDS = {"a", "az", "Az", "és", "ez", "is", "de", "ha", "ki", "el", "be", "ma", "mi", "ne"}
JOINED_COMPOUNDS = {
    "KÖZTÁRSASÁGNEVÉBEN": "KÖZTÁRSASÁG NEVÉBEN",
    "kijavítóvégzés": "kijavító végzés",
}
# The tags may be broken over two lines anywhere ("<javasc" / "ript:LinkUgrik"), so a line
# end is allowed between any two letters of the tag name.
LINK_CODE = re.compile(
    r" ?<(?:" + r"\s*".join("javascript") + "|" + r"\s*".join("cdp") + r")\s*:[^>]*>"
)
EMPTY_TABLE_ROW = re.compile(r"^[ \t]*\|(?:[ \t]*\|)+[ \t]*$")
MISREAD_CLOSING_QUOTE = re.compile(r"(?<=\S)�h(?=[\s\-.,;:)!?]|$)", re.MULTILINE)
CLOSING_QUOTE = "”"

GLUED_LABEL_FIX = "space before a glued label"
COMPOUND_FIX = "joined compound split"
LINK_CODE_FIX = "database link code removed"
EMPTY_ROW_FIX = "empty table row removed"
QUOTE_FIX = "misread closing quotation mark"


def glued_label_words(text: str) -> set[str]:
    """Return the words that stand directly before a glued label, for the spell checker."""
    return {match.group("word") for match in GLUED_LABEL.finditer(text)}


def fix_leftovers(
    text: str, is_known: Callable[[str], bool] = lambda word: True
) -> tuple[str, Counter[str]]:
    """Apply the fixed-pattern fixes to a text.

    Args:
        text: The text; LF or CRLF line endings are kept.
        is_known: Whether the spell checker knows a word; a glued label is split off only
            after a known word.

    Returns:
        The new text and the number of changes per kind of fix.
    """
    changes: Counter[str] = Counter()

    def split_glued_label(match: re.Match[str]) -> str:
        word = match.group("word")
        is_word = len(word) >= MIN_WORD_LENGTH or word in SHORT_WORDS
        if NUMERAL_LOOKALIKE.match(word) or not is_word or not is_known(word):
            return match.group(0)
        changes[GLUED_LABEL_FIX] += 1
        return word + " " + match.group("label")

    fixed = GLUED_LABEL.sub(split_glued_label, text)
    for joined, split in JOINED_COMPOUNDS.items():
        changes[COMPOUND_FIX] += fixed.count(joined)
        fixed = fixed.replace(joined, split)
    fixed, changes[LINK_CODE_FIX] = LINK_CODE.subn("", fixed)
    fixed, changes[QUOTE_FIX] = MISREAD_CLOSING_QUOTE.subn(CLOSING_QUOTE, fixed)

    newline = "\r\n" if "\r\n" in fixed else "\n"
    lines = fixed.split(newline)
    kept = [line for line in lines if not EMPTY_TABLE_ROW.match(line)]
    changes[EMPTY_ROW_FIX] = len(lines) - len(kept)
    return newline.join(kept), +changes
