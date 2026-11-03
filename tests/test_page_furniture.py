"""Tests for removing page numbers and running case-number headers."""

from hu_legal_cleaning.page_furniture import (
    CASE_NUMBER,
    PAGE_NUMBER,
    REJOINED,
    find_removals,
    is_page_number,
    remove_page_furniture,
)


def test_is_page_number_forms():
    for line in ("- 2 -", "-12-", "- 3-", "3 / 6 oldal", "2/4 oldal", "7/2.", "3/3", "  4 "):
        assert is_page_number(line), line
    for line in (
        "--- 0 ---",
        "023/6",
        "8/3",
        "2316. oldal",
        "(nyomozati iratok 5. oldal)",
        "1.",
        "1234",
    ):
        assert not is_page_number(line), line


def test_only_repeated_case_numbers_are_removed():
    lines = [
        "SZEGEDI ÍTÉLŐTÁBLA",
        "Pf.III.20.106/2013/8. szám",
        "Szöveg.",
        "Pf.III.20.106/2013/8.szám",
        "Btk. 79. §,",
        "Btk. 79. §,",
        "SZEGEDI ÍTÉLŐTÁBLA",
    ]
    removals = find_removals(lines)
    assert [(r.line_number, r.kind) for r in removals] == [(4, CASE_NUMBER)]


def test_page_header_inside_a_sentence_is_removed_and_sentence_rejoined():
    text = "a felperes\n\n- 2 -\n\nPf.III.20.106/2013/8. szám\n\nkeresetét elutasította.\nVége."
    text = "Pf.III.20.106/2013/8. szám\n" + text
    fixed, changes, _ = remove_page_furniture(text)
    assert fixed == "Pf.III.20.106/2013/8. szám\na felperes keresetét elutasította.\nVége."
    assert changes[PAGE_NUMBER] == 1
    assert changes[CASE_NUMBER] == 1
    assert changes[REJOINED] == 1


def test_page_number_between_paragraphs_keeps_one_blank_line_and_crlf():
    text = "Első bekezdés.\r\n\r\n-3-\r\n\r\nMásodik bekezdés.\r\n"
    fixed, changes, _ = remove_page_furniture(text)
    assert fixed == "Első bekezdés.\r\n\r\nMásodik bekezdés.\r\n"
    assert changes[REJOINED] == 0


def test_page_number_without_blank_lines_and_new_sentence():
    fixed, _, _ = remove_page_furniture("Első mondat.\n4\nMásodik mondat.")
    assert fixed == "Első mondat.\nMásodik mondat."


def test_text_without_furniture_is_unchanged():
    text = "A Kúria\n--- 0 ---\nA Kúria"
    assert remove_page_furniture(text)[0] == text


def test_list_item_after_a_page_break_is_not_joined():
    fixed, changes, _ = remove_page_furniture(
        "az alábbiak szerint\n- 2 -\nb) a kereset elutasítása"
    )
    assert fixed == "az alábbiak szerint\nb) a kereset elutasítása"
    assert changes[REJOINED] == 0


def test_reference_list_item_is_not_a_page_number():
    lines = [
        "sérelmére:",
        "- 1/12. L.A.",
        "R. sérelmére folytatólagosan:",
        "1/9.",
        "1/15. C.F.",
        "II/5. F.Z.",
    ]
    assert find_removals(lines) == []
    assert [r.text for r in find_removals(["Szöveg.", "3/1.", "Szöveg."])] == ["3/1."]
