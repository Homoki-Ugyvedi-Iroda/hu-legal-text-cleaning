"""Join the lines of hard-wrapped decisions back into sentences.

Most converted decisions hold one paragraph per line. A small share (about 1.5% in BHGY)
was wrapped at a fixed width of roughly 90-115 characters, so that sentences run over
several lines ("Az ítélet ellen ... van helye, melyet jelen" / "bíróságnál lehet ...").

Line breaks inside a sentence also occur in ordinary files, but there they are nearly
always layout that is kept: headings ("meghozta a következő" / "ítéletet:"), the
operative part ("vádlott" / "bűnös"), party blocks and signatures. So the step only runs
on files that are wrapped throughout, recognised by many lines that end mid-sentence and
continue in lowercase on the next line, and by hardly any line much longer than the others.

In such a file a line is joined to the next one when there is no blank line between them,
the line does not end a sentence, the next line is not a list item, signature, heading or
table row, and either:

- the next line starts in lowercase and the line is at least half the wrap width, or
- the next line starts in uppercase and the line is close to the wrap width (a name or
  capitalised word carried over to the next line).

A line that ends a sentence is never joined, even at full width: the next line may start
a new paragraph, and the break keeps the sentence boundary either way.
"""

import re
import statistics
from collections import Counter
from dataclasses import dataclass

from hu_legal_cleaning.line_kinds import (
    STANDALONE_CAUSES,
    TERMINAL_END,
    ends_in_abbreviation,
    lowercase_start_cause,
)

MIN_WRAPPED_LINES = 10
MIN_WRAPPED_SHARE = 0.1
# In a file wrapped at a fixed width, hardly any line is much longer than that width; in a
# file with one paragraph per line, many are.
LONG_LINE_WIDTH = 1.3
MAX_LONG_LINE_SHARE = 0.1
LOWERCASE_JOIN_WIDTH = 0.5
UPPERCASE_JOIN_WIDTH = 0.8
# Words that stand on a line of their own as a heading or as a verdict in the operative
# part, even when the line before reads on into them.
LAYOUT_LINE = re.compile(
    r"^(?:ítélet|ítéletet|ítélete|végzés|végzést|végzése|határozat|határozatot|indokolás"
    r"|bűnös|nem bűnös)[:.!]?$",
    re.IGNORECASE,
)
TABLE_CELL_SEPARATOR = " | "
PLACEHOLDER_CAUSE = "anonymiser_placeholder"
LIST_ITEM_CAUSE = "list_item"
SIGNATURE_CAUSE = "signature_block"
PARAGRAPH_REFERENCE_END = re.compile(r"bekezdés\w*$")
# A point label followed by "pont" ("bd) alpontjára", "h) pont]") or a unit ("km/h") reads
# on in the sentence; only a label that opens an item stands on its own.
NOT_A_LIST_ITEM = re.compile(r"^\(?[a-z]{1,2}\.?\)\s*\]?\s*(?:al)?pont|^[a-z]{1,2}/[a-z]")
MAX_SIGNATURE_LINE = 40
# A line that opens with the article "A" or "Az" starts a new sentence; the full stop before
# it is missing in the source, so the break is a paragraph end.
SENTENCE_OPENER = re.compile(r"^Az? ")
LOWERCASE_JOIN = "joined, lowercase continuation"
UPPERCASE_JOIN = "joined, capitalised word carried over"


@dataclass
class WrapProfile:
    """How a file is wrapped.

    Attributes:
        text_lines: Lines that are not blank.
        wrapped_lines: Lines that end mid-sentence and continue in lowercase on the next line.
        width: The typical length of those lines, taken as the wrap width; 0 if none.
        long_lines: Lines more than LONG_LINE_WIDTH times the wrap width.
    """

    text_lines: int
    wrapped_lines: int
    width: int
    long_lines: int

    @property
    def is_hard_wrapped(self) -> bool:
        """Return True if the file is wrapped throughout, not just in its layout."""
        return (
            self.wrapped_lines >= MIN_WRAPPED_LINES
            and self.wrapped_lines >= MIN_WRAPPED_SHARE * self.text_lines
            and self.long_lines <= MAX_LONG_LINE_SHARE * self.text_lines
        )


