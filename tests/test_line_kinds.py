from hu_legal_cleaning.line_kinds import (
    ends_in_abbreviation,
    is_abbreviation,
    lowercase_start_cause,
)


def test_is_abbreviation_statute_is_case_sensitive():
    assert is_abbreviation("Be.")
    assert not is_abbreviation("be.")


def test_ends_in_abbreviation():
    assert ends_in_abbreviation("az 1998.")
    assert ends_in_abbreviation("a hrsz.")
    assert not ends_in_abbreviation("a bíróság döntött.")


def test_lowercase_start_cause_placeholder():
    cause = lowercase_start_cause("Tanúként meghallgatta", "név9: elmondta")
    assert cause == "anonymiser_placeholder"


def test_lowercase_start_cause_signature_and_list_item():
    assert lowercase_start_cause("Dr. Minta Anna s.k.", "bíró") == "signature_block"
    assert lowercase_start_cause("A vádlott", "a) bűnös") == "list_item"


def test_lowercase_start_cause_wrap_after_abbreviation():
    cause = lowercase_start_cause("a hrsz.", "alatti ingatlan")
    assert cause == "wrap_after_abbrev_or_number"
