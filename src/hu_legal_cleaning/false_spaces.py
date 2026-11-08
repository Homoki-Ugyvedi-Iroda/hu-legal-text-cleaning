"""Find words that were split by a false space: "els ő" for "első", "elk övetési" for "elkövetési".

A false space turns one word into two pieces, usually because a character was lost or
kerned apart in the source. The test is simple: two neighbouring words on one line are a
candidate if the spell checker knows the two pieces joined together, but does not know
one of the pieces by itself. Pairs of two real words ("az alapján") are never listed,
and lines made of single letters ("k e r ü l e t") are skipped, because the author
spaced them out on purpose.

The candidates are counted as pairs, so a person decides once per pair, not once per
occurrence. A few reviewed pairs can go into the correction table, which `apply` already
knows; a long list of approved pairs is applied with `join_false_spaces`, which also skips
a pair after a digit or hyphen ("PN10-es és") and before a closing bracket ("pont ba)").
"""

import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from hu_legal_cleaning.corrections import LETTERS

# Every word that is followed by a space and another word; the lookahead lets the next
# pair start at the second word, so "a b c" gives the pairs (a, b) and (b, c).
# A word after a digit, hyphen, dash, slash or dot is not counted as the first piece: it is
# usually a suffix ("2010-ig a") or an abbreviation, not a broken word.
WORD_PAIR = re.compile(
    rf"(?<![{LETTERS}0-9\-–/.])([{LETTERS}]+)(?= ([{LETTERS}]+)(?![{LETTERS}\-]))"
)
WORD = re.compile(rf"[{LETTERS}]+")
# A line is letter-spaced if at least this share of its words is a single letter.
LETTER_SPACED_SHARE = 0.4
MIN_WORDS_FOR_LETTER_SPACING = 3


@dataclass
class PairStats:
    """How often a pair of neighbouring words occurs.

    Attributes:
        count: Occurrences.
        documents: Files with at least one occurrence.
        forms: The pair as written (with its capitals), commonest first after `most_common`.
        example: A "path:line" where the pair stands.
    """

    count: int
    documents: int
    forms: Counter[tuple[str, str]]
    example: str


def is_letter_spaced(line: str) -> bool:
    """Tell whether a line is written with spaces between the letters of its words."""
    words = WORD.findall(line)
    if len(words) < MIN_WORDS_FOR_LETTER_SPACING:
        return False
    singles = sum(1 for word in words if len(word) == 1)
    return singles / len(words) >= LETTER_SPACED_SHARE


def word_pairs(line: str) -> list[tuple[str, str]]:
    """Return the neighbouring word pairs of a line, or none for a letter-spaced line."""
    if is_letter_spaced(line):
        return []
    return [(match.group(1), match.group(2)) for match in WORD_PAIR.finditer(line)]


def vocabulary(lines: Iterable[str]) -> Counter[str]:
    """Count the words of some lines."""
    counts: Counter[str] = Counter()
    for line in lines:
        counts.update(WORD.findall(line))
    return counts


def collect_pairs(
    texts: Iterable[tuple[str, list[str]]], is_interesting: Callable[[str, str], bool]
) -> dict[tuple[str, str], PairStats]:
    """Count the neighbouring word pairs that pass a filter.

    Args:
        texts: (relative path, lines) for each file.
        is_interesting: Tells whether a pair is worth counting, to keep memory small.

    Returns:
        Lowercase pair -> statistics.
    """
    found: dict[tuple[str, str], PairStats] = {}
    for relative, lines in texts:
        seen_here: set[tuple[str, str]] = set()
        for number, line in enumerate(lines, 1):
            for first, second in word_pairs(line):
                if not is_interesting(first, second):
                    continue
                key = (first.lower(), second.lower())
                stats = found.setdefault(key, PairStats(0, 0, Counter(), f"{relative}:{number}"))
                stats.count += 1
                stats.forms[(first, second)] += 1
                if key not in seen_here:
                    seen_here.add(key)
                    stats.documents += 1
    return found


def false_space_pairs(
    pairs: dict[tuple[str, str], PairStats], unknown: set[str], joined_is_unknown: set[str]
) -> list[tuple[str, str, str, PairStats]]:
    """Keep the pairs whose joined form is a word but at least one piece is not.

    Args:
        pairs: The counted pairs from `collect_pairs`.
        unknown: Words the spell checker does not know.
        joined_is_unknown: Joined forms the spell checker does not know.

    Returns:
        (first piece, second piece, joined form, statistics), the most frequent first.
        The pieces and the joined form are written as in the commonest form of the pair.
    """
    candidates = []
    for stats in pairs.values():
        (first, second), _ = stats.forms.most_common(1)[0]
        joined = first + second
        has_unknown_piece = first in unknown or second in unknown
        if has_unknown_piece and joined not in joined_is_unknown:
            candidates.append((first, second, joined, stats))
    return sorted(candidates, key=lambda candidate: -candidate[3].count)


def joined_forms(pairs: dict[tuple[str, str], PairStats]) -> set[str]:
    """Return the joined form of each pair, written as in its commonest form."""
    return {
        first + second for first, second in (s.forms.most_common(1)[0][0] for s in pairs.values())
    }


# A pair to join: two words separated by spaces on one line. Like WORD_PAIR, the first piece
# must not follow a digit, hyphen, dash, slash or dot ("PN10-es és"), and the second must
# not run on into a hyphen, a digit or a closing bracket ("pont ba)" is a sub-point label).
JOINABLE_PAIR = re.compile(
    rf"(?<![{LETTERS}0-9\-–/.])([{LETTERS}]+)( +)(?=([{LETTERS}]+)(?![{LETTERS}0-9\-)\]]))"
)


def join_false_spaces(
    text: str, joins: set[str], protected_spans: Sequence[tuple[int, int]] = ()
) -> tuple[str, int]:
    """Remove the false space inside each listed pair, keeping the letters as written.

    Args:
        text: The text.
        joins: Lowercase pairs to join, written with one space ("magy ar").
        protected_spans: (start, end) ranges that stay as written, e.g. quoted lay writing.

    Returns:
        The new text and the number of joins.
    """
    joined = 0

    def join(match: re.Match[str]) -> str:
        nonlocal joined
        pair = f"{match.group(1)} {match.group(3)}".lower()
        is_protected = any(start <= match.start() < end for start, end in protected_spans)
        # An abbreviation in capitals before a lowercase word ("AB a", "PR és") is two words.
        first = match.group(1)
        is_abbreviation = len(first) > 1 and first.isupper() and match.group(3)[:1].islower()
        if pair not in joins or is_protected or is_abbreviation:
            return match.group(0)
        joined += 1
        return match.group(1)

    return JOINABLE_PAIR.sub(join, text), joined
