from hu_legal_cleaning.evaluation import (
    BoundaryScore,
    boundaries,
    evaluate_splitter,
    load_gold_passages,
    score_boundaries,
)
from hu_legal_cleaning.sentences import (
    ends_in_abbreviation,
    is_abbreviation,
    join_wrapped_lines,
    lowercase_start_cause,
    split_paragraph,
    split_sentences,
    split_with_causes,
)


def test_split_sentences_keeps_abbreviations_and_ordinals():
    text = "A Ptk. 6:519. §-a szerint felel. A 2015. évi döntés kb. tíz oldal."
    assert split_sentences(text) == [
        "A Ptk. 6:519. §-a szerint felel.",
        "A 2015. évi döntés kb. tíz oldal.",
    ]


def test_split_paragraph_statute_before_capitalised_word_ends_sentence():
    assert split_paragraph("Alkalmazni kell a Ptk. Ezért a bíróság döntött.") == [
        "Alkalmazni kell a Ptk.",
        "Ezért a bíróság döntött.",
    ]


def test_join_wrapped_lines_after_abbreviation():
    assert join_wrapped_lines("a hrsz.\nalatti ingatlan") == ["a hrsz. alatti ingatlan"]


def test_join_wrapped_lines_keeps_list_items_apart():
    assert join_wrapped_lines("A vádlott\na) bűnös") == ["A vádlott", "a) bűnös"]


def test_is_abbreviation_statute_is_case_sensitive():
    assert is_abbreviation("Be.")
    assert not is_abbreviation("be.")


def test_ends_in_abbreviation():
    assert ends_in_abbreviation("az 1998.")
    assert not ends_in_abbreviation("a bíróság döntött.")


def test_lowercase_start_cause_placeholder():
    cause = lowercase_start_cause("Tanúként meghallgatta", "név9: elmondta")
    assert cause == "anonymiser_placeholder"


def test_split_with_causes_tags_signature_line():
    tagged = split_with_causes("Dr. Minta Anna s.k.\nbíró")
    assert tagged[-1] == ("bíró", "signature_block")


def test_boundaries_ignore_whitespace():
    assert boundaries(["A b.", "C d."]) == {3, 6}


def test_score_boundaries():
    assert score_boundaries([{3, 6}], [{3, 6, 9}]) == BoundaryScore(100.0, 66.7, 80.0)


def test_gold_passages_load():
    assert len(load_gold_passages()) == 40


def test_splitter_on_gold_set():
    assert evaluate_splitter(split_sentences).f1 >= 99.0
