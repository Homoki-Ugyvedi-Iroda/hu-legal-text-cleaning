"""Join letter-spaced words and tidy whitespace.

Headings in court decisions are often spaced out letter by letter: "I n d o k o l á s",
"í t é l e t e t", "b ű n ö s". Search, spell checking and sentence splitting see single
letters instead of a word. `join_letter_spaced` joins them where the spell checker (or
whatever `is_known` checks) knows the result, so runs of initials or decorative letters
("o o o o o") stay as they are.

A spaced-out phrase is read as pieces separated by two or more spaces. Usually each piece
is one word ("M a g y a r  K ö z t á r s a s á g"), but some sources break a word with a
double space too ("í t é l  e t e t"), so neighbouring pieces are merged when the merged
word is known. A piece that is unknown on its own gets three more tries:

- split before each capital that follows a small letter, where a single space separated
  two words ("M a g y a r K ö z t á r s a s á g" -> "Magyar Köztársaság");
- "Í" for a leading "I", as typewritten capitals often lost the accent ("I t é l e t");
- the article "a" split off the end ("K ö t e l e z i a felperest").

The double space is the only sign of a word boundary, so `join_letter_spaced` must run
before `normalise_whitespace` collapses the spaces.
"""

import re
from collections import Counter
from collections.abc import Callable

MIN_SPACED_LETTERS = 4
# Merged words longer than this many pieces are not tried; real words have one or two.
MAX_PIECES_PER_WORD = 4
# A phrase of single letters separated by spaces or tabs, not touching another letter:
# "I n d o k o l á s" in "I n d o k o l á s:". [^\W\d_] is any letter, accented or not.
SPACED_PHRASE = re.compile(
    rf"(?<![^\W\d_])[^\W\d_](?:[ \t]+[^\W\d_]){{{MIN_SPACED_LETTERS - 1},}}(?![^\W\d_])"
)
# The spaced-out style also puts a space before the punctuation after the word
# ("I n d o k o l á s :"); it is dropped once the word is joined.
GAP_BEFORE_PUNCTUATION = re.compile(r"[ 	]+(?=[:.,;!?])")
PIECE_GAP = re.compile(r"[ \t]{2,}")
# Split point inside a joined piece: a capital letter right after a small letter.
CAPITAL_AFTER_SMALL = re.compile(r"(?<=[^\W\d_A-ZÁÉÍÓÖŐÚÜŰ])(?=[A-ZÁÉÍÓÖŐÚÜŰ])")
UNACCENTED_CAPITAL_I = "I"
ACCENTED_CAPITAL_I = "Í"
ARTICLE = "a"
# Each part of a split before capitals must be this long, apart from a leading article.
MIN_SPLIT_PART = 3
LINE_BREAK = "\n"
CARRIAGE_RETURN = "\r"


def _pieces(phrase: str) -> list[str]:
    """Return the pieces of a spaced phrase, each with its spaces removed."""
    return [re.sub(r"\s", "", piece) for piece in PIECE_GAP.split(phrase)]


def _piece_variants(piece: str) -> list[str]:
    """Return what an unknown piece may stand for, in the order they are tried."""
    variants = []
    parts = CAPITAL_AFTER_SMALL.split(piece)
    if all(
        len(part) >= MIN_SPLIT_PART or (i == 0 and part == ARTICLE) for i, part in enumerate(parts)
    ):
        variants.append(" ".join(parts))
    if piece.startswith(UNACCENTED_CAPITAL_I):
        variants.append(ACCENTED_CAPITAL_I + piece[1:])
    if piece.endswith(ARTICLE) and len(piece) > MIN_SPACED_LETTERS:
        variants.append(piece[:-1] + " " + ARTICLE)
    return [variant for variant in variants if variant != piece]


def letter_spaced_forms(text: str) -> set[str]:
    """Return every word form `join_letter_spaced` may ask `is_known` about.

    Args:
        text: The text.

    Returns:
        Single words, for one spell-checker call.
    """
    forms = set()
    for match in SPACED_PHRASE.finditer(text):
        pieces = _pieces(match.group(0))
        for start in range(len(pieces)):
            for end in range(start + 1, min(start + MAX_PIECES_PER_WORD, len(pieces)) + 1):
                forms.add("".join(pieces[start:end]))
            for variant in _piece_variants(pieces[start]):
                forms.update(variant.split(" "))
    return forms


