"""Convert RTF and DOCX court decisions to plain text, using only the standard library.

Why not pandoc: on Hungarian court decisions it lost the text of table cells and turned
ő/ű into õ/û in most RTF files (see ADR-2026-11-01-own-rtf-docx-reader).

Tables become lines of cells separated by " | ". Headers, footers, footnotes, text
boxes and pictures are left out: in court decisions they hold page numbers and case
numbers that would otherwise land in the middle of the running text.
"""

import codecs
import html
import re
import unicodedata
import zipfile
from pathlib import Path

from hu_legal_cleaning.encoding_repair import (
    HUNGARIAN_ACCENTED,
    is_mixed_script,
    repair_document,
)

# --- DOCX ---------------------------------------------------------------------

DOCX_BODY = "word/document.xml"
# A tab character in the text: "<w:tab/>" or "<w:tab />". Tab stop definitions such as
# <w:tab w:val="left" w:pos="850"/> have attributes and are not text.
DOCX_TAB = re.compile(r"<w:tab\s*/>")


def _docx_cell(match: re.Match[str]) -> str:
    cell = match.group(1).replace("</w:p>", " ")
    cell = DOCX_TAB.sub(" ", cell)
    cell = re.sub(r"<w:br\b[^>]*/>", " ", cell)
    cell = re.sub(r"<[^>]+>", "", cell)
    return re.sub(r"\s+", " ", cell).strip() + " | "


