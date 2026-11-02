import zipfile

import pytest

from hu_legal_cleaning.convert import docx_to_text, rtf_to_text, to_text

DOCX_BODY = (
    '<?xml version="1.0"?><w:document xmlns:w="w"><w:body>'
    "<w:p><w:r><w:t>Az ítélet jogerős.</w:t></w:r></w:p>"
    "<w:tbl><w:tr><w:tc><w:p><w:t>Név</w:t></w:p></w:tc><w:tc><w:p><w:t>Összeg</w:t></w:p></w:tc></w:tr></w:tbl>"
    "<w:p><w:del><w:t>törölt</w:t></w:del><w:t>Vége &amp; pont</w:t></w:p>"
    "</w:body></w:document>"
)


def make_docx(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", DOCX_BODY)
    return path


def test_docx_to_text_keeps_paragraphs_and_table_cells(tmp_path):
    text = docx_to_text(make_docx(tmp_path / "d.docx"))
    assert "Az ítélet jogerős.\n" in text
    assert "| Név | Összeg | \n" in text
    assert "törölt" not in text
    assert "Vége & pont" in text


def test_rtf_to_text_decodes_central_european_font(tmp_path):
    rtf = (
        rb"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fcharset238 Times;}}"
        rb"{\header Fejl\'e9c}\f0 A b\'edr\'f3s\'e1g d\'f6nt\'f6tt.\par Ok\'f5r\'f5s.}"
    )
    path = tmp_path / "d.rtf"
    path.write_bytes(rtf)
    assert rtf_to_text(path) == "A bíróság döntött.\nOkőrős."


def test_rtf_to_text_unicode_and_section_sign(tmp_path):
    rtf = rb"{\rtf1\ansi\uc1 Pp. 1\u167?(1) bek. \'81\'98 \endash v\u337\'3fs}"
    path = tmp_path / "u.rtf"
    path.write_bytes(rtf)
    # The space after a control word such as \endash belongs to the control word.
    assert rtf_to_text(path) == "Pp. 1§(1) bek. § –vős"


def test_to_text_rejects_other_files(tmp_path):
    with pytest.raises(ValueError):
        to_text(tmp_path / "d.pdf")


def test_rtf_to_text_ignores_a_wrongly_declared_arabic_font(tmp_path):
    rtf = (
        rb"{\rtf1\ansi\ansicpg1250\deff0{\fonttbl{\f0\fcharset238 Times;}"
        rb"{\f3\fcharset178 Times New Roman;}}"
        rb"\f3 A b\'edr\'f3s\'e1g hat\'e1rozata.}"
    )
    path = tmp_path / "d.rtf"
    path.write_bytes(rtf)
    assert rtf_to_text(path) == "A bíróság határozata."


def test_rtf_to_text_keeps_real_greek_text(tmp_path):
    rtf = (
        rb"{\rtf1\ansi\ansicpg1250\deff0{\fonttbl{\f0\fcharset161 Times;}}\f0 \'eb\'fc\'e3\'ef\'f2}"
    )
    path = tmp_path / "d.rtf"
    path.write_bytes(rtf)
    assert rtf_to_text(path) == "λόγος"


def _convert(tmp_path, rtf: bytes) -> str:
    path = tmp_path / "d.rtf"
    path.write_bytes(rtf)
    return rtf_to_text(path)


def test_rtf_to_text_reads_western_font_as_cp1252(tmp_path):
    rtf = (
        rb"{\rtf1\ansi\ansicpg1250\deff0{\fonttbl{\f0\fcharset238 Times New Roman CE;}"
        rb"{\f1\fcharset0 Times New Roman;}}\f0 a lak\'e1s \f1\'bc\f0  r\'e9sze, 5 m\f1\'b3}"
    )
    assert _convert(tmp_path, rtf) == "a lakás ¼ része, 5 m³"


def test_rtf_to_text_keeps_greek_symbol_next_to_latin_letter(tmp_path):
    rtf = (
        rb"{\rtf1\ansi\ansicpg1250\deff0{\fonttbl{\f0\fcharset238 Times New Roman CE;}"
        rb"{\f1\fcharset161 Times New Roman Greek;}}\f0 2,24\f1  \'ecg/ml}"
    )
    assert _convert(tmp_path, rtf) == "2,24 μg/ml"


def test_rtf_to_text_maps_symbol_font_to_unicode(tmp_path):
    rtf = (
        rb"{\rtf1\ansi\ansicpg1250\deff0{\fonttbl{\f0\fcharset238 Arial CE;}"
        rb"{\f1\fcharset238 Symbol;}}\f0 KING \f1\'d2\f0  MILANO, 5 \f1 m\f0 g}"
    )
    assert _convert(tmp_path, rtf) == "KING ® MILANO, 5 μg"


def test_rtf_to_text_gives_picture_font_private_use_codes(tmp_path):
    rtf = (
        rb"{\rtf1\ansi\ansicpg1250\deff0{\fonttbl{\f0\fcharset238 Arial CE;}"
        rb"{\f2\fnil\fcharset2 Wingdings;}}\f2\'d8\tab\f0 t\'e9tel}"
    )
    assert _convert(tmp_path, rtf) == "\ttétel"


def test_rtf_to_text_reads_openoffice_symbol_font_as_cp1252(tmp_path):
    rtf = (
        rb"{\rtf1\ansi\ansicpg1250\deff0{\fonttbl{\f0\fcharset238 Arial CE;}"
        rb"{\f1\fcharset2 OpenSymbol;}}\f1\'95\f0  t\'e9tel}"
    )
    assert _convert(tmp_path, rtf) == "• tétel"


def test_rtf_to_text_reads_bytes_stored_as_unicode(tmp_path):
    rtf = (
        rb"{\rtf1\ansi\ansicpg1250\deff0{\fonttbl{\f0\fcharset238 Times New Roman CE;}}"
        rb"\f0 Ptk. 61. \u129?\u732?-a, payment\u129?h, vezet\u337?i \u150? munka}"
    )
    assert _convert(tmp_path, rtf) == "Ptk. 61. §-a, payment”, vezetői – munka"