def _resolve_piece(piece: str, is_known: Callable[[str], bool]) -> str | None:
    """Return the word or words a single piece becomes, or None to leave it spaced."""
    if len(piece) < MIN_SPACED_LETTERS:
        return None
    if is_known(piece):
        return piece
    for variant in _piece_variants(piece):
        if all(is_known(word) for word in variant.split(" ")):
            return variant
    return None


def _can_merge(
    pieces: list[str], is_known: Callable[[str], bool], is_common: Callable[[str], bool]
) -> bool:
    """Return True if neighbouring pieces should be written as one word.

    Two pieces that are words in their own right are merged only if the merged word is
    common, because the spell checker also accepts compounds made of two words written
    apart on purpose ("kijavító végzést", "Köztársaság nevében").
    """
    merged = "".join(pieces)
    if len(merged) < MIN_SPACED_LETTERS or not is_known(merged):
        return False
    if all(len(piece) >= MIN_SPACED_LETTERS and is_known(piece) for piece in pieces):
        return is_common(merged)
    return True


def _join_phrase(
    phrase: str, is_known: Callable[[str], bool], is_common: Callable[[str], bool]
) -> tuple[str, list[str]]:
    """Return the rewritten phrase and the words it joined."""
    originals = PIECE_GAP.split(phrase)
    pieces = _pieces(phrase)
    output = []
    joined = []
    start = 0
    while start < len(pieces):
        last = min(start + MAX_PIECES_PER_WORD, len(pieces))
        merged = next(
            (
                end
                for end in range(last, start + 1, -1)
                if _can_merge(pieces[start:end], is_known, is_common)
            ),
            None,
        )
        if merged:
            word = "".join(pieces[start:merged])
            start_next = merged
        else:
            word = _resolve_piece(pieces[start], is_known)
            start_next = start + 1
        if word is None:
            output.append(originals[start])
        else:
            output.append(word)
            joined.append(word)
        start = start_next
    return " ".join(output), joined


def join_letter_spaced(
    text: str,
    is_known: Callable[[str], bool],
    is_common: Callable[[str], bool] = lambda word: False,
) -> tuple[str, Counter[str]]:
    """Join letter-spaced words that `is_known` accepts once joined.

    Args:
        text: The text.
        is_known: Returns True for a known word, e.g. from the spell checker.
        is_common: Returns True for a word common enough in the corpus to merge two pieces
            that are words on their own ("ítél" + "etet" -> "ítéletet"). By default such
            pieces stay separate words.

    Returns:
        The new text and how often each joined form was written.
    """
    changes: Counter[str] = Counter()
    pieces = []
    position = 0
    for match in SPACED_PHRASE.finditer(text):
        rewritten, joined = _join_phrase(match.group(0), is_known, is_common)
        if not joined:
            continue
        changes.update(joined)
        pieces.append(text[position : match.start()])
        pieces.append(rewritten)
        position = match.end()
        gap = GAP_BEFORE_PUNCTUATION.match(text, position)
        if gap:
            position = gap.end()
    pieces.append(text[position:])
    return "".join(pieces), changes


def normalise_whitespace(text: str) -> tuple[str, int]:
    """Remove spaces at the start and end of lines and collapse runs of spaces and tabs.

    Blank lines and line endings (LF or CRLF) are kept, as blank lines mark paragraphs.

    Args:
        text: The text.

    Returns:
        The new text and the number of lines changed.
    """
    lines = text.split(LINE_BREAK)
    changed = 0
    for index, line in enumerate(lines):
        has_carriage_return = line.endswith(CARRIAGE_RETURN)
        content = line[:-1] if has_carriage_return else line
        # str.split() without arguments splits on any run of whitespace and drops the ends.
        tidy = " ".join(content.split())
        if tidy != content:
            changed += 1
            lines[index] = tidy + (CARRIAGE_RETURN if has_carriage_return else "")
    return LINE_BREAK.join(lines), changed


# Heading words that the spaced-out style is used for; a damaged spaced run at the start
# of a line is compared with these.
SPACED_HEADINGS = (
    "indokolás", "ítélet", "ítéletet", "ítélete", "részítéletet", "végzés", "végzést",
    "végzése", "bűnös", "bűnösök", "határozat", "határozatot", "záradék", "tényállás",
    "tényállást", "elutasítja", "felmenti", "kötelezi", "megszünteti", "helybenhagyja",
    "megváltoztatja", "ítéli",
)  # fmt: skip
# A spaced run at the start of a line, before punctuation or the end of the line: tokens of
# one to four characters ("I N D OKOL Á S", "I n d o k o 1 á s", "b ü n ö s: ...").
SPACED_LINE_START = re.compile(r"^(?P<run>[^\s:.!]{1,4}(?: [^\s:.!]{1,4}){2,})(?= ?[:.!]| *$)")
MIN_SINGLE_LETTER_SHARE = 0.5
# Confusions folded away before comparing with a heading: OCR reads "l" as "1", "I" or
# "i", and typewritten text mixes up "ű"/"ü" and "ő"/"ö".
HEADING_FOLD = str.maketrans({"1": "l", "i": "l", "ű": "ü", "ő": "ö"})
MIN_LENGTH_FOR_ONE_EDIT = 6


