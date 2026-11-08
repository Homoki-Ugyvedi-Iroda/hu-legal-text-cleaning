"""Tests for joining words split by a false space."""

from hu_legal_cleaning.false_spaces import join_false_spaces

JOINS = {"magy ar", "s zámú", "i ndokolás", "ítélet et", "es és", "pont ba"}


def test_listed_pairs_are_joined_keeping_their_letters():
    text, joined = join_false_spaces("A MAGY AR állam 12. s zámú ítélet et.\nI ndokolás", JOINS)
    assert text == "A MAGYAR állam 12. számú ítéletet.\nIndokolás"
    assert joined == 4


def test_pair_after_a_hyphen_or_before_a_bracket_stays():
    text = "a PN10-es és a 2-es és, valamint a c) pont ba) alpontja"
    assert join_false_spaces(text, JOINS) == (text, 0)


def test_pair_across_a_line_end_stays():
    text = "magy\nar"
    assert join_false_spaces(text, JOINS) == (text, 0)


def test_protected_span_stays():
    text = "„magy ar” és magy ar"
    fixed, joined = join_false_spaces(text, JOINS, protected_spans=[(0, 9)])
    assert fixed == "„magy ar” és magyar"
    assert joined == 1


def test_abbreviation_in_capitals_before_a_lowercase_word_stays():
    text = "az AB a határozatában"
    assert join_false_spaces(text, {"ab a"}) == (text, 0)
