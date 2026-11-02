"""Apply the decisions made on the unusual-characters overview to a text.

The overview (`characters`) lets a person decide per character: keep, replace, remove or
check. Applied blindly, some decisions would do damage, so this module adds context rules:

- "remove" on a space variant (no-break space, thin space, ...) means an ordinary space,
  and a line separator becomes a line break; removing them would glue words together;
- a Cyrillic or Greek letter is replaced by its Latin look-alike only on a line without
  other letters of that script, so real Ukrainian or Greek text stays as it is;
- a replacement that contains a digit ("Ľ" -> "1/4") is used only where the character
  stands apart from letters; inside a word the character is OCR damage of another kind;
- a line made only of one repeated symbol ("ججججج", "ÒÒÒÒÒ") is a decorative separator
  drawn with a symbol font; its characters are removed whatever their decision says.

"check" characters can be settled word by word with the spell checker
(`dictionary_replacements`): a candidate letter is used only if exactly one candidate
turns an unknown word into a known one.
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Callable

from hu_legal_cleaning.characters import UNUSUAL

KEEP, REPLACE, REMOVE = "keep", "replace", "remove"
LINE_SEPARATOR = " "
LINE_BREAK = "\n"
SPACE = " "
MIN_SEPARATOR_LENGTH = 3
LETTER = re.compile(r"[^\W\d_]")
# A word for the dictionary check: a run of characters without spaces.
TOKEN = re.compile(r"\S+")
EDGE_PUNCTUATION = "\"'„”“()[]{}.,;:!?«»-–/"
SCRIPTS_WITH_LOOKALIKES = ("CYRILLIC", "GREEK")


def _is_private_use(character: str) -> bool:
    return unicodedata.category(character) == "Co"


def is_separator_line(line: str) -> bool:
    """Return True for a line made only of one repeated symbol, e.g. "ج ج ج ج".

    Spaces and private-use characters (symbol-font glyphs) between the symbols are
    allowed. ASCII separators ("-----", "*****"), punctuation ("———", "……") and
    Hungarian letters do not count, as they may be meant.
    """
    visible = [c for c in line if not c.isspace() and not _is_private_use(c)]
    if len(visible) < MIN_SEPARATOR_LENGTH or len(set(visible)) != 1:
        return False
    is_punctuation = unicodedata.category(visible[0]).startswith("P")
    return bool(UNUSUAL.match(visible[0])) and not is_punctuation


def remove_separator_lines(text: str) -> tuple[str, int]:
    """Empty the decorative separator lines; return the text and how many were emptied."""
    lines = text.split(LINE_BREAK)
    emptied = 0
    for index, line in enumerate(lines):
        if is_separator_line(line):
            # Keep a carriage return, so CRLF files keep their line endings.
            lines[index] = "\r" if line.endswith("\r") else ""
            emptied += 1
    return LINE_BREAK.join(lines), emptied


def _script_of(character: str) -> str:
    return unicodedata.name(character, "").split(" ", 1)[0]


def _line_around(text: str, index: int) -> str:
    start = text.rfind(LINE_BREAK, 0, index) + 1
    end = text.find(LINE_BREAK, index)
    return text[start : len(text) if end < 0 else end]


def _replacement(text: str, index: int, decision: dict[str, str]) -> str | None:
    """Return what replaces the character at index, or None to leave it."""
    character = text[index]
    if decision["decision"] == REMOVE:
        if character == LINE_SEPARATOR:
            return LINE_BREAK
        return SPACE if unicodedata.category(character).startswith("Z") else ""
    if decision["decision"] != REPLACE:
        return None
    replacement = decision["replacement"]
    script = _script_of(character)
    if script in SCRIPTS_WITH_LOOKALIKES:
        line = _line_around(text, index)
        others = [c for c in line if c != character and _script_of(c) == script]
        if others:
            return None
    if any(c.isdigit() for c in replacement):
        before = text[index - 1 : index]
        after = text[index + 1 : index + 2]
        if LETTER.match(before) or LETTER.match(after):
            return None
        if before.isdigit() and replacement[0].isdigit():
            return SPACE + replacement  # "1½" -> "1 1/2", not "11/2"
    return replacement


def apply_character_decisions(
    text: str, decisions: dict[str, dict[str, str]]
) -> tuple[str, Counter[str]]:
    """Apply the reviewer's character decisions to a text, with the context rules above.

    Args:
        text: The text to change.
        decisions: Character -> {"decision", "replacement"}, e.g. from
            `characters.load_answers`.

    Returns:
        The new text and the number of changes per character ("separator line" counts
        the emptied separator lines).
    """
    text, separators = remove_separator_lines(text)
    changes: Counter[str] = Counter()
    if separators:
        changes["separator line"] = separators
    pieces = []
    position = 0
    for match in UNUSUAL.finditer(text):
        decision = decisions.get(match.group(0))
        if not decision:
            continue
        replacement = _replacement(text, match.start(), decision)
        if replacement is None:
            continue
        pieces.append(text[position : match.start()])
        pieces.append(replacement)
        position = match.end()
        changes[match.group(0)] += 1
    pieces.append(text[position:])
    return "".join(pieces), changes


def _core(token: str) -> str:
    return token.strip(EDGE_PUNCTUATION)


def dictionary_candidates(text: str, candidates: dict[str, list[str]]) -> set[str]:
    """Return every word form the dictionary check of `dictionary_replacements` asks about.

    Args:
        text: The text.
        candidates: Character -> letters that may stand for it, e.g. {"ĺ": ["í", "l"]}.

    Returns:
        The original words and their candidate forms, for one spell-checker call.
    """
    forms = set()
    for match in TOKEN.finditer(text):
        word = _core(match.group(0))
        for character, letters in candidates.items():
            if character in word:
                forms.add(word)
                forms.update(word.replace(character, letter) for letter in letters)
    return forms


def dictionary_replacements(
    text: str, candidates: dict[str, list[str]], is_known: Callable[[str], bool]
) -> tuple[str, Counter[str]]:
    """Replace a doubtful character inside words where the spell checker settles it.

    A word is changed only if it is unknown and exactly one candidate letter makes it a
    known word: "egészségbiztosĺtási" becomes "egészségbiztosítási", while a Polish
    "Łódź" or a Romanian "şi" stays.

    Args:
        text: The text.
        candidates: Character -> letters that may stand for it.
        is_known: Returns True for a word the spell checker knows.

    Returns:
        The new text and the number of words changed per character.
    """
    changes: Counter[str] = Counter()

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        word = _core(token)
        for character, letters in candidates.items():
            if character not in word or is_known(word):
                continue
            known = [word.replace(character, letter) for letter in letters]
            known = [form for form in known if is_known(form)]
            if len(known) == 1:
                changes[character] += 1
                return token.replace(word, known[0])
        return token

    return TOKEN.sub(replace, text), changes
