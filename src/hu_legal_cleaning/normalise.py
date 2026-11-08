"""Character-level steps: NUL padding, soft hyphens, Unicode NFC and look-alike letters.

Removing NUL padding and soft hyphens and applying NFC are normalisation; replacing õ/û
and look-alike letters is cleaning (see docs/pipeline.md for the terms). These steps
change characters only, never words, so they are safe to run first.
"""

import re
import unicodedata

from hu_legal_cleaning.convert import shift_jis_sign

NUL = "\x00"
# An invisible "hyphenate here if needed" mark. Inside a word ("in\u00adgatlan") it splits
# the word for any tool that looks for whole words.
SOFT_HYPHEN = "\u00ad"
# A soft hyphen not followed by a line end (more soft hyphens may stand in between).
SOFT_HYPHEN_INSIDE_LINE = re.compile(SOFT_HYPHEN + "(?!" + SOFT_HYPHEN + "*\\r?\\n)")
# Combining accent marks (U+0300 to U+036F) that are stored apart from their letter.
COMBINING_MARK = re.compile("[̀-ͯ]")
# õ and û never occur in Hungarian. They appear when a text typed with ő and ű is
# read with the Western European code page (Latin-1 or cp1252).
LATIN1_LOOKALIKES = str.maketrans({"õ": "ő", "û": "ű", "Õ": "Ő", "Û": "Ű"})
LOOKALIKE_LETTERS = "õûÕÛ"
# Cyrillic and Greek letters that look like a Latin letter. They get into Latin words by
# mistake (a Cyrillic "Е" in "ЕU"). The Cyrillic "Н" is left out because it can stand for
# an H or an N.
SCRIPT_LOOKALIKES = str.maketrans(
    {
        **dict(zip("АВЕКМОРСТХ", "ABEKMOPCTX", strict=True)),
        **dict(zip("аеорсухіјѕ", "aeopcyxijs", strict=True)),
        **dict(zip("ёӓї", "ëäï", strict=True)),
        **dict(zip("ΑΒΕΖΗΙΚΜΝΟΡΤΥΧ", "ABEZHIKMNOPTYX", strict=True)),
        **dict(zip("οβ", "oß", strict=True)),
    }
)
SCRIPT_LOOKALIKE_LETTERS = {chr(code) for code in SCRIPT_LOOKALIKES}
LETTER_SEQUENCE = re.compile(r"[^\W\d_]+")
# Control characters U+0080 to U+009F never belong in a text. They appear when an RTF
# writer stored cp1252 bytes as Unicode code points (\u150 for an en dash) and when it
# stored a Shift-JIS byte pair as two characters: 0x81 0x98 as "\x81" + "˜" for "§",
# 0x81 0x68 as "\x81" + "h" for "”".
C1_CONTROL = re.compile("[\x80-\x9f]")
SHIFT_JIS_STORED_PAIR = re.compile("\x81(.)", re.S)
SHIFT_JIS_LEAD_BYTE = b"\x81"
# A UTF-8 quotation mark read as cp1250 leaves "€ž" (from "„") or "€" + an unreadable byte.
UTF8_QUOTE_LEFTOVER = re.compile("€ž|€�")
# A dotless ı with a combining accent is an i with that accent ("ı" + acute = "í"); PDF
# conversions write it this way.
DOTLESS_I_WITH_MARK = re.compile("ı(?=[̀-ͯ])")


def remove_nul(text: str) -> tuple[str, int]:
    """Remove NUL characters, such as the padding at the end of some source files.

    Args:
        text: The text to clean.

    Returns:
        The cleaned text and the number of NUL characters removed.
    """
    return text.replace(NUL, ""), text.count(NUL)


def remove_soft_hyphens(text: str) -> tuple[str, int]:
    """Remove soft hyphens, which are invisible when the text is printed.

    A soft hyphen at the end of a line is kept: it marks a word split across two lines,
    which the line-break step joins.

    Args:
        text: The text to clean.

    Returns:
        The cleaned text and the number of soft hyphens removed.
    """
    return SOFT_HYPHEN_INSIDE_LINE.subn("", text)


