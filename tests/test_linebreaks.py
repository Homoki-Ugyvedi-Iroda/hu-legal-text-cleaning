from hu_legal_cleaning.linebreaks import (
    HyphenPair,
    classify_pair,
    find_hyphen_pairs,
    hold_reason,
    join_hyphenated_lines,
)

KNOWN = {"szerint", "sze", "magánokirat", "hamisítás"}


def is_known(word):
    return word in KNOWN


def test_find_hyphen_pairs_skips_blank_line():
    lines = ["a törvény sze-", "", "rint eljárt", "Vége."]
    assert find_hyphen_pairs(lines) == [HyphenPair("sze", "rint", 0, False)]


def test_find_hyphen_pairs_needs_lowercase_start():
    assert find_hyphen_pairs(["XY Kft-", "Budapest"]) == []


def test_classify_pair_join():
    assert classify_pair("sze", "rint", is_known) == "join"


def test_classify_pair_keep_hyphen():
    assert classify_pair("magánokirat", "hamisítás", is_known) == "keep_hyphen"


def test_classify_pair_unresolved():
    assert classify_pair("Ková", "csnak", is_known) == "unresolved"


def test_hold_reason_number_words():
    assert hold_reason("huszonöt", "ezer") == "spelled-out number"


def test_hold_reason_role_word_before_verdict():
    assert hold_reason("vádlott", "bűnös") == "role word before a verdict or label"


def test_hold_reason_ordinary_pair():
    assert hold_reason("sze", "rint") == ""


def test_join_hyphenated_lines_appends_rest_of_next_line():
    lines = ["a törvény sze-", "rint eljárt.", "Vége."]
    joined = join_hyphenated_lines(lines, {("sze", "rint")})
    assert joined == ["a törvény szerint eljárt.", "Vége."]


def test_join_hyphenated_lines_ignores_unapproved_pairs():
    lines = ["vádlott-", "bűnös"]
    assert join_hyphenated_lines(lines, set()) == lines
