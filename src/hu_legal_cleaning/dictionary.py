"""Find OCR damage and typos with a spell checker, after filtering out what is not damage.

A spell checker flags far more than errors in legal texts: names, place names,
abbreviations, Latin phrases, domain terms and anonymisation leftovers. This module
counts the evidence for each word so those can be filtered out before a person reviews
the rest:

- name evidence: written with a capital in mid-sentence, next to another capitalised
  word, after "dr.", or in the last lines of the document (the signature block);
- abbreviation evidence: usually followed by a dot ("hrsz.");
- suffix fragment evidence: usually after a hyphen ("Kft.-nek" gives "nek");
- anonymisation leftovers: a placeholder that kept the suffix of the replaced name
  ("Takács Róberttel" became "nevetel").
"""

import re
from collections import Counter
from dataclasses import dataclass, field

LETTERS = "A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű"
WORD = re.compile(r"(?<![\w])[" + LETTERS + r"]{3,}(?![\w])")
SENTENCE_BREAKERS = '.:;!?(\n"„–-'
SUFFIX_HYPHENS = "-–'’"
TITLE_BEFORE = re.compile(r"(?:dr|ifj|id|özv)\.\s*$", re.IGNORECASE)
SIGNATURE_BLOCK_SHARE = 0.1
NAME_EVIDENCE_SHARE = 0.55
MAJORITY = 0.5
# The anonymiser replaced a name with "neve" and kept the Hungarian suffix of the name.
NAME_PLACEHOLDER_WITH_SUFFIX = re.compile("^neve([a-záéíóöőúüű]{1,6})$")
# Other placeholder words that keep the suffix of the replaced word, often with the wrong
# vowel harmony ("településra" instead of "településre").
PLACEHOLDER_STEMS = ("település", "város", "helység", "helysegnev", "személy", "cégnév")
CONTEXT_CHARACTERS = 2
MAX_EDIT_DISTANCE = 2
MIN_MISTAKE_LENGTH = 5
MIN_SUGGESTION_COUNT = 20
MAX_MISTAKE_SHARE = 0.25
MIN_FAMILY_PREFIX = 7


@dataclass
class WordStats:
    """Counts and evidence per lowercased word, collected over a sample of texts.

    Attributes:
        count: Occurrences.
        documents: Number of texts the word occurs in.
        name_evidence: Occurrences with at least one sign of a name: a capital initial
            in mid-sentence, a neighbour with a capital in mid-sentence, right after
            "dr.", "ifj.", "id." or "özv.", or in the last 10% of the lines of a text.
        before_dot: Occurrences followed by a dot.
        after_hyphen: Occurrences right after a hyphen or apostrophe.
    """

    count: Counter[str] = field(default_factory=Counter)
    documents: Counter[str] = field(default_factory=Counter)
    name_evidence: Counter[str] = field(default_factory=Counter)
    before_dot: Counter[str] = field(default_factory=Counter)
    after_hyphen: Counter[str] = field(default_factory=Counter)


def _is_mid_sentence_capital(line: str, match: re.Match[str]) -> bool:
    word = match.group(0)
    if not word[0].isupper() or word.isupper():
        return False
    before = line[max(0, match.start() - CONTEXT_CHARACTERS) : match.start()].rstrip(" ")
    return bool(before) and before[-1] not in SENTENCE_BREAKERS


