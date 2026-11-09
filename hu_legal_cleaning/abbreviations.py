"""Find abbreviations in a corpus and load the bundled abbreviation lists.

Sentence splitters must know that the dot in "Ptk. szerint" or "kb. tíz" does not end a
sentence. Lists change over time (statutes are renamed and replaced), so a list taken
from one source is never complete. `audit_abbreviations` therefore measures each word
that ends in a dot: if a lowercase word usually follows it on the same line, the dot
cannot be a sentence end there, so the word is almost certainly an abbreviation.
"""

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

LETTERS = "A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű"
# A word of 1-12 letters (possibly with inner dots: "s.k", "v.ö") followed by a dot and
# the next character on the same line.
DOTTED_WORD = re.compile(
    r"(?<![\w.])([" + LETTERS + r"]{1,12}(?:\.[" + LETTERS + r"]{1,6})*)\.[ \t]+(\S)"
)
ROMAN_OR_INITIAL = re.compile(r"[ivxlcdm]+|[a-záéíóöőúüű]")
LIKELY_ABBREVIATION = "likely_abbreviation"
BEFORE_NUMBER = "usually_before_number"
MIN_OCCURRENCES = 30
LOWERCASE_SHARE = 0.5
NUMBER_SHARE = 0.5
STATUTE_LIST_FILE = "abbreviations_statutes_njt.txt"
CORPUS_LIST_FILE = "abbreviations_court_decisions.csv"
STATUTE_SEPARATOR = "|"


@dataclass
class DotFollowers:
    """What follows each word that ends in a dot, counted over a corpus.

    Attributes:
        lowercase: Lowercased word -> times followed by a lowercase word.
        uppercase: Lowercased word -> times followed by a capitalised word.
        number: Lowercased word -> times followed by a digit or "§".
        forms: Lowercased word -> spellings seen, with counts ("Ptk", "ptk").
    """

    lowercase: Counter[str] = field(default_factory=Counter)
    uppercase: Counter[str] = field(default_factory=Counter)
    number: Counter[str] = field(default_factory=Counter)
    forms: dict[str, Counter[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class AbbreviationRow:
    """One row of the abbreviation audit.

    Attributes:
        token: Lowercased word without the final dot.
        commonest_form: The most frequent spelling.
        total: Occurrences followed by something on the same line.
        lowercase_share: Share of occurrences followed by a lowercase word.
        number_share: Share of occurrences followed by a digit or "§".
        verdict: "likely_abbreviation", "usually_before_number" or "".
    """

    token: str
    commonest_form: str
    total: int
    lowercase_share: float
    number_share: float
    verdict: str


def count_dot_followers(lines: list[str], followers: DotFollowers) -> None:
    """Add what follows each dotted word in one text to the running counts.

    Args:
        lines: The lines of one text.
        followers: The running counts, updated in place.
    """
    for line in lines:
        for match in DOTTED_WORD.finditer(line):
            token, following = match.group(1), match.group(2)
            key = token.lower()
            followers.forms.setdefault(key, Counter())[token] += 1
            if following.islower():
                followers.lowercase[key] += 1
            elif following.isdigit() or following == "§":
                followers.number[key] += 1
            elif following.isupper():
                followers.uppercase[key] += 1


def audit_abbreviations(followers: DotFollowers) -> list[AbbreviationRow]:
    """Turn the counts into one row per frequent dotted word, with a verdict.

    Args:
        followers: Counts from `count_dot_followers` over the corpus.

    Returns:
        Rows of words seen at least 30 times, the most frequent first.
    """
    rows = []
    for key, forms in followers.forms.items():
        lower, number = followers.lowercase[key], followers.number[key]
        total = lower + number + followers.uppercase[key]
        if total < MIN_OCCURRENCES:
            continue
        verdict = ""
        if not ROMAN_OR_INITIAL.fullmatch(key):
            if lower / total >= LOWERCASE_SHARE:
                verdict = LIKELY_ABBREVIATION
            elif number / total >= NUMBER_SHARE:
                verdict = BEFORE_NUMBER
        commonest = forms.most_common(1)[0][0]
        rows.append(
            AbbreviationRow(
                key, commonest, total, round(lower / total, 3), round(number / total, 3), verdict
            )
        )
    return sorted(rows, key=lambda row: -row.total)


def _data_file(name: str) -> Path:
    # importlib.resources finds data files inside an installed package.
    return Path(str(resources.files("hu_legal_cleaning") / "data" / name))


def load_statute_abbreviations() -> set[str]:
    """Return the statute short names of the Hungarian National Legislation Database.

    Only single-word names ending in a dot are returned, without the dot ("Ptk", "Be").
    They are case-sensitive: "Be." is the Code of Criminal Procedure, "be." a word.
    """
    text = _data_file(STATUTE_LIST_FILE).read_text(encoding="utf-8")
    entries = (entry.strip() for entry in text.split(STATUTE_SEPARATOR))
    return {entry[:-1] for entry in entries if entry.endswith(".") and " " not in entry}


def load_corpus_abbreviations(category: str | None = None) -> set[str]:
    """Return the lowercased abbreviations found in court decisions.

    Args:
        category: "legal" or "general" to return one group only; None for both.
    """
    path = _data_file(CORPUS_LIST_FILE)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        row["token"]
        for row in rows
        if row["is_abbreviation"] == "yes" and (category is None or row["category"] == category)
    }
