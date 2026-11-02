"""Words split across two lines by a hyphen: "sze-" at the end of a line, "rint" on the next.

Typesetting and OCR leave such splits in the text; search, spell checking and sentence
splitting then see two broken words instead of "szerint". The steps are:

1. `find_hyphen_pairs` lists every (first part, second part) pair in a text.
2. `classify_pair` decides with the spell checker: join, keep the hyphen, or unresolved.
3. `hold_reason` stops the automatic join for patterns that look like a split word but
   are not (spelled-out numbers, a role word before a verdict on the next line).
4. A person reviews the unresolved pairs; `join_hyphenated_lines` applies the decisions.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

LETTERS = "A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű"
LOWER_LETTERS = "a-záéíóöőúüű"
LINE_ENDS_WITH_HYPHEN = re.compile("([" + LETTERS + "]+)-[ \\t]*$")
LINE_STARTS_LOWERCASE = re.compile("^[ \\t]*([" + LOWER_LETTERS + "]+)")

JOIN = "join"
KEEP_HYPHEN = "keep_hyphen"
UNRESOLVED = "unresolved"

# Spelled-out numbers follow their own hyphenation rules ("huszonöt-ezer" is not a
# line-break artefact), so they are never joined automatically.
NUMBER_WORD = re.compile(
    "^(?:egy|kettő|két|három|négy|öt|hat|hét|nyolc|kilenc|tíz|tizen|húsz|huszon|harminc"
    "|negyven|ötven|hatvan|hetven|nyolcvan|kilencven|száz|ezer|millió|milliárd)+$"
)
# A role word at a line end followed by a verdict or a one-letter label on the next line
# is a typographical convention ("vádlott-" / "bűnös"), not a split word.
ROLE_WORDS = {
    "állampolgár", "vádlott", "lakos", "felperesnek", "felperes",
    "alperes", "alperesnek", "terhelt", "sértett",
}  # fmt: skip
LABEL_WORDS = {"bűnös", "fa", "dr"}
MAX_LABEL_LENGTH = 2


@dataclass(frozen=True)
class HyphenPair:
    """One word split across two lines.

    Attributes:
        first_part: The letters before the hyphen at the end of the line.
        second_part: The lowercase word at the start of the next non-empty line.
        line_index: Index (from 0) of the line that ends with the hyphen.
        is_adjacent: True if no blank line stands between the two parts.
    """

    first_part: str
    second_part: str
    line_index: int
    is_adjacent: bool


def find_hyphen_pairs(lines: list[str]) -> list[HyphenPair]:
    """List the words split by a hyphen at a line end.

    Args:
        lines: The lines of one text, without line endings.

    Returns:
        One pair per line that ends in letters + "-" and whose next non-empty line
        starts with a lowercase word.
    """
    pairs = []
    for index, line in enumerate(lines):
        end = LINE_ENDS_WITH_HYPHEN.search(line)
        if not end:
            continue
        next_index = index + 1
        while next_index < len(lines) and not lines[next_index].strip():
            next_index += 1
        if next_index >= len(lines):
            continue
        start = LINE_STARTS_LOWERCASE.match(lines[next_index])
        if start:
            pair = HyphenPair(end.group(1), start.group(1), index, next_index == index + 1)
            pairs.append(pair)
    return pairs


def classify_pair(first_part: str, second_part: str, is_known: Callable[[str], bool]) -> str:
    """Decide what to do with a split word.

    Args:
        first_part: Letters before the hyphen.
        second_part: Word at the start of the next line.
        is_known: Returns True for a word the spell checker knows (lowercase input).

    Returns:
        "join" if the two parts written together are a word ("sze" + "rint");
        "keep_hyphen" if they are not but both parts are words, a real compound
        hyphen ("magánokirat-hamisítás"); otherwise "unresolved", for a person to check.
    """
    if is_known((first_part + second_part).lower()):
        return JOIN
    if is_known(first_part.lower()) and is_known(second_part.lower()):
        return KEEP_HYPHEN
    return UNRESOLVED


def hold_reason(first_part: str, second_part: str) -> str:
    """Return why a pair must not be joined automatically, or "" if it may be.

    Args:
        first_part: Letters before the hyphen.
        second_part: Word at the start of the next line.

    Returns:
        A short reason, or an empty string.
    """
    first, second = first_part.lower(), second_part.lower()
    if NUMBER_WORD.match(first) and NUMBER_WORD.match(second):
        return "spelled-out number"
    is_label = len(second) <= MAX_LABEL_LENGTH or second in LABEL_WORDS
    if first in ROLE_WORDS and is_label:
        return "role word before a verdict or label"
    return ""


def join_hyphenated_lines(lines: list[str], pairs_to_join: set[tuple[str, str]]) -> list[str]:
    """Join the split words that were approved, removing the hyphen and the line break.

    The rest of the next line is appended to the first line. Pairs with a blank line
    between the two parts are left alone, because the blank line may be a real
    paragraph break.

    Args:
        lines: The lines of one text.
        pairs_to_join: Approved (first part, second part) pairs.

    Returns:
        The new list of lines; the input list is not changed.
    """
    result = list(lines)
    # From the bottom up, so that deleting a line does not shift the indexes still to do.
    for pair in reversed(find_hyphen_pairs(lines)):
        if not pair.is_adjacent or (pair.first_part, pair.second_part) not in pairs_to_join:
            continue
        index = pair.line_index
        result[index] = result[index].rstrip(" \t")[:-1] + result[index + 1].lstrip(" \t")
        del result[index + 1]
    return result
