"""Overview of the unusual characters in a corpus, for a person to check.

Hungarian text is made of ASCII and 18 accented letters. Every other character is worth a
look: some are right (quotation marks, the section sign), some are damage (a replacement
character, a stray accent mark, a Cyrillic letter inside a Latin word). The overview counts
each such character, shows a few examples in context and lets a person decide what to do
with it. The decisions are an input for the next clean-up, not applied by this module.
"""

import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path

from hu_legal_cleaning.review_page import file_link
from hu_legal_cleaning.text_files import list_text_files, read_text

HUNGARIAN_LETTERS = "áéíóöőúüűÁÉÍÓÖŐÚÜŰ"
# Everything that is not ASCII and not a Hungarian letter. A regular expression finds these
# characters much faster than a loop over every character of every file.
UNUSUAL = re.compile(f"[^\\x00-\\x7f{HUNGARIAN_LETTERS}]")
DEFAULT_EXAMPLES = 3
CONTEXT_WIDTH = 30
PAGE_TITLE = "Unusual characters"
NEWLINE_SIGN = "⏎"

REPLACEMENT_CHARACTER = "�"
KIND_BY_CATEGORY = {
    "Mn": "combining mark",
    "Mc": "combining mark",
    "Me": "combining mark",
    "Cf": "invisible format character",
    "Cc": "control character",
    "Co": "private use",
    "Cs": "surrogate",
    "Cn": "unassigned",
}


@dataclass
class Example:
    """One place where a character stands.

    Attributes:
        source: Path of the file relative to the corpus folder.
        link: A file:// link to the file.
        line_number: Line of the character, counted from 1.
        year: The first folder of the path, which is the year in the BHGY layout.
        before: Text before the character on its line.
        after: Text after the character on its line.
    """

    source: str
    link: str
    line_number: int
    year: str
    before: str
    after: str


@dataclass
class CharacterStats:
    """Everything the overview knows about one character.

    Attributes:
        character: The character itself.
        code: Its code point, e.g. "U+00AD".
        name: Its Unicode name.
        kind: A group, e.g. "combining mark" or "other script letter (Cyrillic)".
        count: Occurrences.
        documents: Files with at least one occurrence.
        examples: A few occurrences, from different years where possible.
    """

    character: str
    code: str
    name: str
    kind: str
    count: int = 0
    documents: int = 0
    examples: list[Example] = field(default_factory=list)


def kind_of(character: str) -> str:
    """Return the group a character belongs to.

    Args:
        character: One character.
    """
    if character == REPLACEMENT_CHARACTER:
        return "replacement character"
    category = unicodedata.category(character)
    if category in KIND_BY_CATEGORY:
        return KIND_BY_CATEGORY[category]
    if category.startswith("Z"):
        return "space variant"
    if category.startswith("P"):
        return "punctuation"
    if category.startswith(("S", "N")):
        return "symbol or number"
    name = unicodedata.name(character, "")
    script = name.split(" ", 1)[0].title() if name else "Unknown"
    if script == "Latin":
        return "Latin letter outside Hungarian"
    return f"other script letter ({script})"


def scan_characters(root: Path, examples: int = DEFAULT_EXAMPLES) -> dict[str, CharacterStats]:
    """Count the unusual characters of a corpus and collect examples.

    Args:
        root: Folder of text files.
        examples: How many examples to keep per character.

    Returns:
        Character -> statistics.
    """
    stats: dict[str, CharacterStats] = {}
    for path in list_text_files(root):
        text = read_text(path)
        found = Counter(UNUSUAL.findall(text))
        if not found:
            continue
        relative = path.relative_to(root).as_posix()
        for character, count in found.items():
            entry = stats.get(character)
            if entry is None:
                name = unicodedata.name(character, "")
                code = f"U+{ord(character):04X}"
                entry = stats[character] = CharacterStats(character, code, name, kind_of(character))
            entry.count += count
            entry.documents += 1
            if len(entry.examples) < examples:
                _add_example(entry, text, character, relative, path)
    return stats


def _add_example(
    entry: CharacterStats, text: str, character: str, relative: str, path: Path
) -> None:
    """Add the first occurrence in a file as an example, unless its year is already shown."""
    year = relative.split("/", 1)[0]
    if any(example.year == year for example in entry.examples):
        return
    index = text.index(character)
    line_start = text.rfind("\n", 0, index) + 1
    line_end = text.find("\n", index)
    line_end = len(text) if line_end < 0 else line_end
    before = text[max(line_start, index - CONTEXT_WIDTH) : index]
    after = text[index + 1 : min(line_end, index + 1 + CONTEXT_WIDTH)]
    entry.examples.append(
        Example(relative, file_link(path), text.count("\n", 0, index) + 1, year, before, after)
    )


def build_character_page(stats: dict[str, CharacterStats], storage_key: str) -> str:
    """Build the HTML overview.

    Args:
        stats: The result of `scan_characters`.
        storage_key: Name under which the browser keeps the decisions.

    Returns:
        The HTML page, which is self-contained.
    """
    template = Path(str(resources.files("hu_legal_cleaning") / "data" / "characters_template.html"))
    ordered = sorted(stats.values(), key=lambda entry: (entry.kind, -entry.count))
    data = json.dumps([asdict(entry) for entry in ordered], ensure_ascii=False)
    # "</" inside the JSON would end the script block early.
    data = data.replace("</", "<\\/")
    return (
        template.read_text(encoding="utf-8")
        .replace("<!--TITLE-->", PAGE_TITLE)
        .replace("<!--STORAGE-KEY-->", storage_key)
        .replace("/*CHARACTERS*/[]", data)
    )
