"""Apply a reviewed correction table to texts: wrong word -> proposed word.

The table is a CSV file with at least the columns `wrong`, `proposed` and
`safe_to_apply` ("yes", "check" or "no"). Only "yes" rows are applied automatically;
"check" rows need a look at each occurrence, and "no" rows are kept for reference.
The bundled table (`data/correction_table.csv`) was built from Hungarian court decisions
and reviewed by a person; see docs/word-lists.md.
"""

import csv
import re
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

SAFE = "yes"
LETTERS = "A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű"
# A word touching a digit or underscore is part of an anonymisation placeholder
# ("tanu1", "tanu_2") and must keep the form the source gave it.
WORD_CHARACTERS = LETTERS + "0-9_"
# Rows whose "proposed" value is an instruction, e.g. "(normalise the text to NFC)".
INSTRUCTION_START = "("


def bundled_table_path() -> Path:
    """Return the path of the correction table shipped with the package."""
    # importlib.resources finds data files inside an installed package.
    return Path(str(resources.files("hu_legal_cleaning") / "data" / "correction_table.csv"))


def load_corrections(path: Path, only_safe: bool = True) -> dict[str, str]:
    """Read a correction table.

    Args:
        path: The CSV file.
        only_safe: If True, return only the rows marked safe to apply.

    Returns:
        Lowercase wrong word -> proposed word.
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    corrections = {}
    for row in rows:
        if only_safe and row["safe_to_apply"] != SAFE:
            continue
        if row["proposed"].startswith(INSTRUCTION_START):
            continue
        corrections[row["wrong"].lower()] = row["proposed"]
    return corrections


def _match_case(original: str, replacement: str) -> str:
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def correction_pattern(corrections: dict[str, str]) -> re.Pattern[str]:
    """Return a pattern matching any wrong word of the table as a whole word, in any case.

    A word directly before or after a letter, digit or underscore does not match.

    Args:
        corrections: Lowercase wrong word -> proposed word; must not be empty.
    """
    # Longest words first, so that a longer wrong word wins over a shorter one it contains.
    words = "|".join(re.escape(word) for word in sorted(corrections, key=len, reverse=True))
    return re.compile(
        r"(?<![" + WORD_CHARACTERS + r"])(" + words + r")(?![" + WORD_CHARACTERS + r"])",
        re.IGNORECASE,
    )


def apply_corrections(
    text: str,
    corrections: dict[str, str],
    protected_spans: Sequence[tuple[int, int]] = (),
) -> tuple[str, int]:
    """Replace whole words found in the table, keeping their capitalisation.

    Args:
        text: The text to correct.
        corrections: Lowercase wrong word -> proposed word.
        protected_spans: (start, end) character ranges of the text that must stay as
            written, e.g. verbatim quotes from `protected_text.protected_quotes`.

    Returns:
        The corrected text and the number of replacements.
    """
    if not corrections:
        return text, 0
    replaced = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal replaced
        if any(start <= match.start() < end for start, end in protected_spans):
            return match.group(1)
        replaced += 1
        return _match_case(match.group(1), corrections[match.group(1).lower()])

    return correction_pattern(corrections).sub(replace, text), replaced
