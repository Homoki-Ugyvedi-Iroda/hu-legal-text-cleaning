from collections import Counter

from hu_legal_cleaning.line_starts import (
    LineStartCounts,
    count_line_starts,
    find_lost_letter_candidates,
    fix_line_starts,
    join_line_start,
    starts_sentence,
)


def test_count_line_starts_skips_capital_headings():
    counts = LineStartCounts(Counter(), Counter())
    count_line_starts(["Sértett elmondta.", "értett1 szerint", "ÍTÉLET"], counts)
    assert counts.lowercase == Counter({"értett": 1})
    assert counts.capitalised == Counter({"sértett": 1})


def test_count_line_starts_ignores_wrapped_lines():
    counts = LineStartCounts(Counter(), Counter())
    count_line_starts(["Ez a döntés, amely", "mellett nem áll.", "értett szerint"], counts)
    assert counts.lowercase == Counter({"értett": 1})


def test_starts_sentence():
    assert starts_sentence(None)
    assert starts_sentence("")
    assert starts_sentence("Vége a mondatnak.  ")
    assert not starts_sentence("a mondat folytatódik, amely")


def test_find_lost_letter_candidates_finds_rare_lowercase_form():
    counts = LineStartCounts(Counter({"értett": 50}), Counter({"sértett": 4000}))
    [candidate] = find_lost_letter_candidates(counts)
    assert candidate.damaged == "értett"
    assert candidate.probable_word == "Sértett"
    assert candidate.lost_letters == "s"


def test_find_lost_letter_candidates_ignores_common_lowercase_word():
    counts = LineStartCounts(Counter({"illetve": 900}), Counter({"pilletve": 1000}))
    assert find_lost_letter_candidates(counts) == []


def test_fix_line_starts_changes_first_word_only():
    lines, changed = fix_line_starts(["  értett szerint értett", "a értett"], {"értett": "Sértett"})
    assert lines == ["  Sértett szerint értett", "a értett"]
    assert changed == 1


def _known(word: str) -> bool:
    return word in {"szerint", "forgalmi", "e körben"}


def test_join_line_start_joins_split_word_across_blank_line():
    lines = ["a törvény sze", "  ", "rint a bíróság", "ennek for-", "galmi oka"]
    joined, changes = join_line_start(lines, "rint", _known)
    assert joined == ["a törvény szerint a bíróság", "ennek for-", "galmi oka"]
    assert changes == ["szerint"]
    assert join_line_start(lines, "galmi", _known)[0][-1] == "ennek forgalmi oka"


def test_join_line_start_leaves_unknown_joins():
    lines = ["a kérelem", "rint a bíróság"]
    assert join_line_start(lines, "rint", _known) == (lines, [])


def test_join_line_start_with_expected_word():
    lines = ["lakott Mosonmagyar-", "óvár városban.", "A tanú", "óvár lakosa."]
    joined, changes = join_line_start(lines, "óvár", _known, expected="Mosonmagyaróvár")
    assert joined == ["lakott Mosonmagyaróvár városban.", "A tanú", "Mosonmagyaróvár lakosa."]
    assert sorted(changes) == ["Mosonmagyaróvár", "Mosonmagyaróvár"]


def test_join_line_start_with_space():
    lines = ["és e", "körben a bíróság", "a megadott", "körben"]
    joined = join_line_start(lines, "körben", _known, with_space=True)[0]
    assert joined == ["és e körben a bíróság", "a megadott", "körben"]
