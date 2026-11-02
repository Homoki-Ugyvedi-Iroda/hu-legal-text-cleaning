"""Tests for the overview of unusual characters."""

from hu_legal_cleaning import characters
from hu_legal_cleaning.text_files import write_text


def test_kind_of():
    assert characters.kind_of("�") == "replacement character"
    assert characters.kind_of("́") == "combining mark"
    assert characters.kind_of("­") == "invisible format character"
    assert characters.kind_of(" ") == "space variant"
    assert characters.kind_of("„") == "punctuation"
    assert characters.kind_of("µ") == "symbol or number" or characters.kind_of("µ")
    assert characters.kind_of("Е") == "other script letter (Cyrillic)"
    assert characters.kind_of("ç") == "Latin letter outside Hungarian"


def test_scan_characters_counts_and_gives_context(tmp_path):
    root = tmp_path / "in"
    write_text(root / "2010" / "a.txt", "első sor\nA „idézet” és á jel „.\n")
    write_text(root / "2012" / "b.txt", "csak ő és „ itt\n")
    stats = characters.scan_characters(root)
    assert "ő" not in stats and "á" not in stats
    quote = stats["„"]
    assert (quote.count, quote.documents) == (3, 2)
    assert [example.year for example in quote.examples] == ["2010", "2012"]
    assert quote.examples[0].before == "A " and quote.examples[0].line_number == 2
    assert stats["́"].kind == "combining mark"


def test_build_character_page_contains_the_data(tmp_path):
    root = tmp_path / "in"
    write_text(root / "2010" / "a.txt", "szöveg „ jel\n")
    page = characters.build_character_page(characters.scan_characters(root), "my_key")
    assert "U+201E" in page and "my_key" in page
