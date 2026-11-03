"""Remove page numbers and running case-number headers left inside the text.

Converted decisions keep some of the page layout of the printed original: a page number
between two paragraphs ("- 2 -", "3 / 6 oldal", a bare "4"), or the case number repeated
at the top of every page ("Pf.III.20.106/2013/8. szám"). Both interrupt the text, often in
the middle of a sentence.

The rules follow a review of the BHGY corpus:

- page numbers are removed: a number between single dashes ("- 2 -", "-2-"), "x / y oldal",
  "x/y." and "x/y" when x is not larger than y (page x of y), and a bare number of one to
  three digits on its own line; an "x/y." line next to lines that start with the same kind
  of reference ("1/12. L.A.", "II/5. F.Z.") is a list item and stays;
- a line that is only a case number is removed when it repeats an earlier line of the
  file: the first occurrence is the decision's own heading and stays;
- everything else stays, even if it repeats: court names, headings, role words, and
  separator lines made of several dashes ("--- 0 ---").

Where a removed line stood inside a sentence (the kept line before it has no sentence end
and the kept line after it starts in lowercase), the two halves are joined with a space.
"""

import re
from collections import Counter
from dataclasses import dataclass

DASHED_PAGE_NUMBER = re.compile(r"^- ?\d{1,3} ?-$")
PAGES_OF_TOTAL = re.compile(r"^(?P<page>\d{1,3}) ?/ ?(?P<total>\d{1,3})(?P<rest>\.| ?oldal)?$")
BARE_NUMBER = re.compile(r"^\d{1,3}$")
# A line that starts with a reference like "1/12." or "II/5." ("1/12. L.A."): an "x/y." line
# next to such lines is an item of the same list, e.g. a defendant's number, not a page.
REFERENCE_START = re.compile(r"^-? ?(?:\d{1,3}|[IVX]{1,4})/\d{1,3}\.")
LIST_NEIGHBOURHOOD = 2
# A case number on its own line: "Pf.III.20.106/2013/8. szám", "4.K.700.396/2020/38.",
# "Bf.I.181/2012/5.", "8.G.15-13-040051/17. Ítélet".
CASE_NUMBER_LINE = re.compile(
    r"^(?:\d{1,2}\. ?)?[A-ZÁÉ][a-zé]{0,4}\. ?(?:[IVX]{1,4}\. ?)?"
    r"(?:\d[\d. ]*/\d{4}/ ?\d{1,4}(?:/[IVX]{1,3})?|\d{1,2}-\d{2}-\d{4,6}/\d{1,4})"
    r"\.? ?(?:szám|Ítélet|Végzés)?\.?$"
)
SENTENCE_END = tuple(".!?:;")
# A line after a page break that starts a list item ("a) ...", "ba) ...") is a new item,
# not the rest of the sentence before the break.
LIST_ITEM_START = re.compile(r"^[a-z]{1,2}[).]\s")
PAGE_NUMBER = "page number"
CASE_NUMBER = "repeated case number"
REJOINED = "sentence rejoined"


@dataclass
class Removal:
    """One removed line.

    Attributes:
        line_number: The line in the input, counted from 1.
        text: The removed line, without surrounding spaces.
        kind: PAGE_NUMBER or CASE_NUMBER.
    """

    line_number: int
    text: str
    kind: str


def is_page_number(line: str) -> bool:
    """Return True for a line that is only a page number ("- 2 -", "3 / 6 oldal", "4")."""
    text = line.strip()
    if DASHED_PAGE_NUMBER.match(text) or BARE_NUMBER.match(text):
        return True
    match = PAGES_OF_TOTAL.match(text)
    if not match:
        return False
    # "023/6" is a parcel number, not page 23 of 6.
    page, total = match.group("page"), match.group("total")
    return match.group("rest") == "." or (not page.startswith("0") and int(page) <= int(total))


def _case_key(line: str) -> str | None:
    """Return the case number of a case-number line with spaces removed, or None."""
    text = line.strip()
    return text.replace(" ", "") if CASE_NUMBER_LINE.match(text) else None


def _is_in_reference_list(lines: list[str], index: int) -> bool:
    """Return True for an "x/y." line next to other lines that start with such a reference."""
    match = PAGES_OF_TOTAL.match(lines[index].strip())
    if not match or match.group("rest") != ".":
        return False
    start, end = max(0, index - LIST_NEIGHBOURHOOD), index + LIST_NEIGHBOURHOOD + 1
    neighbours = [line.strip() for line in lines[start:index] + lines[index + 1 : end]]
    return any(REFERENCE_START.match(line) and line != lines[index].strip() for line in neighbours)


def find_removals(lines: list[str]) -> list[Removal]:
    """Return the page numbers and repeated case-number lines of a text, in line order."""
    removals = []
    seen_case_numbers = set()
    for index, line in enumerate(lines):
        if is_page_number(line) and not _is_in_reference_list(lines, index):
            removals.append(Removal(index + 1, line.strip(), PAGE_NUMBER))
            continue
        key = _case_key(line)
        if key is None:
            continue
        if key in seen_case_numbers:
            removals.append(Removal(index + 1, line.strip(), CASE_NUMBER))
        seen_case_numbers.add(key)
    return removals


def _should_join(before: str, after: str) -> bool:
    before, after = before.strip(), after.strip()
    if LIST_ITEM_START.match(after):
        return False
    return (
        bool(before) and bool(after) and not before.endswith(SENTENCE_END) and after[:1].islower()
    )


def remove_page_furniture(text: str) -> tuple[str, Counter[str], list[Removal]]:
    """Remove page numbers and repeated case-number lines, rejoining split sentences.

    Args:
        text: The text; LF or CRLF line endings are kept.

    Returns:
        The new text, the number of changes per kind (PAGE_NUMBER, CASE_NUMBER, REJOINED)
        and the removed lines.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    removals = find_removals(lines)
    changes: Counter[str] = Counter(removal.kind for removal in removals)
    if not removals:
        return text, changes, removals
    removed = {removal.line_number - 1 for removal in removals}
    output: list[str] = []
    index = 0
    while index < len(lines):
        if index not in removed:
            output.append(lines[index])
            index += 1
            continue
        # A run of blank and removed lines between two kept lines: the blank lines before
        # the removed line are already in the output, so take them back first.
        had_blank = False
        while output and not output[-1].strip():
            output.pop()
            had_blank = True
        end = index
        while end < len(lines) and (end in removed or not lines[end].strip()):
            had_blank = had_blank or not lines[end].strip()
            end += 1
        last_kept = output[-1] if output else ""
        next_kept = lines[end] if end < len(lines) else ""
        if _should_join(last_kept, next_kept):
            output[-1] = output[-1].rstrip() + " " + next_kept.lstrip()
            changes[REJOINED] += 1
            end += 1
        elif had_blank and output:
            output.append("")
        index = end
    return newline.join(output), changes, removals