def _fold(word: str) -> str:
    return word.lower().translate(HEADING_FOLD)


def _differs_by_one_edit(first: str, second: str) -> bool:
    """Return True if one insertion, deletion or substitution turns first into second."""
    if abs(len(first) - len(second)) > 1 or first == second:
        return False
    if len(first) == len(second):
        return sum(a != b for a, b in zip(first, second, strict=True)) == 1
    shorter, longer = sorted((first, second), key=len)
    return any(longer[:i] + longer[i + 1 :] == shorter for i in range(len(longer)))


def _matching_heading(letters: str) -> str | None:
    folded = _fold(letters)
    exact = [heading for heading in SPACED_HEADINGS if _fold(heading) == folded]
    if exact:
        return exact[0]
    if len(folded) < MIN_LENGTH_FOR_ONE_EDIT:
        return None
    # An extra letter at the end is a separate word, e.g. the numeral in "Indokolás I.".
    close = [
        heading
        for heading in SPACED_HEADINGS
        if _differs_by_one_edit(_fold(heading), folded) and folded[:-1] != _fold(heading)
    ]
    return close[0] if len(close) == 1 else None


def _in_case_of(heading: str, letters: str) -> str:
    capitals = sum(c.isupper() for c in letters)
    if capitals > len(letters) / 2:
        return heading.upper()
    # A lost first letter was a heading's capital ("n d o k o l á s" for "Indokolás").
    lost_first_letter = len(letters) < len(heading) and _fold(letters)[0] != _fold(heading)[0]
    return heading.capitalize() if letters[0].isupper() or lost_first_letter else heading


def repair_spaced_headings(text: str) -> tuple[str, Counter[str]]:
    """Replace damaged spaced-out headings at the start of a line with the heading word.

    Covers what `join_letter_spaced` leaves: irregular gaps ("I N D OKOL Á S"), OCR
    confusions ("I n d o k o 1 á s"), a lost letter ("n d o k o l á s") and "ü"/"ö" for
    "ű"/"ő" ("b ü n ö s"). A run is replaced only if it matches a word of
    `SPACED_HEADINGS` after folding those confusions, or is one letter away from exactly
    one of them.

    Args:
        text: The text.

    Returns:
        The new text and how often each heading was written.
    """
    changes: Counter[str] = Counter()
    lines = text.split(LINE_BREAK)
    for index, line in enumerate(lines):
        match = SPACED_LINE_START.match(line)
        if not match:
            continue
        tokens = match.group("run").split(" ")
        if sum(len(token) == 1 for token in tokens) < len(tokens) * MIN_SINGLE_LETTER_SHARE:
            continue
        letters = "".join(tokens)
        heading = _matching_heading(letters)
        if heading is None:
            continue
        written = _in_case_of(heading, letters)
        changes[written] += 1
        rest = line[match.end() :]
        lines[index] = written + (rest[1:] if rest.startswith(" ") and rest[1:2] in ":.!" else rest)
    return LINE_BREAK.join(lines), changes


# "bűnös" spaced out in the middle of a sentence ("b ü n ö s a Btk. 234. §-ába ütköző"),
# where `repair_spaced_headings` does not look; "ü"/"ö" stand for "ű"/"ő".
SPACED_GUILTY = re.compile(r"(?<![^\W\d_])([bB]) [üű] n [öő] s(?P<plural> [öő] k)?(?![^\W\d_])")


def repair_spaced_guilty(text: str) -> tuple[str, int]:
    """Write a spaced-out "b ü n ö s" or "b ű n ő s ö k" anywhere as "bűnös" or "bűnösök".

    Args:
        text: The text.

    Returns:
        The new text and the number of replacements.
    """

    def replace(match: re.Match[str]) -> str:
        return match.group(1) + "űnös" + ("ök" if match.group("plural") else "")

    return SPACED_GUILTY.subn(replace, text)
