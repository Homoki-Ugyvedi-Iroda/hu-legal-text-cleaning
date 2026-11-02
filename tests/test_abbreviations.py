from hu_legal_cleaning.abbreviations import (
    DotFollowers,
    audit_abbreviations,
    count_dot_followers,
    load_corpus_abbreviations,
    load_statute_abbreviations,
)


def test_audit_finds_abbreviation_followed_by_lowercase():
    followers = DotFollowers()
    count_dot_followers(["a hrsz. alatti ingatlan"] * 40 + ["a Ptk. 6:519. §"] * 40, followers)
    verdicts = {row.token: row.verdict for row in audit_abbreviations(followers)}
    assert verdicts["hrsz"] == "likely_abbreviation"
    assert verdicts["ptk"] == "usually_before_number"


def test_audit_skips_rare_words():
    followers = DotFollowers()
    count_dot_followers(["a ritk. szó"], followers)
    assert audit_abbreviations(followers) == []


def test_bundled_lists_load():
    assert "Ptk" in load_statute_abbreviations()
    assert "hrsz" in load_corpus_abbreviations("legal")
    assert "kb" in load_corpus_abbreviations("general")
