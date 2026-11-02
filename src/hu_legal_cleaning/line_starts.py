"""Lines that lost their first letter(s): "értett" for "Sértett", "ővárosi" for "Fővárosi".

Some OCR and conversion runs cut the first letter of a line. The damaged word starts in
lowercase, so it also misleads sentence splitting. The method compares, over a whole
corpus, how often a word starts a line in lowercase with how often a slightly longer
capitalised word starts a line:

- "értett" starts 900 lines, "Sértett" starts 40,000 lines: "értett" is probably damaged.
- A real wrapped line (a sentence continued on the next line) also starts in lowercase,
  so a candidate is kept only if it is much rarer than the capitalised form.
- Only lines that follow a finished sentence are counted, because a damaged line is a
  sentence start whose first letter is missing. A line that continues the sentence above
  ("..., amely" / "mellett az értékkülönbség ...") is a normal wrap, not damage.

A person then reviews the candidates; `fix_line_starts` applies the approved ones.
"""

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

LETTERS = "A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű"
# A digit may follow the word: "értett1" (a numbered victim) counts as "értett".
FIRST_WORD = re.compile(r"^\s*([" + LETTERS + r"]{2,})(?![" + LETTERS + r"])")
SINGLE_LETTERS = list("abcdefghijklmnopqrstuvwxyzáéíóöőúüű")
# Hungarian digraphs are one letter of the alphabet but two characters.
DIGRAPHS = ["sz", "cs", "gy", "ny", "ty", "zs", "ly", "dz"]
LOST_PREFIXES = SINGLE_LETTERS + DIGRAPHS
MIN_CAPITALISED_LINES = 200
MAX_SHARE_OF_CAPITALISED = 1 / 3
MIN_LOWERCASE_LINES = 3
MIN_WORD_LENGTH = 4
# A line after one ending in one of these (or after a blank line) starts a new sentence.
SENTENCE_END = ".!?:;"


@dataclass
class LineStartCounts:
    """How often each word starts a line, over a corpus.

    Attributes:
        lowercase: Lowercase line-start word -> number of lines.
        capitalised: Lowercased form of a capitalised line-start word -> number of lines.
    """

    lowercase: Counter[str]
    capitalised: Counter[str]


@dataclass(frozen=True)
class LostLetterCandidate:
    """A lowercase line-start word that probably lost its first letter(s).

    Attributes:
        damaged: The word as it stands at the line start, e.g. "értett".
        lost_letters: The letters probably lost, e.g. "s".
        probable_word: The probable original, capitalised, e.g. "Sértett".
        damaged_lines: Number of lines starting with the damaged word.
        original_lines: Number of lines starting with the probable original.
    """

    damaged: str
    lost_letters: str
    probable_word: str
    damaged_lines: int
    original_lines: int


def starts_sentence(previous_line: str | None) -> bool:
    """Tell whether a line that follows `previous_line` can begin a new sentence.

    Args:
        previous_line: The line above, or None for the first line of a text.
    """
    if previous_line is None:
        return True
    previous = previous_line.rstrip()
    return not previous or previous[-1] in SENTENCE_END


def count_line_starts(lines: list[str], counts: LineStartCounts) -> None:
    """Add the first words of the lines of one text to the counts.

    Words written entirely in capitals (headings) are not counted. A lowercase word is
    counted only if the line follows a finished sentence (see `starts_sentence`).

    Args:
        lines: The lines of one text.
        counts: The running counts, updated in place.
    """
    for index, line in enumerate(lines):
        match = FIRST_WORD.match(line)
        if not match:
            continue
        word = match.group(1)
        if word[0].islower():
            if starts_sentence(lines[index - 1] if index else None):
                counts.lowercase[word] += 1
        elif not word.isupper():
            counts.capitalised[word.lower()] += 1


