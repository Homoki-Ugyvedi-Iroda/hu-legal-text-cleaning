"""Rule-based sentence splitter for Hungarian court decisions.

Court decision texts mix sentences with headings, list items, signature lines and
anonymisation placeholders, and many lines are wrapped in the middle of a sentence.
The splitter works in two steps:

1. Join wrapped lines into paragraphs: a line that starts in lowercase continues the
   previous line, unless the previous line is finished, or the lowercase line is a
   list item, signature, placeholder, bullet, spaced-out heading or blank form field.
2. Split each paragraph at ". ", "! ", "? " before a capital or digit, except after an
   abbreviation, an initial, an ordinal or date number, a roman numeral or "§".

On a gold set of 40 passages (140 segments) it reached a boundary F1 of 99.0; see
docs/sentence-splitting.md.
"""

import re

from hu_legal_cleaning.abbreviations import load_corpus_abbreviations, load_statute_abbreviations

UPPER = "A-ZÁÉÍÓÖŐÚÜŰ"
LOWER = "a-záéíóöőúüű"
SENTENCE_END = re.compile(r"([.!?…]+[\"”»)\]]*)(\s+)(?=[\"„(\[]*[" + UPPER + r"0-9\[])")
TERMINAL_END = re.compile(r"[.!?:;][\"”»)\]]*\s*$")
NUMBER = re.compile(r"[\d.,/-]+(?:[A-Z])?")  # "22.", "2008.", "1/B."
ROMAN = re.compile(r"[IVXLC]+")
INITIALS = re.compile(r"(?:[" + UPPER + r"][" + LOWER + r"]?\.)+[" + UPPER + r"]?")
CAPITALISED_WORD = re.compile("[" + UPPER + "][" + LOWER + "]{2,}")
OPENING_MARKS = '([„"»'
DOT_CLOSINGS = (".", ".)", ".]")
SECTION_FOLLOWERS = "(0123456789" + "abcdefghijklmnopqrstuvwxyzáéíóöőúüű"
LOOKAHEAD_CHARACTERS = 40
SHORT_STATUTE_LENGTH = 3

# Words that look like abbreviations in the corpus counts but are placeholders
# ("neve.", "címe.") and so may end a sentence.
NOT_ABBREVIATIONS = {"neve", "címe", "száma", "szám", "cím", "ügyszám", "ssz"}
# "be" is an ordinary word in lowercase; the statute "Be." is matched case-sensitively.
CASE_SENSITIVE_ONLY = {"be"}

ROLE_WORDS = (
    r"(?:vádlott|terhelt|sértett|tanú|felperes|alperes|felügyelő|ülnök|magánvádló"
    r"|pótmagánvádló|kérelmező|kérelmezett|panaszos)"
)
SIGNATURE_WORDS = {
    "bíró", "tisztviselő", "előadó", "kiadó", "ülnök", "jegyző", "titkár", "elnök",
    "bírósági", "törvényszéki", "tanácselnök", "eljáró",
}  # fmt: skip
SIGNATURE_LINE = re.compile(r"^(?:dr\.?\s+)?[\w.\- ]{3,60}\s+s\.?\s?k\.?\b", re.IGNORECASE)
SIGNATURE_END = re.compile(r"s\.?\s?k\.?\s*$|kiadmány hiteléül", re.IGNORECASE)
LIST_ITEM = re.compile(r"^\(?[a-z]{1,2}[.]?[)/]|^[a-z]\s?[.)]\s")
# Anonymisation placeholders: "név9:", "tanú 41", "ülnök1", "nevevádlott".
PLACEHOLDER = re.compile(
    r"^(?:név|cím|szám|hely|személy|helységnév|cégnév|szakértő|tanu)\s?\d+|^x{4,}|\b"
    + ROLE_WORDS
    + r"\s?\d+|\bneve"
    + ROLE_WORDS
)
PLACE_PLACEHOLDER = re.compile(r"^(?:település|város|helység)\d*")
SHORT_FRAGMENT = re.compile("[" + LOWER + "]{1,3}")
ORDINARY_SHORT_WORDS = {"a", "az", "és", "de", "is", "ha", "ez", "ő"}
BULLET = re.compile(r"^[ol]\s*(?:[-\t ]|$)")
SPACED_HEADING = re.compile(r"^(?:\S\s+){3,}\S(?:\s|$)")
FORM_BLANK_START = re.compile(r"^[.…]{3,}|^…")
FORM_BLANK_END = re.compile(r"[.…]{3,}\s*$")
NUMBER_OR_ROMAN = re.compile(r"[\d.,/-]+|[IVXLC]+\.?")

# Causes of a lowercase segment start that make the line a unit of its own.
STANDALONE_CAUSES = {
    "list_item", "signature_block", "anonymiser_placeholder", "bullet_marker",
    "letter_spaced_heading", "blank_form_fill",
}  # fmt: skip

STATUTES = load_statute_abbreviations()
SHORT_STATUTES = {statute for statute in STATUTES if len(statute) < SHORT_STATUTE_LENGTH}
LOWERCASE_ABBREVIATIONS = load_corpus_abbreviations() - NOT_ABBREVIATIONS - CASE_SENSITIVE_ONLY


def is_abbreviation(token: str) -> bool:
    """Return True if the word (with or without its final dot) is a known abbreviation."""
    word = token.rstrip(".")
    return word in STATUTES or word.lower() in LOWERCASE_ABBREVIATIONS


def ends_in_abbreviation(line: str) -> bool:
    """Return True if a line ends in a dot after an abbreviation, a number or a roman numeral."""
    words = line.split()
    if not words or not words[-1].endswith("."):
        return False
    word = words[-1].rstrip(".")
    return (
        is_abbreviation(words[-1])
        or NUMBER.fullmatch(word) is not None
        or ROMAN.fullmatch(word) is not None
    )


