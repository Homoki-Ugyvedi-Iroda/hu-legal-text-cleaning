"""Tests for the small fixed-pattern fixes."""

from hu_legal_cleaning.leftovers import (
    COMPOUND_FIX,
    EMPTY_ROW_FIX,
    GLUED_LABEL_FIX,
    LINK_CODE_FIX,
    QUOTE_FIX,
    fix_leftovers,
    glued_label_words,
)


def test_glued_label_gets_a_space():
    text, changes = fix_leftovers("I. r. vádlott neveI. r. vádlott és vádlott neveII.rendű")
    assert text == "I. r. vádlott neve I. r. vádlott és vádlott neve II.rendű"
    assert changes[GLUED_LABEL_FIX] == 2


def test_label_inside_a_word_is_left_for_a_person():
    text = "kereseti kérelmet terjeI. rendű alperesi érdekelttt elő, és neveI. r."
    fixed, changes = fix_leftovers(text, is_known=lambda word: word != "terje")
    assert fixed == "kereseti kérelmet terjeI. rendű alperesi érdekelttt elő, és neve I. r."
    assert changes[GLUED_LABEL_FIX] == 1


def test_short_fragment_before_a_label_is_left():
    text = "a cselekmény kapcsán nem tX.rendű vádlott, és aI. r. vádlott"
    fixed, _ = fix_leftovers(text)
    assert fixed == "a cselekmény kapcsán nem tX.rendű vádlott, és a I. r. vádlott"


def test_glued_label_words():
    assert glued_label_words("neveI. r. vádlott, ugyaI. r. és IlI. r.") == {"neve", "ugya", "Il"}


def test_misread_numeral_is_not_split():
    text = "IlI. r. vádlott, XlI. r. vádlott"
    assert fix_leftovers(text) == (text, {})


def test_joined_compounds_are_split():
    text, changes = fix_leftovers("A MAGYAR KÖZTÁRSASÁGNEVÉBEN! a kijavítóvégzést")
    assert text == "A MAGYAR KÖZTÁRSASÁG NEVÉBEN! a kijavító végzést"
    assert changes[COMPOUND_FIX] == 2


def test_link_code_is_removed_even_across_a_line_end():
    text, changes = fix_leftovers(
        "(Pp. 235. § <cdp://1/95200003.TV/235/> (1) bekezdés) a Karta <javasc\n"
        "ript:LinkUgrik('A0900006.TV','','lawref')> tehát"
    )
    assert text == "(Pp. 235. § (1) bekezdés) a Karta tehát"
    assert changes[LINK_CODE_FIX] == 2


def test_empty_table_rows_are_removed_and_crlf_kept():
    text, changes = fix_leftovers("a tanács elnöke |\r\n| |\r\nDr. Kiss Anna s. k. |\r\n")
    assert text == "a tanács elnöke |\r\nDr. Kiss Anna s. k. |\r\n"
    assert changes[EMPTY_ROW_FIX] == 1


def test_misread_closing_quote():
    text, changes = fix_leftovers("„forgalmazásához�h a „P.C.�h-ből �hol")
    assert text == "„forgalmazásához” a „P.C.”-ből �hol"
    assert changes[QUOTE_FIX] == 2
