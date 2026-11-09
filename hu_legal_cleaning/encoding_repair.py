r"""Find and repair Hungarian text that was decoded with the wrong code page.

Old Windows documents store accented letters as single bytes, and the code page says
which letter each byte means. If a document declares the wrong code page, the bytes of
Hungarian letters turn into letters of another script. In BHGY, some RTF files declare an
Arabic font (`\\fcharset178`) for Hungarian text, so "határozat" became "hatلrozat":
byte 0xE1 is "á" in the Central European code page (cp1250) and "ل" in the Arabic one
(cp1256).

The damage is easy to recognise: a word mixes Latin letters with letters of another
script, which does not happen in real text. The repair turns the damaged word back into
bytes with the wrong code page and decodes the bytes with cp1250. A repair is kept only
if the result consists of Latin letters only.

The same method covers text that was encoded as UTF-8 and then read as cp1252 or
Latin-1 ("Ã¡" for "á").
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

TARGET_CODEC = "cp1250"
# Code pages whose letters replace Hungarian ones when they are declared by mistake.
# Latin code pages are left out: they turn ő/ű into õ/û, which normalise.py fixes.
WRONG_CODECS = ["cp1256", "cp1255", "cp1253", "cp1251", "cp874", "cp932", "gbk"]
# Some anonymisation tools wrote signs ("§", "…", quotation marks, "μ") as Shift-JIS
# byte pairs whose first byte is 0x81-0x84. Read with another code page, the pair becomes
# foreign letters, e.g. "پک" for "§" or "پh" for "”" in cp1256.
SHIFT_JIS_CODEC = "cp932"
SHIFT_JIS_SIGN_LEAD_BYTES = range(0x81, 0x85)
UTF8_MISREAD_CODECS = ["cp1252", "latin-1"]
# Unicode name prefixes of the scripts of WRONG_CODECS. Other non-Latin characters, such
# as "º" in "22ºC" or "ᵌ" in "mᵌ", are symbols in Hungarian text, not damage.
SCRIPT_NAMES = ("ARABIC", "HEBREW", "GREEK", "CYRILLIC", "THAI", "CJK", "KATAKANA", "HIRAGANA")
HUNGARIAN_ACCENTED = set("áéíóöőúüűÁÉÍÓÖŐÚÜŰ")
# A word as written in running text: anything between spaces, without the punctuation
# that can stand at its ends.
TOKEN = re.compile(r"\S+")
EDGE_PUNCTUATION = "\"'„”“()[]{}.,;:!?«»-–"
# The second byte of a two-byte UTF-8 letter (0x80-0xBF), as cp1252 shows it.
UTF8_CONTINUATION = bytes(range(0x80, 0xC0)).decode("cp1252", "ignore")
# "Ã" and "Å" are the lead bytes of Hungarian accented letters in UTF-8 (U+00C0-U+017F).
UTF8_MISREAD = re.compile(f"[ÃÅ][{re.escape(UTF8_CONTINUATION)}]")
# A quick test before the slow word-by-word check: any character from Greek onwards,
# leaving out the punctuation block (U+2000-U+2BFF) with dashes, quotation marks and "…".
POSSIBLY_FOREIGN = re.compile(
    f"[{chr(0x0370)}-{chr(0x1FFF)}{chr(0x2C00)}-{chr(0xD7FF)}{chr(0xE000)}-{chr(0xFFFF)}]"
)
MIN_DAMAGED_WORDS = 3
MIN_REPAIRABLE_SHARE = 0.8


def _is_foreign(character: str) -> bool:
    """Tell whether a character is a letter or mark of one of the scripts of SCRIPT_NAMES."""
    if not unicodedata.category(character).startswith(("L", "M")):
        return False
    return unicodedata.name(character, "").startswith(SCRIPT_NAMES)


def _is_latin_letter(character: str) -> bool:
    return unicodedata.name(character, "").startswith("LATIN")


def is_mixed_script(word: str) -> bool:
    """Tell whether a word has a letter of another script directly next to a Latin letter.

    "hatلrozat" is mixed. Greek letters used as symbols usually stand apart from the
    Latin letters ("Δ9-THC", "α-PVP"), so they do not count.

    Args:
        word: One word, e.g. "hatلrozat".
    """
    for left, right in zip(word, word[1:], strict=False):
        if _is_foreign(left) and _is_latin_letter(right):
            return True
        if _is_latin_letter(left) and _is_foreign(right):
            return True
    return False


def _reread(word: str, wrong_codec: str, right_codec: str) -> str | None:
    """Return the word decoded with the right code page, or None if that is not possible."""
    try:
        repaired = word.encode(wrong_codec).decode(right_codec)
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None
    if any(_is_foreign(character) for character in repaired):
        return None
    return repaired


def _is_from_foreign_block(character: str) -> bool:
    """Tell whether a character belongs to another script, letters and punctuation alike.

    Punctuation counts too: in cp1256, the byte of "Ű" is the Arabic semicolon "؛".
    """
    return unicodedata.name(character, "").startswith(SCRIPT_NAMES)


def _is_hungarian_reading(characters: str) -> bool:
    """Tell whether re-read characters are what a Hungarian text can contain.

    One foreign character stands for one accented letter (single-byte code pages) or for
    an accented letter and the next ASCII letter (two-byte code pages such as GBK).
    Anything else, e.g. "Ä" from a Greek "Δ" in "Δ9-THC", means the word was not damaged.
    """
    has_accent = any(character in HUNGARIAN_ACCENTED for character in characters)
    is_allowed = all(
        character in HUNGARIAN_ACCENTED or (character.isascii() and character.isalpha())
        for character in characters
    )
    return has_accent and is_allowed


def _single_byte(character: str, codec: str) -> int | None:
    try:
        encoded = character.encode(codec)
    except UnicodeEncodeError:
        return None
    return encoded[0] if len(encoded) == 1 else None


def _shift_jis_sign(first: str, second: str, wrong_codec: str) -> str | None:
    """Return the Shift-JIS sign that two misread characters stand for, or None."""
    lead = _single_byte(first, wrong_codec)
    trail = _single_byte(second, wrong_codec)
    if lead not in SHIFT_JIS_SIGN_LEAD_BYTES or trail is None:
        return None
    try:
        sign = bytes([lead, trail]).decode(SHIFT_JIS_CODEC)
    except UnicodeDecodeError:
        return None
    # Japanese letters are not what the anonymisation tools wrote.
    if unicodedata.name(sign, "").startswith(("CJK", "KATAKANA", "HIRAGANA")):
        return None
    return sign


def repair_word(word: str, wrong_codec: str) -> str | None:
    """Return the repaired form of a damaged word, or None if it cannot be repaired.

    The characters of the other script are re-read one by one, so letters that were
    decoded correctly (e.g. "ű" from a Central European font in the same word) stay. A
    repair is accepted only if every re-read character gives a Hungarian accented letter.
    Pairs that stand for a Shift-JIS sign ("پک" for "§") are replaced by the sign.

    Args:
        word: A word that contains letters of another script, e.g. "hatلrozat".
        wrong_codec: The code page the text was wrongly decoded with, e.g. "cp1256".

    Returns:
        The word read with cp1250 ("határozat"), or None.
    """
    characters, index = [], 0
    while index < len(word):
        pair = word[index : index + 2]
        sign = None
        if wrong_codec != SHIFT_JIS_CODEC and len(pair) == 2:
            if any(_is_from_foreign_block(character) for character in pair):
                sign = _shift_jis_sign(pair[0], pair[1], wrong_codec)
        if sign is not None:
            characters.append(sign)
            index += 2
            continue
        character = word[index]
        index += 1
        if not _is_from_foreign_block(character):
            characters.append(character)
            continue
        repaired = _reread(character, wrong_codec, TARGET_CODEC)
        if repaired is None or not _is_hungarian_reading(repaired):
            return None
        characters.append(repaired)
    return "".join(characters)


@dataclass
class EncodingDiagnosis:
    """What a text's damaged words point to.

    Attributes:
        damaged_words: Number of words with letters of another script.
        wrong_codec: The code page that repairs most of them, or "" if none does.
        repairable_words: Number of damaged words that code page repairs.
        utf8_misread: Number of "Ã¡"-style sequences (UTF-8 read as cp1252).
        examples: A few damaged words, the most frequent first.
    """

    damaged_words: int
    wrong_codec: str
    repairable_words: int
    utf8_misread: int
    examples: list[str]


def _foreign_tokens(text: str) -> list[str]:
    tokens = (token.strip(EDGE_PUNCTUATION) for token in TOKEN.findall(text))
    return [token for token in tokens if any(_is_foreign(character) for character in token)]


def diagnose(text: str) -> EncodingDiagnosis:
    """Count the damaged words of a text and find the code page that explains them.

    Only words that mix Latin letters with another script count as damaged, so a text
    that quotes a Greek or Russian word correctly is not flagged.

    Args:
        text: The text of one document.
    """
    if not POSSIBLY_FOREIGN.search(text):
        return EncodingDiagnosis(0, "", 0, len(UTF8_MISREAD.findall(text)), [])
    damaged = Counter(token for token in _foreign_tokens(text) if is_mixed_script(token))
    best_codec, best_count = "", 0
    for codec in WRONG_CODECS:
        repaired = sum(count for word, count in damaged.items() if repair_word(word, codec))
        if repaired > best_count:
            best_codec, best_count = codec, repaired
    examples = [word for word, _ in damaged.most_common(5)]
    misread = len(UTF8_MISREAD.findall(text))
    return EncodingDiagnosis(sum(damaged.values()), best_codec, best_count, misread, examples)


def needs_repair(
    diagnosis: EncodingDiagnosis,
    min_damaged_words: int = MIN_DAMAGED_WORDS,
    min_share: float = MIN_REPAIRABLE_SHARE,
) -> bool:
    """Tell whether a text is damaged enough, and consistently enough, to repair.

    On plain text, a single odd word is more likely a real quotation or a typo, so a few
    damaged words are required, and most of them must be explained by the same code page.

    Args:
        diagnosis: The result of `diagnose`.
        min_damaged_words: How many repairable words are needed.
        min_share: Which share of the damaged words the code page must explain.
    """
    if diagnosis.repairable_words < min_damaged_words:
        return False
    return diagnosis.repairable_words >= min_share * diagnosis.damaged_words


def repair_document(
    text: str, min_damaged_words: int = MIN_DAMAGED_WORDS, min_share: float = MIN_REPAIRABLE_SHARE
) -> tuple[str, EncodingDiagnosis, int]:
    """Diagnose a text and repair it if `needs_repair` says so.

    Args:
        text: The text of one document.
        min_damaged_words: Passed to `needs_repair`.
        min_share: Passed to `needs_repair`.

    Returns:
        The (possibly) repaired text, the diagnosis and the number of words changed.
    """
    diagnosis = diagnose(text)
    changed = 0
    if needs_repair(diagnosis, min_damaged_words, min_share):
        text, changed = repair_text(text, diagnosis.wrong_codec)
    if diagnosis.utf8_misread >= MIN_DAMAGED_WORDS:
        text, misread_changed = repair_utf8_misread(text)
        changed += misread_changed
    return text, diagnosis, changed


def _repair_token(token: str, wrong_codec: str) -> str:
    """Repair the foreign letters of one space-separated token, keeping its punctuation."""
    if not any(_is_from_foreign_block(character) for character in token):
        return token
    repaired = repair_word(token, wrong_codec)
    return repaired if repaired is not None else token


def repair_text(text: str, wrong_codec: str) -> tuple[str, int]:
    """Repair every word that contains letters of the wrong code page's script.

    In a document known to be damaged, words made only of foreign letters (e.g. "ل"
    for the letter "á" standing alone) are repaired too, not only mixed ones.

    Args:
        text: The text of one document.
        wrong_codec: The code page found by `diagnose`.

    Returns:
        The repaired text and the number of words changed.
    """
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        repaired = _repair_token(match.group(0), wrong_codec)
        changed += repaired != match.group(0)
        return repaired

    return TOKEN.sub(replace, text), changed


def repair_utf8_misread(text: str) -> tuple[str, int]:
    """Repair words that were encoded as UTF-8 and read as cp1252 ("Ã¡" -> "á").

    Args:
        text: The text of one document.

    Returns:
        The repaired text and the number of words changed.
    """
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        token = match.group(0)
        if not UTF8_MISREAD.search(token):
            return token
        for codec in UTF8_MISREAD_CODECS:
            repaired = _reread(token, codec, "utf-8")
            if repaired is not None:
                changed += 1
                return repaired
        return token

    return TOKEN.sub(replace, text), changed
