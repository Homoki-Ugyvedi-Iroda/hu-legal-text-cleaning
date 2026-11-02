"""Words split across two lines by a hyphen: "sze-" at the end of a line, "rint" on the next.

Typesetting and OCR leave such splits in the text; search, spell checking and sentence
splitting then see two broken words instead of "szerint". The steps are:

1. `find_hyphen_pairs` lists every (first part, second part) pair in a text.
2. `classify_pair` decides with the spell checker: join, keep the hyphen, or unresolved.
3. `hold_reason` stops the automatic join for patterns that look like a split word but
   are not (spelled-out numbers, a role word before a verdict on the next line).
4. A person reviews the unresolved pairs; `join_hyphenated_lines` applies the decisions.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

LETTERS = "A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű"
LOWER_LETTERS = "a-záéíóöőúüű"
LINE_ENDS_WITH_HYPHEN = re.compile("([" + LETTERS + "]+)-[ \\t]*$")
LINE_STARTS_LOWERCASE = re.compile("^[ \\t]*([" + LOWER_LETTERS + "]+)")

JOIN = "join"
KEEP_HYPHEN = "keep_hyphen"
UNRESOLVED = "unresolved"

# Spelled-out numbers follow their own hyphenation rules ("huszonöt-ezer" is not a
# line-break artefact), so they are never joined automatically.
NUMBER_WORD = re.compile(
    "^(?:egy|kettő|két|három|négy|öt|hat|hét|nyolc|kilenc|tíz|tizen|húsz|huszon|harminc"
    "|negyven|ötven|hatvan|hetven|nyolcvan|kilencven|száz|ezer|millió|milliárd)+$"
)
# A role word at a line end followed by a verdict or a one-letter label on the next line
# is a typographical convention ("vádlott-" / "bűnös"), not a split word.
ROLE_WORDS = {
    "állampolgár", "vádlott", "lakos", "felperesnek", "felperes",
    "alperes", "alperesnek", "terhelt", "sértett",
}  # fmt: skip
LABEL_WORDS = {"bűnös", "fa", "dr"}
MAX_LABEL_LENGTH = 2

# Hungarian writes a long two-letter consonant by doubling only its first letter
# ("ssz" in "összeg"), but hyphenation splits it into two whole digraphs ("ösz-szeg").
# "dzs" is listed first so that it is matched before "zs".
DIGRAPHS = ("dzs", "cs", "dz", "gy", "ly", "ny", "sz", "ty", "zs")
VOWELS = set("aáeéiíoóöőuúüű")
# The question particle is always written with a hyphen ("megfelelnek-e").
QUESTION_PARTICLE = "e"
# Compounds of more than six syllables (and three or more parts) take a hyphen
# ("ingatlan-nyilvántartás"); shorter ones do not, so the spell checker's acceptance of
# a hyphenated form only counts above this length.
MAX_SYLLABLES_WITHOUT_HYPHEN = 6
# The first word of a hyphen that stands before a conjunction ("állag- és értékmegóvás").
CONJUNCTIONS = {"és", "s", "vagy", "illetve", "valamint", "avagy"}
ELECTRONIC_PREFIX = "e"
# Above two thousand, a spelled-out number has a hyphen after each group word
# ("hatszázezer-kétszáz"); below it, and inside a group, it is written as one word.
NUMBER_GROUP_WORDS = ("ezer", "millió", "milliárd")
NUMBERS_BELOW_TWO_THOUSAND = {"ezer", "egyezer"}
# Suffixes written after an abbreviation with a hyphen ("Ft-ot", "Kft-vel", "ÁSZF-ben").
ABBREVIATION_SUFFIX = re.compile(
    "^(?:[aáeéioóöőuúüű]?(?:t|n|k|s|ig|ra|re|ba|be|ban|ben|ból|ből|ról|ről|tól|től|hoz|hez"
    "|höz|nak|nek|val|vel|tal|tel|nál|nél|ért|ként|ul|ül)|i|ú|ű|e|ket|kat|ja|je)$"
)
# Words at a line end that start the subject of a case or a party's details on the next
# line in decision headers ("alperes ellen-" / "közigazgatási ügyben"): a layout break.
LAYOUT_FIRST_WORDS = {
    "ellen", "adatok", "adatai", "beavatkozó", "beavatkozott", "felpereseknek", "neve",
    "lakcíme", "száma", "szerint", "által", "aki", "is", "el",
}  # fmt: skip
# An inflected first word or a verb as second word means the hyphen is a dash
# ("tényre-" / "bizonyítékra", "bűncselekmény-" / "felmentette"), not a compound.
INFLECTED_ENDING = re.compile(
    "(?:nak|nek|ra|re|val|vel|ban|ben|ból|ből|ról|ről|tól|től|ján|jén|nál|nél|ért|ett|ott|ött)$"
)
VERB_ENDING = re.compile("(?:tta|tte|om|öm|ható|hető)$")
JOINED_PLAIN = "joined"
JOINED_WITH_HYPHEN = "joined, hyphen kept"
JOINED_UNSURE = "joined, unsure spelling"


@dataclass(frozen=True)
class HyphenPair:
    """One word split across two lines.

    Attributes:
        first_part: The letters before the hyphen at the end of the line.
        second_part: The lowercase word at the start of the next non-empty line.
        line_index: Index (from 0) of the line that ends with the hyphen.
        is_adjacent: True if no blank line stands between the two parts.
    """

    first_part: str
    second_part: str
    line_index: int
    is_adjacent: bool


def find_hyphen_pairs(lines: list[str]) -> list[HyphenPair]:
    """List the words split by a hyphen at a line end.

    Args:
        lines: The lines of one text, without line endings.

    Returns:
        One pair per line that ends in letters + "-" and whose next non-empty line
        starts with a lowercase word.
    """
    pairs = []
    for index, line in enumerate(lines):
        end = LINE_ENDS_WITH_HYPHEN.search(line)
        if not end:
            continue
        next_index = index + 1
        while next_index < len(lines) and not lines[next_index].strip():
            next_index += 1
        if next_index >= len(lines):
            continue
        start = LINE_STARTS_LOWERCASE.match(lines[next_index])
        if start:
            pair = HyphenPair(end.group(1), start.group(1), index, next_index == index + 1)
            pairs.append(pair)
    return pairs


def classify_pair(first_part: str, second_part: str, is_known: Callable[[str], bool]) -> str:
    """Decide what to do with a split word.

    Args:
        first_part: Letters before the hyphen.
        second_part: Word at the start of the next line.
        is_known: Returns True for a word the spell checker knows (lowercase input).

    Returns:
        "join" if the two parts written together are a word ("sze" + "rint");
        "keep_hyphen" if they are not but both parts are words, a real compound
        hyphen ("magánokirat-hamisítás"); otherwise "unresolved", for a person to check.
    """
    if is_known((first_part + second_part).lower()):
        return JOIN
    if is_known(first_part.lower()) and is_known(second_part.lower()):
        return KEEP_HYPHEN
    return UNRESOLVED


def hold_reason(first_part: str, second_part: str) -> str:
    """Return why a pair must not be joined automatically, or "" if it may be.

    Args:
        first_part: Letters before the hyphen.
        second_part: Word at the start of the next line.

    Returns:
        A short reason, or an empty string.
    """
    first, second = first_part.lower(), second_part.lower()
    if NUMBER_WORD.match(first) and NUMBER_WORD.match(second):
        return "spelled-out number"
    is_label = len(second) <= MAX_LABEL_LENGTH or second in LABEL_WORDS
    if first in ROLE_WORDS and is_label:
        return "role word before a verdict or label"
    return ""


def syllable_count(word: str) -> int:
    """Return the number of syllables of a Hungarian word, which is its number of vowels."""
    return sum(1 for letter in word.lower() if letter in VOWELS)


def is_abbreviation(part: str) -> bool:
    """Return True for an abbreviation such as "Ft", "Kft" or "ÁSZF" (capitals or no vowel)."""
    return len(part) > 1 and (part.isupper() or not set(part.lower()) & VOWELS)


def merge_double_digraph(first_part: str, second_part: str) -> str | None:
    """Join "ösz" + "szeg" as "összeg"; return None if the parts do not split a digraph."""
    for digraph in DIGRAPHS:
        if first_part.lower().endswith(digraph) and second_part.startswith(digraph):
            return first_part[: -len(digraph)] + first_part[-len(digraph)] + second_part
    return None


def spelled_join(
    first_part: str, second_part: str, is_known: Callable[[str], bool]
) -> tuple[str, str]:
    """Return how a split word is written when its two parts are put together.

    Args:
        first_part: Letters before the hyphen at the line end.
        second_part: Word at the start of the next line.
        is_known: Returns True for a word the spell checker knows.

    Returns:
        The written form and how sure it is: "joined" ("ösz" + "szegére" ->
        "összegére"), "joined, hyphen kept" ("megfelelnek-e", "Ft-ban",
        "ingatlan-nyilvántartás") or "joined, unsure spelling" when the spell checker
        knows none of the forms, so the plain join is given for a person to check.
    """
    plain = first_part + second_part
    hyphenated = f"{first_part}-{second_part}"
    is_forced_hyphen = second_part == QUESTION_PARTICLE or len(first_part) == 1
    if is_forced_hyphen or is_abbreviation(first_part):
        return hyphenated, JOINED_WITH_HYPHEN
    number = number_join(first_part, second_part)
    if number:
        return number, JOINED_WITH_HYPHEN if "-" in number else JOINED_PLAIN
    merged = merge_double_digraph(first_part, second_part)
    if merged and (is_known(merged) or not is_known(plain)):
        return merged, JOINED_PLAIN
    if is_known(plain):
        return plain, JOINED_PLAIN
    if syllable_count(plain) > MAX_SYLLABLES_WITHOUT_HYPHEN and is_known(hyphenated):
        return hyphenated, JOINED_WITH_HYPHEN
    return plain, JOINED_UNSURE


def hyphen_join(first_part: str, second_part: str, is_known: Callable[[str], bool]) -> str | None:
    """Return the one-line form of a real hyphenated word that a line break split.

    For pairs whose hyphen is right ("Rendőr-" / "főkapitányság") but whose line break
    is not. Layout breaks ("vádlott-" / "bűnös") and dashes ("szerint-" / "a") are left
    alone; so is any pair that the rules below do not recognise.

    Args:
        first_part: Letters before the hyphen at the line end.
        second_part: Word at the start of the next line.
        is_known: Returns True for a word the spell checker knows.

    Returns:
        "Rendőr-főkapitányság", "Ft-ot", "hatszázezer-kétszáz", "külön-külön",
        "állag- és", or None to keep the line break.
    """
    first = first_part.lower()
    if first in ROLE_WORDS or first in LAYOUT_FIRST_WORDS:
        return None
    hyphenated = f"{first_part}-{second_part}"
    if first == second_part:
        return hyphenated  # "külön-külön", "egy-egy"
    if second_part in CONJUNCTIONS:
        return f"{first_part}- {second_part}"
    number = number_join(first_part, second_part)
    if number:
        return number
    if is_abbreviation(first_part):
        # A placeholder name before a verdict ("XX-" / "bűnös") is not followed by a suffix.
        return hyphenated if ABBREVIATION_SUFFIX.match(second_part) else None
    if len(second_part) <= MAX_LABEL_LENGTH:
        return None
    if first == ELECTRONIC_PREFIX:
        return hyphenated  # "e-mail", "e-beszámoló"
    if len(first_part) == 1 or second_part.startswith(first):
        return None  # a letter-spaced word, or a word repeated by mistake
    if INFLECTED_ENDING.search(first) or VERB_ENDING.search(second_part):
        return None
    is_long = syllable_count(first_part + second_part) > MAX_SYLLABLES_WITHOUT_HYPHEN
    if is_long and is_known(hyphenated) and not is_known(first_part + second_part):
        return hyphenated
    return None


def number_join(first_part: str, second_part: str) -> str | None:
    """Return the written form of a spelled-out number split at a line end.

    Args:
        first_part: Letters before the hyphen.
        second_part: Word at the start of the next line.

    Returns:
        "hatszázezer-kétszáz" after a group word above two thousand, "négymillió" or
        "hétszázkilencven" otherwise, or None if the parts are not number words.
    """
    first, second = first_part.lower(), second_part.lower()
    if not (NUMBER_WORD.match(first) and NUMBER_WORD.match(second)):
        return None
    if first.endswith(NUMBER_GROUP_WORDS) and first not in NUMBERS_BELOW_TWO_THOUSAND:
        return f"{first_part}-{second_part}"
    return first_part + second_part


def join_hyphenated_lines(
    lines: list[str],
    pairs_to_join: set[tuple[str, str]] | dict[tuple[str, str], str],
    across_blank_lines: bool = False,
) -> list[str]:
    """Join the split words that were approved, removing the line break.

    The rest of the next line is appended to the first line.

    Args:
        lines: The lines of one text.
        pairs_to_join: Approved (first part, second part) pairs. A set joins the parts
            without the hyphen; a dict gives the written form of each pair, e.g.
            ("ösz", "szeg") -> "összeg", ("Rendőr", "főkapitányság") ->
            "Rendőr-főkapitányság" or ("állag", "és") -> "állag- és".
        across_blank_lines: Also join when blank lines stand between the two parts, and
            remove those lines. Leave it False for pairs a person has not checked: for
            an unchecked pair the blank line may be a real paragraph break, but a word
            a person confirmed as split cannot continue after a new paragraph.

    Returns:
        The new list of lines; the input list is not changed.
    """
    if not isinstance(pairs_to_join, dict):
        pairs_to_join = {pair: pair[0] + pair[1] for pair in pairs_to_join}
    result = list(lines)
    # From the bottom up, so that deleting lines does not shift the indexes still to do.
    for pair in reversed(find_hyphen_pairs(lines)):
        written = pairs_to_join.get((pair.first_part, pair.second_part))
        if written is None or not (pair.is_adjacent or across_blank_lines):
            continue
        index = next_index = pair.line_index
        next_index += 1
        while not result[next_index].strip():
            next_index += 1
        before = result[index].rstrip(" \t")[: -len(pair.first_part) - 1]
        after = result[next_index].lstrip(" \t")[len(pair.second_part) :]
        result[index] = before + written + after
        del result[index + 1 : next_index + 1]
    return result