def collect_word_stats(lines: list[str], stats: WordStats) -> None:
    """Add the words of one text and their evidence to the running statistics.

    Words written entirely in capitals (headings, names in verdicts) are skipped.

    Args:
        lines: The lines of one text.
        stats: The running statistics, updated in place.
    """
    non_empty = [line for line in lines if line.strip()]
    signature_start = len(non_empty) * (1 - SIGNATURE_BLOCK_SHARE)
    seen: set[str] = set()
    for position, line in enumerate(non_empty):
        matches = [match for match in WORD.finditer(line) if not match.group(0).isupper()]
        capitals = [_is_mid_sentence_capital(line, match) for match in matches]
        for index, match in enumerate(matches):
            key = match.group(0).lower()
            seen.add(key)
            stats.count[key] += 1
            neighbours = capitals[max(0, index - 1) : index] + capitals[index + 1 : index + 2]
            signs = (
                capitals[index],
                any(neighbours),
                TITLE_BEFORE.search(line[: match.start()]) is not None,
                position >= signature_start,
            )
            stats.name_evidence[key] += any(signs)
            stats.before_dot[key] += line[match.end() : match.end() + 1] == "."
            stats.after_hyphen[key] += line[match.start() - 1 : match.start()] in SUFFIX_HYPHENS
    stats.documents.update(seen)


def is_name_like(word: str, stats: WordStats) -> bool:
    """Return True if the evidence says the word is mostly a name.

    Args:
        word: A lowercased word.
        stats: Statistics collected by `collect_word_stats`.
    """
    total = stats.count[word]
    if not total:
        return False
    return stats.name_evidence[word] / total >= NAME_EVIDENCE_SHARE


def is_abbreviation_or_suffix(word: str, stats: WordStats) -> bool:
    """Return True if the word is mostly followed by a dot or preceded by a hyphen."""
    total = stats.count[word]
    if not total:
        return False
    return max(stats.before_dot[word], stats.after_hyphen[word]) >= MAJORITY * total


def is_anonymisation_leftover(word: str) -> bool:
    """Return True for a placeholder that kept the suffix of the word it replaced.

    Examples: "nevetel" (from "Takács Róberttel"), "településra", "személynak".
    """
    lowered = word.lower()
    if NAME_PLACEHOLDER_WITH_SUFFIX.match(lowered):
        return True
    return any(lowered.startswith(stem) and lowered != stem for stem in PLACEHOLDER_STEMS)


def edit_distance(first: str, second: str) -> int:
    """Return the Levenshtein distance: the fewest single-letter edits between two words."""
    previous = list(range(len(second) + 1))
    for row, first_letter in enumerate(first, 1):
        current = [row]
        for column, second_letter in enumerate(second, 1):
            substitution = previous[column - 1] + (first_letter != second_letter)
            current.append(min(previous[column] + 1, current[column - 1] + 1, substitution))
        previous = current
    return previous[-1]


def is_probable_mistake(word: str, suggestion: str, count: Counter[str]) -> bool:
    """Return True if an unknown word is probably a damaged form of the suggestion.

    The suggestion must be close (at most two edits), frequent in the corpus, and much
    more frequent than the unknown word: a rare variant of a common word is likely to be
    damage, while two forms of similar frequency are more likely to be two real words.

    Args:
        word: The lowercased unknown word.
        suggestion: Hunspell's best suggestion.
        count: Word counts over the sample.
    """
    target = suggestion.lower()
    if " " in target or len(word) < MIN_MISTAKE_LENGTH or target == word:
        return False
    if edit_distance(word, target) > MAX_EDIT_DISTANCE:
        return False
    return count[target] >= MIN_SUGGESTION_COUNT and count[word] < MAX_MISTAKE_SHARE * count[target]


def group_word_families(words: list[str]) -> dict[str, list[str]]:
    """Group inflected forms that share a long beginning, so a reviewer decides once.

    "ellenkérelem", "ellenkérelmében" and "ellenkérelmet" share "ellenkérel" and form
    one family; the shortest form is the head.

    Args:
        words: Lowercased words.

    Returns:
        Head word -> all forms of the family, the head first.
    """
    families: dict[str, list[str]] = {}
    for word in sorted(set(words), key=lambda item: (len(item), item)):
        head = next(
            (
                existing
                for existing in families
                if len(word) >= MIN_FAMILY_PREFIX
                and word[:MIN_FAMILY_PREFIX] == existing[:MIN_FAMILY_PREFIX]
            ),
            None,
        )
        families.setdefault(head or word, []).append(word)
    return families
