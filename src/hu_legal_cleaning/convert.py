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

from hu_legal_cleaning.encoding_repair import is_mixed_script, repair_document

# --- DOCX ---------------------------------------------------------------------

DOCX_BODY = "word/document.xml"


def _docx_cell(match: re.Match[str]) -> str:
    cell = match.group(1).replace("</w:p>", " ")
    cell = re.sub(r"<w:tab/>|<w:br\b[^>]*/>", " ", cell)
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
    xml = xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t")
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
# RTF font character set number -> Python codec. 238 is Central European (Hungarian);
# 128 is Japanese Shift-JIS, which some anonymisation tools used for "…" and "§".
FONT_CHARSET_CODECS = {
    238: "cp1250", 128: "cp932", 204: "cp1251", 161: "cp1253", 162: "cp1254",
    186: "cp1257", 163: "cp1258", 177: "cp1255", 178: "cp1256", 129: "cp949",
    134: "gb2312", 136: "cp950", 222: "cp874",
}  # fmt: skip
SHIFT_JIS_CODEC = "cp932"
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
HEX_PAIR = re.compile(rb"[0-9a-fA-F]{2}")
UNICODE_LIMIT = 65536


def _cp1252_fallback(error: UnicodeDecodeError) -> tuple[str, int]:
    # Bytes undefined in the document's code page (e.g. 0x98 in cp1250) come from cp1252.
    return error.object[error.start : error.end].decode("cp1252", "replace"), error.end


# Registers the handler under a name, so that bytes.decode(codec, name) can use it.
codecs.register_error(FALLBACK_ERROR_HANDLER, _cp1252_fallback)


def _default_codec(data: bytes) -> str:
    """Return the document's code page; a Central European font means cp1250."""
    if b"fcharset238" in data:
        return "cp1250"
    declared = re.search(rb"\\ansicpg(\d+)", data)
    return "cp" + (declared.group(1).decode() if declared else "1250")


def _font_codecs(data: bytes, default: str) -> dict[int, str]:
    """Return font number -> codec, read from the charset of each font in the font table."""
    start = re.search(rb"\{\\fonttbl", data)
    if not start:
        return {}
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
    codecs_by_font: dict[int, str] = {}
    font = None
    table = data[start.start() : index]
    for token in re.finditer(rb"\\f(\d+)(?![0-9a-zA-Z])|\\fcharset(\d+)", table):
        if token.group(1) is not None:
            font = int(token.group(1))
            codecs_by_font.setdefault(font, default)
        elif font is not None:
            codecs_by_font[font] = FONT_CHARSET_CODECS.get(int(token.group(2)), default)
    return codecs_by_font


def _shift_jis_sign(pair: bytes) -> str | None:
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
    if codec == SHIFT_JIS_CODEC:
        return raw.decode(SHIFT_JIS_CODEC, "replace")
    pieces, start = [], 0
    for match in SHIFT_JIS_PAIR.finditer(raw):
        sign = _shift_jis_sign(match.group(0))
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
    not mix scripts inside words, so it keeps its font's code page.
    """
    text = _decode(raw, codec)
    if codec not in NON_LATIN_CODECS or codec == default_codec:
        return text
    if not any(is_mixed_script(word) for word in text.split()):
        return text
    return _decode(raw, default_codec)


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
            self.emit(chr(value + UNICODE_LIMIT if value < 0 else value))
            return self.skip_fallback(index)
        elif word == "uc" and argument:
            self.fallback_units = int(argument)
        return index

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
        return self.control_word(match.group(1).decode(), match.group(2), match.end())

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
