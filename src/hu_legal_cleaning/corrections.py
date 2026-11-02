"""Apply a reviewed correction table to texts: wrong word -> proposed word.

The table is a CSV file with at least the columns `wrong`, `proposed` and
`safe_to_apply` ("yes", "check" or "no"). Only "yes" rows are applied automatically;
"check" rows need a look at each occurrence, and "no" rows are kept for reference.
The bundled table (`data/correction_table.csv`) was built from Hungarian court decisions
and reviewed by a person; see docs/word-lists.md.
"""

import csv
import re
from importlib import resources
from pathlib import Path

SAFE = "yes"
LETTERS = "A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű"
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


def apply_corrections(text: str, corrections: dict[str, str]) -> tuple[str, int]:
    """Replace whole words found in the table, keeping their capitalisation.

    Args:
        text: The text to correct.
        corrections: Lowercase wrong word -> proposed word.

    Returns:
        The corrected text and the number of replacements.
    """
    if not corrections:
        return text, 0
    words = "|".join(re.escape(word) for word in sorted(corrections, key=len, reverse=True))
    pattern = re.compile(
        r"(?<![" + LETTERS + r"])(" + words + r")(?![" + LETTERS + r"])", re.IGNORECASE
    )
    replaced = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal replaced
        replaced += 1
        return _match_case(match.group(1), corrections[match.group(1).lower()])

    return pattern.sub(replace, text), replaced
