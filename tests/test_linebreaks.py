from hu_legal_cleaning.linebreaks import (
    JOINED_PLAIN,
    JOINED_UNSURE,
    HyphenPair,
    classify_pair,
    find_hyphen_pairs,
    hold_reason,
    hyphen_join,
    join_hyphenated_lines,
    number_join,
    spelled_join,
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


KNOWN_WORDS = {
    "összegére", "személlyel", "felperes", "ingatlan-nyilvántartásba", "megfelelnek-e",
    "rendőr-főkapitányság", "Rendőr-főkapitányság", "szerint-a",
}  # fmt: skip


def _is_known(word: str) -> bool:
    return word in KNOWN_WORDS


def test_spelled_join_restores_a_doubled_digraph():
    assert spelled_join("ösz", "szegére", _is_known) == ("összegére", JOINED_PLAIN)
    assert spelled_join("személy", "lyel", _is_known) == ("személlyel", JOINED_PLAIN)


def test_spelled_join_keeps_required_hyphens():
    assert spelled_join("megfelelnek", "e", _is_known)[0] == "megfelelnek-e"
    assert spelled_join("Ft", "ban", _is_known)[0] == "Ft-ban"
    assert spelled_join("ingatlan", "nyilvántartásba", _is_known)[0] == ("ingatlan-nyilvántartásba")


def test_spelled_join_plain_and_unsure():
    assert spelled_join("fel", "peres", _is_known) == ("felperes", JOINED_PLAIN)
    assert spelled_join("tárgyalá", "lon", _is_known) == ("tárgyalálon", JOINED_UNSURE)


def test_number_join_puts_hyphen_after_group_word_above_two_thousand():
    assert number_join("hetvenháromezer", "nyolcszáz") == "hetvenháromezer-nyolcszáz"
    assert number_join("négy", "millió") == "négymillió"
    assert number_join("ezer", "kétszáz") == "ezerkétszáz"
    assert number_join("alma", "fa") is None


def test_hyphen_join_keeps_compounds_on_one_line():
    assert hyphen_join("Rendőr", "főkapitányság", _is_known) == "Rendőr-főkapitányság"
    assert hyphen_join("Ft", "ot", _is_known) == "Ft-ot"
    assert hyphen_join("állag", "és", _is_known) == "állag- és"
    assert hyphen_join("külön", "külön", _is_known) == "külön-külön"


def test_hyphen_join_leaves_layout_breaks_and_dashes():
    assert hyphen_join("vádlott", "bűnös", _is_known) is None
    assert hyphen_join("XX", "bűnös", _is_known) is None
    assert hyphen_join("ellen", "közigazgatási", _is_known) is None
    assert hyphen_join("szerint", "a", _is_known) is None


def test_join_hyphenated_lines_with_written_forms_and_blank_lines():
    lines = ["a teljes ösz-", "  ", "szegére és a", "Rendőr-", "főkapitányság"]
    joins = {("ösz", "szegére"): "összegére", ("Rendőr", "főkapitányság"): "Rendőr-főkapitányság"}
    assert join_hyphenated_lines(lines, joins) == [
        "a teljes ösz-", "  ", "szegére és a", "Rendőr-főkapitányság"
    ]  # fmt: skip
    assert join_hyphenated_lines(lines, joins, across_blank_lines=True) == [
        "a teljes összegére és a", "Rendőr-főkapitányság"
    ]  # fmt: skip
