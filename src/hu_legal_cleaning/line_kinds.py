"""Tell what kind of line a line of a court decision is, for joining wrapped lines.

Decision texts break lines both at paragraph ends and in the middle of sentences. Two
questions decide whether a line break can be removed:

- Does the line above end a sentence? A final dot after an abbreviation ("hrsz."), an
  ordinal or date number ("2015.") or a roman numeral ("III.") does not.
- Why does the next line start in lowercase? A list item, signature line, anonymisation
  placeholder, bullet, letter-spaced heading or blank form field is a line of its own;
  anything else may continue the line above.

`unwrap` uses these answers to join the lines of hard-wrapped decisions.
"""

import re

from hu_legal_cleaning.abbreviations import load_corpus_abbreviations, load_statute_abbreviations

UPPER = "A-ZÁÉÍÓÖŐÚÜŰ"
LOWER = "a-záéíóöőúüű"
# A sentence end, optionally followed by closing quotes or brackets, at the end of a line.
TERMINAL_END = re.compile(r"[.!?:;][\"”»)\]]*\s*$")
NUMBER = re.compile(r"[\d.,/-]+(?:[A-Z])?")  # "22.", "2008.", "1/B."
ROMAN = re.compile(r"[IVXLC]+")
LOOKAHEAD_CHARACTERS = 40

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

# Causes of a lowercase line start that make the line a unit of its own.
STANDALONE_CAUSES = {
    "list_item", "signature_block", "anonymiser_placeholder", "bullet_marker",
    "letter_spaced_heading", "blank_form_fill",
}  # fmt: skip

STATUTES = load_statute_abbreviations()
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


def lowercase_start_cause(previous: str, line: str) -> str:
    """Return the most likely reason why a line starts in lowercase.

    The answer is a rule-based guess, not a verdict. Reasons:
    "letter_spaced_heading", "bullet_marker", "anonymiser_placeholder",
    "signature_block", "wrap_after_abbrev_or_number", "blank_form_fill", "list_item",
    "wrap_damage", "role_or_article_start", "after_colon_semicolon" or "other".

    Args:
        previous: The line before.
        line: The line that starts in lowercase.
    """
    first_word = line.split()[0].lower().rstrip(":.,")
    last_word = previous.split()[-1] if previous.split() else ""
    head = line[:LOOKAHEAD_CHARACTERS]
    spaced_words = line[:30].split()[:4]
    if SPACED_HEADING.match(head) and all(len(w) == 1 or w in ":,." for w in spaced_words):
        return "letter_spaced_heading"
    if BULLET.match(line):
        return "bullet_marker"
    if PLACEHOLDER.search(line[:60]) or PLACE_PLACEHOLDER.match(first_word):
        return "anonymiser_placeholder"
    is_signature = first_word in SIGNATURE_WORDS or first_word == "dr"
    if is_signature or SIGNATURE_LINE.match(line) or SIGNATURE_END.search(previous):
        return "signature_block"
    last_bare = last_word.rstrip(".")
    is_dotted = last_word.endswith(".")
    if is_dotted and (is_abbreviation(last_word) or NUMBER_OR_ROMAN.fullmatch(last_bare)):
        return "wrap_after_abbrev_or_number"
    if FORM_BLANK_START.match(line) or FORM_BLANK_END.search(previous):
        return "blank_form_fill"
    if LIST_ITEM.match(line):
        return "list_item"
    if SHORT_FRAGMENT.fullmatch(first_word) and first_word not in ORDINARY_SHORT_WORDS:
        return "wrap_damage"
    if re.match(ROLE_WORDS, first_word) or first_word in {"a", "az"}:
        return "role_or_article_start"
    if previous.rstrip().endswith((";", ":")):
        return "after_colon_semicolon"
    return "other"
