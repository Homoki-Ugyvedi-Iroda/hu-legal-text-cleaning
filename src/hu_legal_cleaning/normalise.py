"""Character-level clean-up: NUL padding, soft hyphens, Unicode NFC and look-alike letters.

These steps change characters only, never words, so they are safe to run first.
"""

import re
import unicodedata

NUL = "\x00"
# An invisible "hyphenate here if needed" mark. Inside a word ("in\u00adgatlan") it splits
# the word for any tool that looks for whole words.
SOFT_HYPHEN = "\u00ad"
# Combining accent marks (U+0300 to U+036F) that are stored apart from their letter.
COMBINING_MARK = re.compile("[̀-ͯ]")
# õ and û never occur in Hungarian. They appear when a text typed with ő and ű is
# read with the Western European code page (Latin-1 or cp1252).
LATIN1_LOOKALIKES = str.maketrans({"õ": "ő", "û": "ű", "Õ": "Ő", "Û": "Ű"})
LOOKALIKE_LETTERS = "õûÕÛ"


def remove_nul(text: str) -> tuple[str, int]:
    """Remove NUL characters, such as the padding at the end of converted files.

    Args:
        text: The text to clean.

    Returns:
        The cleaned text and the number of NUL characters removed.
    """
    return text.replace(NUL, ""), text.count(NUL)


def remove_soft_hyphens(text: str) -> tuple[str, int]:
    """Remove soft hyphens, which are invisible when the text is printed.

    Args:
        text: The text to clean.

    Returns:
        The cleaned text and the number of soft hyphens removed.
    """
    return text.replace(SOFT_HYPHEN, ""), text.count(SOFT_HYPHEN)


def to_nfc(text: str) -> tuple[str, int]:
    """Compose letters and their separately stored accents into single characters.

    "a" followed by a combining acute accent (two characters) becomes "á" (one character).
    Accents that have no composed form, such as a combining strike-through, stay as they are.

    Args:
        text: The text to normalise.

    Returns:
        The normalised text and the number of combining marks left in it.
    """
    # NFC ("normalisation form C") is the standard composed form of Unicode text.
    normalised = unicodedata.normalize("NFC", text)
    return normalised, len(COMBINING_MARK.findall(normalised))


def fix_latin1_lookalikes(text: str) -> tuple[str, int]:
    """Replace õ/û (and capitals) with the Hungarian ő/ű.

    Args:
        text: Hungarian text.

    Returns:
        The repaired text and the number of letters replaced.
    """
    count = sum(text.count(letter) for letter in LOOKALIKE_LETTERS)
    return text.translate(LATIN1_LOOKALIKES), count


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
    text, marks_left = to_nfc(text)
    text, lookalike_count = fix_latin1_lookalikes(text)
    counts = {"nul_removed": nul_count, "soft_hyphens_removed": soft_hyphen_count}
    counts["lookalikes_fixed"] = lookalike_count
    counts["combining_marks_left"] = marks_left
    return text, counts