def is_open(line: str) -> bool:
    """Return True if a line does not end a sentence (an abbreviation or number does not)."""
    return not TERMINAL_END.search(line) or ends_in_abbreviation(line)


def _is_layout_pair(line: str, following: str) -> bool:
    """Return True if the break between two lines is layout that must stay."""
    if LAYOUT_LINE.match(following) or following.isupper():
        return True
    if TABLE_CELL_SEPARATOR in line or TABLE_CELL_SEPARATOR in following:
        return True
    if not following[:1].islower():
        return False
    cause = lowercase_start_cause(line, following)
    # In running text a placeholder ("tanú16", "cím33") is just a word of the sentence, and
    # "(3) bekezdés" / "b) pontja" is a reference, not a list item.
    if cause == PLACEHOLDER_CAUSE:
        return False
    is_reference = PARAGRAPH_REFERENCE_END.search(line) or NOT_A_LIST_ITEM.match(following)
    if cause == LIST_ITEM_CAUSE and is_reference:
        return False
    # "bírósági" or "bíró" opening a long line is a word of the sentence, not a signature.
    if cause == SIGNATURE_CAUSE and len(following) > MAX_SIGNATURE_LINE:
        return False
    return cause in STANDALONE_CAUSES


def _is_lowercase_continuation(line: str, following: str) -> bool:
    return bool(line) and bool(following) and following[:1].islower() and is_open(line)


def profile_wrapping(lines: list[str]) -> WrapProfile:
    """Measure how a text is wrapped.

    Args:
        lines: The lines of the text, without line endings.

    Returns:
        The number of text lines and wrapped lines, and the estimated wrap width.
    """
    stripped = [line.strip() for line in lines]
    wrapped_lengths = [
        len(line)
        for line, following in zip(stripped, stripped[1:], strict=False)
        if _is_lowercase_continuation(line, following) and not _is_layout_pair(line, following)
    ]
    width = int(statistics.median(wrapped_lengths)) if wrapped_lengths else 0
    text_lines = [line for line in stripped if line]
    long_lines = sum(len(line) > LONG_LINE_WIDTH * width for line in text_lines)
    return WrapProfile(len(text_lines), len(wrapped_lengths), width, long_lines)


def join_kind(line: str, following: str, width: int) -> str | None:
    """Return why two adjacent lines of a hard-wrapped file are joined, or None to keep them.

    Args:
        line: The line, without surrounding spaces.
        following: The next line, without surrounding spaces; empty for a blank line.
        width: The file's wrap width.
    """
    if not line or not following or not is_open(line) or _is_layout_pair(line, following):
        return None
    if following[:1].islower() and len(line) >= LOWERCASE_JOIN_WIDTH * width:
        return LOWERCASE_JOIN
    is_carried_over = following[:1].isupper() and not SENTENCE_OPENER.match(following)
    if is_carried_over and len(line) >= UPPERCASE_JOIN_WIDTH * width:
        return UPPERCASE_JOIN
    return None


def unwrap_lines(text: str) -> tuple[str, Counter[str], WrapProfile]:
    """Join the wrapped lines of a hard-wrapped text; other texts are returned unchanged.

    Args:
        text: The text; LF or CRLF line endings are kept.

    Returns:
        The new text, the number of joins per kind, and the file's wrap profile.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    profile = profile_wrapping(lines)
    joins: Counter[str] = Counter()
    if not profile.is_hard_wrapped:
        return text, joins, profile
    output = [lines[0]]
    # A joined line grows past the wrap width, so the length test uses the original line.
    for line, following in zip(lines, lines[1:], strict=False):
        kind = join_kind(line.strip(), following.strip(), profile.width)
        if kind:
            output[-1] = output[-1].rstrip() + " " + following.strip()
            joins[kind] += 1
        else:
            output.append(following)
    return newline.join(output), joins, profile