def to_nfc(text: str) -> tuple[str, int]:
    """Compose letters and their separately stored accents into single characters.

    "a" followed by a combining acute accent (two characters) becomes "á" (one character).
    Accents that have no composed form, such as a combining strike-through, stay as they are.

    Args:
        text: The text to normalise.

    Returns:
        The normalised text and the number of combining marks left in it.
    """
    text = DOTLESS_I_WITH_MARK.sub("i", text)
    # NFC ("normalisation form C") is the standard composed form of Unicode text.
    normalised = unicodedata.normalize("NFC", text)
    return normalised, len(COMBINING_MARK.findall(normalised))


def repair_control_characters(text: str) -> tuple[str, int]:
    r"""Turn stored control characters back into the signs they stand for.

    "\x81" followed by a character is a Shift-JIS byte pair ("§", "”", or the
    anonymisation tool's lost-letter mark, which becomes "�"); any other control
    character is the cp1252 sign with that byte ("\x96" becomes "–"), or is removed if
    cp1252 has none. UTF-8 quotation marks read as cp1250 ("„€ž") lose their leftovers.

    Args:
        text: The text to repair.

    Returns:
        The repaired text and the number of characters repaired.
    """
    repaired = 0

    def pair(match: re.Match[str]) -> str:
        nonlocal repaired
        repaired += 1
        try:
            trail_byte = match.group(1).encode("cp1252")
        except UnicodeEncodeError:
            return match.group(1)
        return shift_jis_sign(SHIFT_JIS_LEAD_BYTE + trail_byte) or match.group(1)

    def single(match: re.Match[str]) -> str:
        nonlocal repaired
        repaired += 1
        return bytes([ord(match.group(0))]).decode("cp1252", "ignore")

    text = SHIFT_JIS_STORED_PAIR.sub(pair, text)
    text = C1_CONTROL.sub(single, text)
    text, leftovers = UTF8_QUOTE_LEFTOVER.subn("", text)
    return text, repaired + leftovers


def fix_latin1_lookalikes(text: str) -> tuple[str, int]:
    """Replace õ/û (and capitals) with the Hungarian ő/ű.

    Args:
        text: Hungarian text.

    Returns:
        The repaired text and the number of letters replaced.
    """
    count = sum(text.count(letter) for letter in LOOKALIKE_LETTERS)
    return text.translate(LATIN1_LOOKALIKES), count


def _is_cyrillic_or_greek(letter: str) -> bool:
    return unicodedata.name(letter, "").startswith(("CYRILLIC", "GREEK"))


def _is_latin(letter: str) -> bool:
    return unicodedata.name(letter, "").startswith("LATIN")


def fix_script_lookalikes(text: str) -> tuple[str, int]:
    """Replace Cyrillic and Greek look-alike letters inside Latin words.

    A word is changed only if it has a Latin letter and every letter of another script in
    it has a Latin look-alike. "ЕU" (with a Cyrillic E) becomes "EU", but a Cyrillic word
    such as "Адреса" or a Greek symbol such as "μg" stays.

    Args:
        text: The text to clean.

    Returns:
        The repaired text and the number of letters replaced.
    """
    replaced = 0

    def repair(match: re.Match[str]) -> str:
        nonlocal replaced
        word = match.group(0)
        foreign = [letter for letter in word if _is_cyrillic_or_greek(letter)]
        if not foreign or not any(_is_latin(letter) for letter in word):
            return word
        if any(letter not in SCRIPT_LOOKALIKE_LETTERS for letter in foreign):
            return word
        replaced += len(foreign)
        return word.translate(SCRIPT_LOOKALIKES)

    return LETTER_SEQUENCE.sub(repair, text), replaced


def clean_characters(text: str) -> tuple[str, dict[str, int]]:
    """Run all character-level steps: NUL and soft hyphens, NFC, then look-alike letters.

    NFC runs before the look-alike repair because "o" plus a combining tilde only
    becomes the single letter õ, which the repair can then recognise, after NFC.

    Args:
        text: The text to clean.

    Returns:
        The cleaned text and a count per step, for the log.
    """
    text, nul_count = remove_nul(text)
    text, soft_hyphen_count = remove_soft_hyphens(text)
    text, control_count = repair_control_characters(text)
    text, marks_left = to_nfc(text)
    text, lookalike_count = fix_latin1_lookalikes(text)
    text, script_count = fix_script_lookalikes(text)
    counts = {"nul_removed": nul_count, "soft_hyphens_removed": soft_hyphen_count}
    counts["control_characters_repaired"] = control_count
    counts["lookalikes_fixed"] = lookalike_count
    counts["script_lookalikes_fixed"] = script_count
    counts["combining_marks_left"] = marks_left
    return text, counts