def find_lost_letter_candidates(counts: LineStartCounts) -> list[LostLetterCandidate]:
    """Return the lowercase line-start words that probably lost their first letter(s).

    Args:
        counts: Line-start counts over the whole corpus.

    Returns:
        The candidates, the most frequent first.
    """
    best: dict[str, LostLetterCandidate] = {}
    for damaged, damaged_lines in counts.lowercase.items():
        if damaged_lines < MIN_LOWERCASE_LINES or len(damaged) < MIN_WORD_LENGTH:
            continue
        for prefix in LOST_PREFIXES:
            original_lines = counts.capitalised.get(prefix + damaged, 0)
            is_frequent = original_lines >= MIN_CAPITALISED_LINES
            if not is_frequent or damaged_lines >= original_lines * MAX_SHARE_OF_CAPITALISED:
                continue
            if damaged in best and best[damaged].original_lines >= original_lines:
                continue
            probable = (prefix + damaged).capitalize()
            best[damaged] = LostLetterCandidate(
                damaged, prefix, probable, damaged_lines, original_lines
            )
    return sorted(best.values(), key=lambda candidate: -candidate.damaged_lines)


def fix_line_starts(lines: list[str], replacements: dict[str, str]) -> tuple[list[str], int]:
    """Replace damaged line-start words with their approved corrections.

    Only the first word of a line is changed, and only when it matches exactly.

    Args:
        lines: The lines of one text.
        replacements: Damaged word -> correction, e.g. {"értett": "Sértett"}.

    Returns:
        The new lines and the number of lines changed.
    """
    result, changed = [], 0
    for line in lines:
        match = FIRST_WORD.match(line)
        if match and match.group(1) in replacements:
            start, end = match.span(1)
            line = line[:start] + replacements[match.group(1)] + line[end:]
            changed += 1
        result.append(line)
    return result, changed


LAST_WORD = re.compile(r"([" + LETTERS + r"]+)(-?)[ \t]*$")


def join_line_start(
    lines: list[str],
    fragment: str,
    is_known: Callable[[str], bool],
    expected: str | None = None,
    with_space: bool = False,
) -> tuple[list[str], list[str]]:
    """Join lines whose first word is the second half of a word split at the line above.

    Some line breaks split a word without a hyphen ("sze" / "rint") or with one that the
    line-break step did not join. A reviewer marks such line-start words; this function
    puts each one back on the previous non-empty line.

    Args:
        lines: The lines of one text.
        fragment: The line-start word, e.g. "rint".
        is_known: Returns True for a word the spell checker knows; the joined word must
            be known, otherwise the line is left alone. With `with_space` it is asked
            about the two words ("e körben"), so the caller can limit such joins.
        expected: The whole word the reviewer gave, e.g. "Mosonmagyaróvár" for "óvár".
            If the line above ends with the missing part ("Mosonmagyar-"), the lines are
            joined; if it does not, the line-start word is replaced by this word.
        with_space: Join with a space instead of putting the halves together, for a
            line that only continues the sentence above ("e" / "körben").

    Returns:
        The new lines and the written form of each change, e.g. ["szerint"].
    """
    result = list(lines)
    changes = []
    # From the bottom up, so that deleting lines does not shift the indexes still to do.
    for index in range(len(result) - 1, 0, -1):
        first = FIRST_WORD.match(result[index])
        if not first or first.group(1) != fragment:
            continue
        previous = index - 1
        while previous > 0 and not result[previous].strip():
            previous -= 1
        last = LAST_WORD.search(result[previous])
        written = _joined_form(last, fragment, is_known, expected, with_space)
        if written is None:
            if expected:
                start, end = first.span(1)
                result[index] = result[index][:start] + expected + result[index][end:]
                changes.append(expected)
            continue
        rest = result[index].lstrip(" \t")[len(fragment) :]
        result[previous] = result[previous][: last.start()] + written + rest
        del result[previous + 1 : index + 1]
        changes.append(written)
    return result, changes


def _joined_form(
    last: re.Match[str] | None,
    fragment: str,
    is_known: Callable[[str], bool],
    expected: str | None,
    with_space: bool,
) -> str | None:
    """Return how the last word above and the fragment are written together, or None."""
    if last is None:
        return None
    word = last.group(1)
    if with_space:
        spaced = f"{word} {fragment}"
        return spaced if is_known(spaced) else None
    forms = [word + fragment, f"{word}-{fragment}"]
    if expected:
        return next((form for form in forms if form.lower() == expected.lower()), None)
    return forms[0] if is_known(forms[0]) else None
