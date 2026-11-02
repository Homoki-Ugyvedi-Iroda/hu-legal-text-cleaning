"""Tests for joining letter-spaced words and tidying whitespace."""

from collections import Counter

from hu_legal_cleaning.spacing import (
    join_letter_spaced,
    letter_spaced_forms,
    normalise_whitespace,
    repair_spaced_guilty,
    repair_spaced_headings,
)

KNOWN = {
    "Indokolás", "INDOKOLÁS", "ítéletet", "Ítéletet", "bűnös", "Magyar", "Köztársaság",
    "Kötelezi", "a", "tényállást", "etet", "ítél",
}  # fmt: skip


def is_known(word: str) -> bool:
    return word in KNOWN


def test_letter_spaced_heading_is_joined_before_punctuation():
    text, changes = join_letter_spaced("I n d o k o l á s :\nb ű n ö s.\no o o o :", is_known)
    assert text == "Indokolás:\nbűnös.\no o o o :"
    assert changes["Indokolás"] == 1


def test_double_space_marks_word_boundary():
    text, _ = join_letter_spaced("M a g y a r  K ö z t á r s a s á g", is_known)
    assert text == "Magyar Köztársaság"


def test_single_space_run_split_before_capitals():
    text, _ = join_letter_spaced("M a g y a r K ö z t á r s a s á g nevében", is_known)
    assert text == "Magyar Köztársaság nevében"


def test_pieces_broken_by_double_space_are_merged():
    text, _ = join_letter_spaced(
        "í t é l  e t e t, I  N D O K O L Á S", is_known, {"ítéletet"}.__contains__
    )
    assert text == "ítéletet, INDOKOLÁS"


def test_lost_accent_on_capital_i():
    text, _ = join_letter_spaced("I t é l e t e t", is_known)
    assert text == "Ítéletet"


def test_article_split_off_the_end():
    text, _ = join_letter_spaced("K ö t e l e z i a felperest", is_known)
    assert text == "Kötelezi a felperest"


def test_article_before_spaced_word_and_unknown_runs_stay():
    text = "a  t é n y á l l á s t, a b c d, o o o o o"
    joined, changes = join_letter_spaced(text, is_known)
    assert joined == "a tényállást, a b c d, o o o o o"
    assert sum(changes.values()) == 1


def test_letter_spaced_forms_lists_merges_and_variants():
    forms = letter_spaced_forms("í t é l  e t e t  M a g y a r K ö z t á r s a s á g")
    assert {"ítéletet", "ítél", "etet", "Magyar", "Köztársaság"} <= forms


def test_normalise_whitespace_keeps_blank_lines_and_crlf():
    text, changed = normalise_whitespace("  a\t\tb  \r\n\r\nc  d\nok")
    assert text == "a b\r\n\r\nc d\nok"
    assert changed == 2


def test_known_pieces_merge_only_when_common():
    known = KNOWN | {"kijavító", "végzést", "kijavítóvégzést", "ítéletet"}
    text = "k i j a v í t ó  v é g z é s t, í t é l  e t e t"
    joined, _ = join_letter_spaced(text, known.__contains__, {"ítéletet"}.__contains__)
    assert joined == "kijavító végzést, ítéletet"


def test_capital_split_needs_long_parts():
    known = KNOWN | {"Ja", "P"}
    joined, _ = join_letter_spaced("a J a P", known.__contains__)
    assert joined == "a J a P"


def test_repair_spaced_headings_damaged_forms():
    text = (
        "I N D OKOL Á S\nI n d o k o 1 á s:\nn d o k o l á s\nI D O K O L Á S :\n"
        "b ü n ö s: lopás bűntettében\nb ü n ö s ö k :\nb ű n ő s"
    )
    fixed, changes = repair_spaced_headings(text)
    assert fixed == (
        "INDOKOLÁS\nIndokolás:\nIndokolás\nINDOKOLÁS:\nbűnös: lopás bűntettében\nbűnösök:\nbűnös"
    )
    assert changes["INDOKOLÁS"] == 2


def test_repair_spaced_headings_leaves_other_lines():
    text = "a b c d\nA x M x S\nX X X X\nI t é l e t e k\nI n d o k o l á s I."
    assert repair_spaced_headings(text) == (text, Counter())


def test_repair_spaced_headings_keeps_lowercase_for_unaccented_i():
    assert repair_spaced_headings("i t é l e t e t :")[0] == "ítéletet:"


def test_repair_spaced_guilty_inside_a_line():
    text = "b ü n ö s a Btk. szerinti, b ű n ő s ö k - lopás"
    assert repair_spaced_guilty(text) == ("bűnös a Btk. szerinti, bűnösök - lopás", 2)
