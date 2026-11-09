"""Build a keyboard-driven HTML page on which a person reviews candidate corrections.

Every automatic rule in this package produces candidates that a person must confirm:
words to correct, split words to join, damaged line starts to fix. The page shows one
item at a time with its context and a link to the original file:

- keys 1, 2, 3 ... choose an answer and move to the next item;
- the arrow keys (or j and k) move between items without answering;
- answers are kept in the browser (localStorage), so the page can be closed and reopened;
- "Export CSV" downloads the answers for the next step of the pipeline.

The page is a single self-contained file with no external scripts, so it also works
offline and from a network drive.
"""

import html
import json
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path

TEMPLATE_FILE = "review_page_template.html"
DATA_PLACEHOLDER = "/*ITEMS*/[]"
TITLE_PLACEHOLDER = "<!--TITLE-->"
OPTIONS_PLACEHOLDER = "/*OPTIONS*/[]"
STORAGE_PLACEHOLDER = "<!--STORAGE-KEY-->"


@dataclass
class Context:
    """One place where a candidate occurs.

    Attributes:
        before: Text before the candidate.
        hit: The candidate as it stands in the text.
        after: Text after the candidate.
        source: Path of the file, shown to the reviewer.
        link: Optional link to open the original document (file:// or https://).
    """

    before: str
    hit: str
    after: str
    source: str
    link: str = ""


@dataclass
class ReviewItem:
    """A candidate for review.

    Attributes:
        key: Identifier written to the exported CSV, e.g. the word.
        title: What the reviewer sees as the heading.
        proposal: The proposed change, e.g. "értett -> Sértett".
        count: How often the candidate occurs.
        contexts: Examples with their source.
    """

    key: str
    title: str
    proposal: str
    count: int
    contexts: list[Context] = field(default_factory=list)


def _as_script_json(value: object) -> str:
    # "</" inside a <script> block would end the block early, so it is escaped.
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def build_review_page(
    items: list[ReviewItem], options: list[str], title: str, storage_key: str
) -> str:
    """Return the HTML of a review page.

    Args:
        items: The candidates, in the order they should be reviewed.
        options: The possible answers, e.g. ["apply", "no", "unsure"]; at most nine.
        title: Heading and window title of the page.
        storage_key: Name under which the browser keeps the answers; also the name of
            the exported file. Use a different key for each review.

    Returns:
        The complete HTML document.
    """
    # importlib.resources finds data files inside an installed package.
    template = (resources.files("hu_legal_cleaning") / "data" / TEMPLATE_FILE).read_text("utf-8")
    page = template.replace(DATA_PLACEHOLDER, _as_script_json([asdict(i) for i in items]))
    page = page.replace(OPTIONS_PLACEHOLDER, _as_script_json(options))
    page = page.replace(TITLE_PLACEHOLDER, html.escape(title))
    return page.replace(STORAGE_PLACEHOLDER, html.escape(storage_key))


def file_link(path: Path) -> str:
    """Return a file:// link that opens a local file from the review page."""
    return path.resolve().as_uri()


ORIGINAL_SUFFIXES = (".rtf", ".docx", ".doc", ".pdf")


def original_of(relative_text: str, originals: Path) -> Path | None:
    """Return the original document a converted text file was made from, if it exists.

    Args:
        relative_text: Path of the text file relative to its corpus folder, e.g.
            "2006/Court/P.123.txt".
        originals: Folder of the original documents, with the same layout.

    Returns:
        The original file with the same stem (.rtf, .docx, ...), or None.
    """
    stem = originals / Path(relative_text).with_suffix("")
    for suffix in ORIGINAL_SUFFIXES:
        candidate = stem.with_name(stem.name + suffix)
        if candidate.exists():
            return candidate
    return None