def docx_to_text(path: Path) -> str:
    """Return the body text of a DOCX file.

    Deleted text of tracked changes is dropped; paragraphs become lines and tables
    become lines of cells separated by " | ".

    Args:
        path: The .docx file.

    Returns:
        The plain text.
    """
    # A DOCX file is a zip archive; the body text is the XML file word/document.xml.
    with zipfile.ZipFile(path) as archive:
        xml = archive.read(DOCX_BODY).decode("utf-8", "ignore")
    xml = re.sub(r"<w:del\b.*?</w:del>", "", xml, flags=re.S)
    xml = re.sub(r"<w:tc\b[^>]*>(.*?)</w:tc>", _docx_cell, xml, flags=re.S)
    xml = re.sub(r"<w:tr\b[^>]*>", "| ", xml).replace("</w:tr>", "\n")
    xml = DOCX_TAB.sub("\t", xml.replace("</w:p>", "\n"))
    xml = re.sub(r"<w:br\b[^>]*/>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(xml)


# --- RTF ----------------------------------------------------------------------

# Groups whose content is not part of the running text.
RTF_SKIPPED_GROUPS = {
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "header", "footer", "footnote",
    "themedata", "colorschememapping", "latentstyles", "datastore", "xmlnstbl",
    "listtable", "listoverridetable", "rsidtbl", "generator",
}  # fmt: skip
RTF_SPECIAL_CHARACTERS = {
    "emdash": "\u2014", "endash": "\u2013", "lquote": "\u2018", "rquote": "\u2019",
    "ldblquote": "\u201c", "rdblquote": "\u201d", "bullet": "\u2022",
    "emspace": " ", "enspace": " ", "qmspace": " ",
}  # fmt: skip
RTF_LINE_BREAKS = {"par", "line", "sect", "row"}
# RTF font character set number -> Python codec. 0 is Western ("Times New Roman" without
# "CE"): its bytes are cp1252 even in a Hungarian document, so 0xBC is "¼", not "Ľ".
# 238 is Central European (Hungarian); 128 is Japanese Shift-JIS, which some anonymisation
# tools used for "…" and "§".
FONT_CHARSET_CODECS = {
    0: "cp1252", 238: "cp1250", 128: "cp932", 204: "cp1251", 161: "cp1253", 162: "cp1254",
    186: "cp1257", 163: "cp1258", 177: "cp1255", 178: "cp1256", 129: "cp949",
    134: "gb2312", 136: "cp950", 222: "cp874",
}  # fmt: skip
SHIFT_JIS_CODEC = "cp932"
# Symbol fonts (charset 2) draw their own pictures for each byte, so no code page applies.
# Read with cp1250, a Wingdings arrow bullet (0xD8) became "Ř" and a row of separators
# "ŇŇŇ". "Symbol" has Unicode equivalents (Greek letters, "®", "°"); the picture fonts
# (Wingdings, Webdings, ...) get the private-use code U+F0hh, as Word itself does.
SYMBOL_CHARSET = 2
SYMBOL_FONT_CODEC = "symbol"
PICTURE_FONT_CODEC = "picture-font"
OTHER_SYMBOL_FONT_CODEC = "cp1252"
SYMBOL_FONT_NAMES = {"symbol"}
PICTURE_FONT_NAMES = {"wingdings", "wingdings 2", "wingdings 3", "webdings", "marlett"}
PRIVATE_USE_SYMBOL_BASE = 0xF000
SYMBOL_GREEK_UPPER = "ΑΒΧΔΕΦΓΗΙϑΚΛΜΝΟΠΘΡΣΤΥςΩΞΨΖ"
SYMBOL_GREEK_LOWER = "αβχδεφγηιϕκλμνοπθρστυϖωξψζ"
SYMBOL_FONT_SIGNS = {
    0xA2: "′", 0xA3: "≤", 0xA5: "∞", 0xA7: "♣", 0xA8: "♦", 0xA9: "♥", 0xAA: "♠",
    0xAC: "←", 0xAD: "↑", 0xAE: "→", 0xAF: "↓", 0xB0: "°", 0xB1: "±", 0xB2: "″",
    0xB3: "≥", 0xB4: "×", 0xB7: "•", 0xB8: "÷", 0xB9: "≠", 0xBB: "≈", 0xBC: "…",
    0xC3: "℘", 0xC6: "∅", 0xD2: "®", 0xD3: "©", 0xD4: "™", 0xD6: "√", 0xD8: "¬",
    0xDE: "⇒", 0xE2: "®", 0xE3: "©", 0xE4: "™", 0xE5: "∑", 0xF2: "∫",
}  # fmt: skip
# Signs written as Shift-JIS byte pairs ("§" is 0x81 0x98, "…" is 0x81 0x63), also seen in
# fonts that are not declared as Shift-JIS. Only lead bytes that are unused in cp1250 are
# taken, so that "„" (0x84) followed by a letter is never read as a pair.
SHIFT_JIS_PAIR = re.compile(rb"[\x81\x83][\x40-\x7e\x80-\xfc]")
# The anonymisation tools wrote "・" (0x81 0x45) where they had lost a letter.
SHIFT_JIS_LOST_LETTER = "\u30fb"
LOST_LETTER = "\ufffd"
# Font charsets of other scripts. Some documents declare one of these for Hungarian text
# (e.g. Arabic for a "Times New Roman" font); see `_decode_run`.
NON_LATIN_CODECS = {"cp932", "cp1251", "cp1253", "cp1255", "cp1256", "cp874", "cp949"}
NON_LATIN_CODECS |= {"gb2312", "cp950"}
# After conversion, one repairable word is enough to repair: a converted document has no
# real reason to contain Hungarian words with Arabic or Japanese letters inside them.
CONVERTED_MIN_DAMAGED_WORDS = 1
CONVERTED_MIN_SHARE = 0.0
FALLBACK_ERROR_HANDLER = "cp1252fallback"
CONTROL_WORD = re.compile(rb"([a-zA-Z]+)(-?\d+)? ?")
# Some writers leave out the space that ends a control word before text, as in "\tabDr.",
# "\qjbudapest" or "\tab981 092 Ft". Control words that are followed by text, and never
# take a number, are split off such a run;
# longest first, so that "\pardDr" becomes \pard + "Dr", not \par + "dDr".
TEXT_PRECEDING_WORDS = sorted(
    ("tab", "par", "pard", "cell", "row", "line", "qc", "qj", "ql", "qr", "intbl",
     "nowidctlpar", "ltrpar", "rtlpar", "plain", "sectd"),
    key=len, reverse=True,
)  # fmt: skip
# Real control words that begin with one of the above; those marked True take a number.
LONGER_CONTROL_WORDS = {
    "pararsid": True, "cellx": True, "linex": True, "linemod": True, "linestarts": True,
    "linebetcol": False, "linecont": False, "lineppage": False, "linerestart": False,
    "sectdefaultcl": False, "tabsnoovrlp": False,
}  # fmt: skip
HEX_PAIR = re.compile(rb"[0-9a-fA-F]{2}")
UNICODE_LIMIT = 65536
# Control characters U+0080 to U+009F in a \uN are bytes the writer failed to decode.
C1_CONTROL_RANGE = range(0x80, 0xA0)
SHIFT_JIS_LEAD = b"\x81"
STORED_BYTES_CODEC = "cp1252"


def _cp1252_fallback(error: UnicodeDecodeError) -> tuple[str, int]:
    # Bytes undefined in the document's code page (e.g. 0x98 in cp1250) come from cp1252.
    return error.object[error.start : error.end].decode("cp1252", "replace"), error.end


# Registers the handler under a name, so that bytes.decode(codec, name) can use it.
codecs.register_error(FALLBACK_ERROR_HANDLER, _cp1252_fallback)


def _glued_control_word(word: str, argument: bytes | None) -> str | None:
    r"""Return the control word at the start of a run glued to text, or None.

    "tabDr" returns "tab" (the text is "Dr"), and so does "tab" with the number 981,
    because \tab never takes a number ("\tab981 092 Ft"). "pararsid" with a number and
    "tab" alone return None: they are whole control words.
    """
    if word in TEXT_PRECEDING_WORDS:
        return word if argument is not None else None
    takes_number = LONGER_CONTROL_WORDS.get(word)
    if takes_number is not None and (argument is not None or not takes_number):
        return None
    for known_word in TEXT_PRECEDING_WORDS:
        if word.startswith(known_word):
            return known_word
    return None


def _default_codec(data: bytes) -> str:
    """Return the document's code page; a Central European font means cp1250."""
    if b"fcharset238" in data:
        return "cp1250"
    declared = re.search(rb"\\ansicpg(\d+)", data)
    return "cp" + (declared.group(1).decode() if declared else "1250")


def _font_table(data: bytes) -> bytes:
    r"""Return the {\fonttbl ...} group of an RTF file, or b"" if there is none."""
    start = re.search(rb"\{\\fonttbl", data)
    if not start:
        return b""
    depth, index = 0, start.start()
    while index < len(data):
        character = data[index : index + 1]
        if character == b"{":
            depth += 1
        elif character == b"}":
            depth -= 1
            if depth == 0:
                break
        elif character == b"\\":
            index += 1
        index += 1
    return data[start.start() : index]


def _font_name(entry: bytes) -> str:
    r"""Return the lowercase name of a font table entry such as "\f2\fcharset2 Wingdings;"."""
    entry = re.sub(rb"\{\\\*[^{}]*\}", b"", entry)
    entry = re.sub(rb"\\[a-z]+-?\d* ?", b"", entry)
    return entry.split(b";", 1)[0].strip(b" {}").decode("latin-1").lower()


def _font_codec(entry: bytes, default: str) -> str:
    """Return the codec of one font table entry, from its charset and, for symbols, its name."""
    name = _font_name(entry)
    charset = re.search(rb"\\fcharset(\d+)", entry)
    charset_number = int(charset.group(1)) if charset else None
    # The name decides, not the charset: some files declare "Symbol" with a text charset,
    # and OpenOffice's StarSymbol and OpenSymbol declare the symbol charset although
    # their glyphs at these bytes are the ordinary cp1252 signs ("•", "–").
    if name in SYMBOL_FONT_NAMES:
        return SYMBOL_FONT_CODEC
    if name in PICTURE_FONT_NAMES:
        return PICTURE_FONT_CODEC
    if charset_number == SYMBOL_CHARSET:
        return OTHER_SYMBOL_FONT_CODEC
    return FONT_CHARSET_CODECS.get(charset_number, default)


def _font_codecs(data: bytes, default: str) -> dict[int, str]:
    """Return font number -> codec, read from each font in the font table."""
    table = _font_table(data)
    starts = list(re.finditer(rb"\\f(\d+)(?![0-9a-zA-Z])", table))
    codecs_by_font: dict[int, str] = {}
    for position, start in enumerate(starts):
        end = starts[position + 1].start() if position + 1 < len(starts) else len(table)
        codecs_by_font[int(start.group(1))] = _font_codec(table[start.end() : end], default)
    return codecs_by_font


def _decode_symbols(raw: bytes, codec: str) -> str:
    """Decode bytes of a symbol font: Unicode signs for "Symbol", private-use codes otherwise."""
    characters = []
    for value in raw:
        if value == ord(" "):
            characters.append(" ")
        elif codec == SYMBOL_FONT_CODEC and ord("A") <= value <= ord("Z"):
            characters.append(SYMBOL_GREEK_UPPER[value - ord("A")])
        elif codec == SYMBOL_FONT_CODEC and ord("a") <= value <= ord("z"):
            characters.append(SYMBOL_GREEK_LOWER[value - ord("a")])
        elif codec == SYMBOL_FONT_CODEC and value in SYMBOL_FONT_SIGNS:
            characters.append(SYMBOL_FONT_SIGNS[value])
        elif codec == SYMBOL_FONT_CODEC and value < 0x80:
            characters.append(chr(value))
        else:
            characters.append(chr(PRIVATE_USE_SYMBOL_BASE + value))
    return "".join(characters)


def shift_jis_sign(pair: bytes) -> str | None:
    """Return the sign a Shift-JIS byte pair stands for, or None for a Japanese letter."""
    try:
        sign = pair.decode(SHIFT_JIS_CODEC)
    except UnicodeDecodeError:
        return None
    if sign == SHIFT_JIS_LOST_LETTER:
        return LOST_LETTER
    if unicodedata.name(sign, "").startswith(("CJK", "KATAKANA", "HIRAGANA")):
        return None
    return sign


def _decode(raw: bytes, codec: str) -> str:
    """Decode text bytes, keeping the signs written as Shift-JIS byte pairs."""
    if codec in (SYMBOL_FONT_CODEC, PICTURE_FONT_CODEC):
        return _decode_symbols(raw, codec)
    if codec == SHIFT_JIS_CODEC:
        return raw.decode(SHIFT_JIS_CODEC, "replace")
    pieces, start = [], 0
    for match in SHIFT_JIS_PAIR.finditer(raw):
        sign = shift_jis_sign(match.group(0))
        if sign is None:
            continue
        pieces.append(raw[start : match.start()].decode(codec, FALLBACK_ERROR_HANDLER))
        pieces.append(sign)
        start = match.end()
    pieces.append(raw[start:].decode(codec, FALLBACK_ERROR_HANDLER))
    return "".join(pieces)


def _decode_run(raw: bytes, codec: str, default_codec: str) -> str:
    """Decode a run of text bytes with its font's code page, unless that is clearly wrong.

    If a font of another script yields words that mix Latin letters with that script
    ("hatلrozat", "bekezd駸"), the font's charset was declared by mistake and the run is
    decoded with the document's own code page instead. Real Greek or Japanese text does
    not mix scripts inside words, so it keeps its font's code page. A symbol next to a
    Latin letter ("μg/ml") is real too: read with the document's code page it gives no
    Hungarian letter ("ěg/ml"), so it also keeps its font's code page.
    """
    text = _decode(raw, codec)
    if codec not in NON_LATIN_CODECS or codec == default_codec:
        return text
    if not any(is_mixed_script(word) for word in text.split()):
        return text
    redecoded = _decode(raw, default_codec)
    if _hungarian_letter_count(redecoded) <= _hungarian_letter_count(text):
        return text
    return redecoded


def _hungarian_letter_count(text: str) -> int:
    return sum(1 for character in text if character in HUNGARIAN_ACCENTED)


class _RtfReader:
    """A small RTF reader that keeps only the running text.

    It walks the file byte by byte, keeps a stack of groups ({...}), skips groups that
    are not text (font table, headers, pictures), and decodes text bytes with the code
    page of the font that is active at that point.
    """

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.default_codec = _default_codec(data)
        self.font_codecs = _font_codecs(data, self.default_codec)
        default_font = re.search(rb"\\deff(\d+)", data)
        self.font = int(default_font.group(1)) if default_font else None
        self.output: list[str] = []
        self.pending = bytearray()
        self.is_skipping = False
        self.fallback_units = 1
        self.stack: list[tuple[bool, int, int | None]] = []

    def flush(self) -> None:
        """Decode the collected text bytes with the current font's code page."""
        if self.pending:
            codec = self.font_codecs.get(self.font, self.default_codec)
            self.output.append(_decode_run(bytes(self.pending), codec, self.default_codec))
            self.pending.clear()

    def emit(self, text: str) -> None:
        """Add already decoded text to the output."""
        self.flush()
        self.output.append(text)

    def skip_fallback(self, index: int) -> int:
        r"""Skip the ASCII fallback written after a \uN character (\'hh units or characters)."""
        for _ in range(self.fallback_units):
            while self.data[index : index + 1] in (b"\r", b"\n"):
                index += 1
            if self.data[index : index + 2] == b"\\'":
                index += 4
            elif self.data[index : index + 1] in (b"\\", b"{", b"}", b""):
                break
            else:
                index += 1
        return index

    def control_word(self, word: str, argument: bytes | None, index: int) -> int:
        r"""Handle a control word such as \par or \u337; return the next position."""
        if word in RTF_SKIPPED_GROUPS:
            self.is_skipping = True
        elif self.is_skipping:
            return index
        elif word in RTF_LINE_BREAKS:
            self.emit("\n")
        elif word == "cell":
            self.emit(" | ")
        elif word == "tab":
            self.emit("\t")
        elif word in RTF_SPECIAL_CHARACTERS:
            self.emit(RTF_SPECIAL_CHARACTERS[word])
        elif word == "f" and argument:
            self.flush()
            self.font = int(argument)
        elif word == "u" and argument:
            value = int(argument)
            character = chr(value + UNICODE_LIMIT if value < 0 else value)
            stored_byte = self._stored_byte(character)
            if stored_byte is None:
                self.emit(character)
            else:
                self.pending.append(stored_byte)
            return self.skip_fallback(index)
        elif word == "uc" and argument:
            self.fallback_units = int(argument)
        return index

    def _stored_byte(self, character: str) -> int | None:
        r"""Return the byte a \uN character really stands for, or None if it is a character.

        Some RTF writers stored bytes as Unicode code points: \u150 for the cp1252 byte
        0x96 (an en dash), and Shift-JIS pairs as \u129 + a cp1252 character
        (\u129\u732 is 0x81 0x98, "§"). Such bytes go back among the text bytes, where
        the font's code page and the Shift-JIS pair rule decode them.
        """
        if ord(character) in C1_CONTROL_RANGE:
            return ord(character)
        if not self.pending.endswith(SHIFT_JIS_LEAD):
            return None
        try:
            encoded = character.encode(STORED_BYTES_CODEC)
        except UnicodeEncodeError:
            return None
        return encoded[0] if len(encoded) == 1 else None

    def backslash(self, index: int) -> int:
        """Handle the sequence that starts with a backslash; return the next position."""
        following = self.data[index + 1 : index + 2]
        if following in (b"\\", b"{", b"}"):
            if not self.is_skipping:
                self.pending.extend(following)
            return index + 2
        if following == b"'":
            hex_digits = self.data[index + 2 : index + 4]
            if not self.is_skipping and HEX_PAIR.fullmatch(hex_digits):
                self.pending.append(int(hex_digits, 16))
            return index + 4
        if following == b"*":
            self.is_skipping = True
            return index + 2
        if following in (b"~", b"_"):
            if not self.is_skipping:
                self.emit(" " if following == b"~" else "-")
            return index + 2
        match = CONTROL_WORD.match(self.data, index + 1)
        if not match:
            return index + 2
        word, argument = match.group(1).decode(), match.group(2)
        glued_word = _glued_control_word(word, argument)
        if glued_word:
            # The rest of the run (and any number after it) is text, read from here on.
            return self.control_word(glued_word, None, index + 1 + len(glued_word))
        return self.control_word(word, argument, match.end())

    def read(self) -> str:
        """Return the running text of the whole file."""
        index = 0
        while index < len(self.data):
            character = self.data[index : index + 1]
            if character == b"{":
                self.flush()
                self.stack.append((self.is_skipping, self.fallback_units, self.font))
                index += 1
            elif character == b"}":
                self.flush()
                if self.stack:
                    self.is_skipping, self.fallback_units, self.font = self.stack.pop()
                index += 1
            elif character == b"\\":
                index = self.backslash(index)
            else:
                if character not in (b"\r", b"\n") and not self.is_skipping:
                    self.pending.extend(character)
                index += 1
        self.flush()
        text = "".join(self.output)
        # Characters outside the basic plane arrive as two \u halves; this joins them.
        text = text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
        return re.sub(r"\n{3,}", "\n\n", text)


def rtf_to_text(path: Path) -> str:
    """Return the running text of an RTF file.

    Args:
        path: The .rtf file.

    Returns:
        The plain text. Words decoded with a wrongly declared non-Latin font charset
        (e.g. Arabic for Hungarian text) are repaired; see `encoding_repair`.
    """
    text = _RtfReader(path.read_bytes()).read()
    text, _, _ = repair_document(text, CONVERTED_MIN_DAMAGED_WORDS, CONVERTED_MIN_SHARE)
    return text


def to_text(path: Path) -> str:
    """Convert a .docx or .rtf file to plain text, choosing the reader by file extension."""
    if path.suffix.lower() == ".docx":
        return docx_to_text(path)
    if path.suffix.lower() == ".rtf":
        return rtf_to_text(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")
