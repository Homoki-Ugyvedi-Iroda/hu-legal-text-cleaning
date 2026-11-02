from collections import Counter

from hu_legal_cleaning.dictionary import (
    WordStats,
    collect_word_stats,
    edit_distance,
    group_word_families,
    is_abbreviation_or_suffix,
    is_anonymisation_leftover,
    is_name_like,
    is_probable_mistake,
)


def test_collect_word_stats_counts_name_evidence():
    stats = WordStats()
    collect_word_stats(["A tanú szerint Kovács Béla látta.", "dr. Kovács"], stats)
    assert stats.count["kovács"] == 2
    assert stats.name_evidence["kovács"] == 2
    assert is_name_like("kovács", stats)
    assert not is_name_like("tanú", stats)


def test_is_abbreviation_or_suffix():
    stats = WordStats()
    collect_word_stats(["a hrsz. alatti ingatlan, hrsz. szerint"], stats)
    assert is_abbreviation_or_suffix("hrsz", stats)


def test_is_anonymisation_leftover():
    assert is_anonymisation_leftover("nevetel")
    assert is_anonymisation_leftover("településra")
    assert not is_anonymisation_leftover("település")


def test_edit_distance():
    assert edit_distance("biróság", "bíróság") == 1


def test_is_probable_mistake_needs_frequent_close_suggestion():
    assert is_probable_mistake("biróság", "bíróság", Counter({"biróság": 3, "bíróság": 500}))
    assert not is_probable_mistake("biróság", "bíróság", Counter({"biróság": 3}))


def test_group_word_families_uses_shortest_form_as_head():
    families = group_word_families(["ellenkérelmet", "ellenkérelem", "védirat"])
    assert families == {"védirat": ["védirat"], "ellenkérelem": ["ellenkérelem", "ellenkérelmet"]}