def lowercase_start_cause(previous: str, segment: str) -> str:
    """Return the most likely reason why a segment starts in lowercase.

    The answer is a rule-based guess for review, not a verdict. Reasons:
    "letter_spaced_heading", "bullet_marker", "anonymiser_placeholder",
    "signature_block", "wrap_after_abbrev_or_number", "blank_form_fill", "list_item",
    "wrap_damage", "role_or_article_start", "after_colon_semicolon" or "other".

    Args:
        previous: The segment before.
        segment: The segment that starts in lowercase.
    """
    first_word = segment.split()[0].lower().rstrip(":.,")
    last_word = previous.split()[-1] if previous.split() else ""
    head = segment[:LOOKAHEAD_CHARACTERS]
    spaced_words = segment[:30].split()[:4]
    if SPACED_HEADING.match(head) and all(len(w) == 1 or w in ":,." for w in spaced_words):
        return "letter_spaced_heading"
    if BULLET.match(segment):
        return "bullet_marker"
    if PLACEHOLDER.search(segment[:60]) or PLACE_PLACEHOLDER.match(first_word):
        return "anonymiser_placeholder"
    is_signature = first_word in SIGNATURE_WORDS or first_word == "dr"
    if is_signature or SIGNATURE_LINE.match(segment) or SIGNATURE_END.search(previous):
        return "signature_block"
    last_bare = last_word.rstrip(".")
    is_dotted = last_word.endswith(".")
    if is_dotted and (is_abbreviation(last_word) or NUMBER_OR_ROMAN.fullmatch(last_bare)):
        return "wrap_after_abbrev_or_number"
    if FORM_BLANK_START.match(segment) or FORM_BLANK_END.search(previous):
        return "blank_form_fill"
    if LIST_ITEM.match(segment):
        return "list_item"
    if SHORT_FRAGMENT.fullmatch(first_word) and first_word not in ORDINARY_SHORT_WORDS:
        return "wrap_damage"
    if re.match(ROLE_WORDS, first_word) or first_word in {"a", "az"}:
        return "role_or_article_start"
    if previous.rstrip().endswith((";", ":")):
        return "after_colon_semicolon"
    return "other"


def join_wrapped_lines(text: str) -> list[str]:
    """Group the lines of a text into paragraphs, joining lines wrapped mid-sentence."""
    paragraphs: list[str] = []
    for line in (raw.strip() for raw in text.split("\n")):
        if not line:
            continue
        if paragraphs and line[0].islower():
            previous = paragraphs[-1]
            is_standalone = lowercase_start_cause(previous, line) in STANDALONE_CAUSES
            is_unfinished = not TERMINAL_END.search(previous) or ends_in_abbreviation(previous)
            if not is_standalone and is_unfinished:
                paragraphs[-1] = previous + " " + line
                continue
        paragraphs.append(line)
    return paragraphs


def _is_false_boundary(last: str, closing: str, following: str) -> bool:
    """Return True if the dot after `last` does not end a sentence."""
    word = last.rstrip(".")
    ends_with_dot = closing in DOT_CLOSINGS
    is_initial = (len(word) == 1 and last[:1].isupper()) or INITIALS.fullmatch(last) is not None
    is_number = ends_with_dot and NUMBER.fullmatch(word) is not None
    is_roman = ends_with_dot and ROMAN.fullmatch(word) is not None
    # "228. §." followed by "(1) bek." continues the citation.
    is_section_sign = word.endswith("§") and following[:1] in SECTION_FOLLOWERS
    # A statute name followed by a capitalised word ends the sentence: "... a Ptk. A bíróság".
    statute_ends = (
        word in STATUTES
        and word not in SHORT_STATUTES
        and CAPITALISED_WORD.match(following) is not None
    )
    is_known_abbreviation = is_abbreviation(last) and not statute_ends
    return is_known_abbreviation or is_initial or is_number or is_roman or is_section_sign


def split_paragraph(paragraph: str) -> list[str]:
    """Split one paragraph into sentences."""
    pieces, start = [], 0
    for match in SENTENCE_END.finditer(paragraph):
        before = paragraph[start : match.start(1)].split()
        last = before[-1].lstrip(OPENING_MARKS) if before else ""
        following = paragraph[match.end() : match.end() + LOOKAHEAD_CHARACTERS]
        if _is_false_boundary(last, match.group(1), following):
            continue
        pieces.append(paragraph[start : match.end(1)].strip())
        start = match.end()
    tail = paragraph[start:].strip()
    if tail:
        pieces.append(tail)
    return pieces


def split_sentences(text: str) -> list[str]:
    """Split a decision text into sentences and sentence-like lines.

    Args:
        text: The whole text, with its line breaks.

    Returns:
        Sentences, headings, list items and signature lines, in order.
    """
    return [
        piece
        for paragraph in join_wrapped_lines(text)
        for piece in split_paragraph(paragraph)
        if piece
    ]


def split_with_causes(text: str) -> list[tuple[str, str]]:
    """Split a text and tag every segment that starts in lowercase with its likely cause.

    Args:
        text: The whole text.

    Returns:
        (segment, cause) pairs; the cause is "" for a segment that starts normally.
    """
    segments = split_sentences(text)
    tagged = []
    for index, segment in enumerate(segments):
        starts_lowercase = index > 0 and segment[:1].islower()
        cause = lowercase_start_cause(segments[index - 1], segment) if starts_lowercase else ""
        tagged.append((segment, cause))
    return tagged
