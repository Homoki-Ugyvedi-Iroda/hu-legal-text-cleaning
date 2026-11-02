"""Tests for applying the character decisions."""

from hu_legal_cleaning.character_decisions import (
    apply_character_decisions,
    dictionary_candidates,
    dictionary_replacements,
    is_separator_line,
    remove_separator_lines,
)

DECISIONS = {
    " ": {"decision": "remove", "replacement": ""},
    " ": {"decision": "remove", "replacement": ""},
    "®": {"decision": "remove", "replacement": ""},
    "»": {"decision": "replace", "replacement": '"'},
    "а": {"decision": "replace", "replacement": "a"},
    "Ľ": {"decision": "replace", "replacement": "1/4"},
    "Ò": {"decision": "replace", "replacement": "Ó"},
    "ä": {"decision": "keep", "replacement": ""},
}


def test_is_separator_line():
    assert is_separator_line("ج ج ج ج")
    assert is_separator_line("ÒÒÒÒÒ")
    assert not is_separator_line("-----")
    assert not is_separator_line("———")
    assert not is_separator_line("Schäfer")


def test_remove_separator_lines_keeps_carriage_returns():
    assert remove_separator_lines("a\r\nججج\r\nb") == ("a\r\n\r\nb", 1)


def test_spaces_become_ordinary_spaces():
    text, changes = apply_character_decisions("a b c ®", DECISIONS)
    assert text == "a b\nc "
    assert changes[" "] == 1


def test_cyrillic_lookalike_only_on_latin_lines():
    text, _ = apply_character_decisions("ez а szerződés\nВідмова а країни", DECISIONS)
    assert text == "ez a szerződés\nВідмова а країни"


def test_fraction_only_apart_from_letters():
    text, _ = apply_character_decisions("a lakás Ľ része, bíĽóság, 2Ľ év", DECISIONS)
    assert text == "a lakás 1/4 része, bíĽóság, 2 1/4 év"


def test_separator_line_wins_over_letter_decision():
    text, changes = apply_character_decisions("ÒÒÒÒÒ\nÒra", DECISIONS)
    assert text == "\nÓra"
    assert changes["separator line"] == 1


def test_dictionary_replacements_need_exactly_one_known_form():
    known = {"egészségbiztosítási", "megfelelő", "şi"}
    candidates = {"ĺ": ["í", "l"], "ş": ["s"]}
    text = "egészségbiztosĺtási, megfeleĺő és şi"
    assert "megfelelő" in dictionary_candidates(text, candidates)
    fixed, changes = dictionary_replacements(text, candidates, lambda w: w in known)
    assert fixed == "egészségbiztosítási, megfelelő és şi"
    assert changes["ĺ"] == 2
