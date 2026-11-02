"""Review the "check" rows of the correction table, one occurrence at a time.

A "check" row is a wrong word that is usually, but not always, a mistake (for example
"elk", which is a typo of "elő" but also the start of a word split at a line end). Whether
the proposed correction is right depends on the surrounding text, so a person has to look
at some occurrences with their context. This module finds a spread of occurrences in the
corpus and builds an HTML page where each occurrence gets a decision and a comment.
"""

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path

from hu_legal_cleaning.corrections import INSTRUCTION_START, LETTERS
from hu_legal_cleaning.review_page import file_link
from hu_legal_cleaning.text_files import iter_lines, list_text_files

CHECK = "check"
DEFAULT_EXAMPLES = 6
DEFAULT_CONTEXT_LINES = 10
# At most this many occurrences are kept per word and year while scanning, so that the
# examples can be spread over the years without keeping every occurrence in memory.
KEPT_PER_YEAR = 2
PAGE_TITLE = "Correction table: check rows"


@dataclass
class Occurrence:
    """One place in the corpus where a wrong word stands.

    Attributes:
        source: Path of the file relative to the corpus folder, with forward slashes.
        link: A file:// link to the file.
        line_number: Line of the hit, counted from 1.
        year: The first folder of the path, which is the year in the BHGY layout.
        above: The lines before the hit line.
        before: The text of the hit line before the word.
        hit: The word as written in the text.
        after: The text of the hit line after the word.
        below: The lines after the hit line.
    """

    source: str
    link: str
    line_number: int
    year: str
    above: list[str]
    before: str
    hit: str
    after: str
    below: list[str]


@dataclass
class CheckRow:
    """A "check" row of the correction table with its occurrences.

    Attributes:
        wrong: The wrong word, lowercase.
        proposed: The proposed correction.
        error_type: The error type from the table.
        suggestions: Hunspell's suggestions from the table.
        count: Occurrences in the scanned corpus.
        documents: Files with at least one occurrence.
        occurrences: The examples chosen for the review.
    """

    wrong: str
    proposed: str
    error_type: str
    suggestions: str
    count: int = 0
    documents: int = 0
    occurrences: list[Occurrence] = field(default_factory=list)


def load_check_rows(table: Path) -> dict[str, CheckRow]:
    """Read the "check" rows of a correction table.

    Args:
        table: The correction table (CSV).

    Returns:
        Lowercase wrong word -> row, without occurrences.
    """
    with table.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        row["wrong"].lower(): CheckRow(
            row["wrong"].lower(), row["proposed"], row["type"], row["hunspell_suggestions"]
        )
        for row in rows
        if row["safe_to_apply"] == CHECK and not row["proposed"].startswith(INSTRUCTION_START)
    }


def _word_pattern(words: list[str]) -> re.Pattern[str]:
    """Match any of the words as a whole word, ignoring case."""
    alternatives = "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))
    return re.compile(f"(?<![{LETTERS}])({alternatives})(?![{LETTERS}])", re.IGNORECASE)


def _year_of(relative: str) -> str:
    return relative.split("/", 1)[0]


def find_occurrences(
    root: Path, rows: dict[str, CheckRow], examples: int, context_lines: int
) -> None:
    """Count the wrong words in a corpus and choose examples spread over the years.

    The rows are updated in place: `count`, `documents` and `occurrences`.

    Args:
        root: Folder of text files.
        rows: The "check" rows from `load_check_rows`.
        examples: How many occurrences to keep per word.
        context_lines: How many lines to keep above and below each occurrence.
    """
    pattern = _word_pattern(list(rows))
    kept: dict[str, dict[str, list[Occurrence]]] = defaultdict(lambda: defaultdict(list))
    documents: Counter[str] = Counter()
    for path in list_text_files(root):
        relative = path.relative_to(root).as_posix()
        lines = list(iter_lines(path))
        found_here: set[str] = set()
        for index, line in enumerate(lines):
            for match in pattern.finditer(line):
                word = match.group(1).lower()
                rows[word].count += 1
                found_here.add(word)
                year = _year_of(relative)
                if len(kept[word][year]) >= KEPT_PER_YEAR:
                    continue
                kept[word][year].append(
                    Occurrence(
                        relative,
                        file_link(path),
                        index + 1,
                        year,
                        lines[max(0, index - context_lines) : index],
                        line[: match.start()],
                        match.group(1),
                        line[match.end() :],
                        lines[index + 1 : index + 1 + context_lines],
                    )
                )
        documents.update(found_here)
    for word, row in rows.items():
        row.documents = documents[word]
        row.occurrences = _spread(kept[word], examples)


def _spread(by_year: dict[str, list[Occurrence]], examples: int) -> list[Occurrence]:
    """Pick occurrences by taking one per year in turn, so that no single year dominates."""
    years = sorted(by_year)
    chosen: list[Occurrence] = []
    for round_number in range(KEPT_PER_YEAR):
        for year in years:
            if round_number < len(by_year[year]) and len(chosen) < examples:
                chosen.append(by_year[year][round_number])
    return sorted(chosen, key=lambda occurrence: occurrence.source)


def build_check_page(rows: dict[str, CheckRow], storage_key: str) -> str:
    """Build the HTML review page.

    Args:
        rows: The "check" rows with their occurrences.
        storage_key: Name under which the browser keeps the answers; use a different one
            for each corpus or table.

    Returns:
        The HTML page, which is self-contained.
    """
    template = Path(str(resources.files("hu_legal_cleaning") / "data" / "check_rows_template.html"))
    words = json.dumps([asdict(row) for row in rows.values()], ensure_ascii=False)
    # "</" inside the JSON would end the script block early.
    words = words.replace("</", "<\\/")
    return (
        template.read_text(encoding="utf-8")
        .replace("<!--TITLE-->", PAGE_TITLE)
        .replace("<!--STORAGE-KEY-->", storage_key)
        .replace("/*WORDS*/[]", words)
    )
