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
