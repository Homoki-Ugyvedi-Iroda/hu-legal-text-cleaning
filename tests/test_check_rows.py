"""Tests for the review of the "check" rows of the correction table."""

from hu_legal_cleaning import check_rows
from hu_legal_cleaning.text_files import write_text

TABLE = (
    "wrong,proposed,type,safe_to_apply,occurrences,decisions,first_year,last_year,"
    "hunspell_suggestions,occurrences_if_not_NFC\n"
    "elk,elő,one character,check,2,1,2004,2004,el | elő,2\n"
    "tanu,tanú,accent,yes,5,1,2005,2005,tanú,5\n"
)


def _write_table(tmp_path):
    table = tmp_path / "table.csv"
    table.write_text(TABLE, encoding="utf-8")
    return table


def test_load_check_rows_keeps_only_check_rows(tmp_path):
    rows = check_rows.load_check_rows(_write_table(tmp_path))
    assert list(rows) == ["elk"]
    assert rows["elk"].proposed == "elő"


def test_find_occurrences_gives_context_and_spreads_years(tmp_path):
    root = tmp_path / "in"
    write_text(root / "2004" / "a.txt", "one\ntwo\nthe Elk here\nfour\nfive\n")
    write_text(root / "2010" / "b.txt", "elk again\nelkedett is not a hit\n")
    rows = check_rows.load_check_rows(_write_table(tmp_path))
    check_rows.find_occurrences(root, rows, examples=5, context_lines=2)
    row = rows["elk"]
    assert (row.count, row.documents) == (2, 2)
    first = row.occurrences[0]
    assert (first.year, first.hit, first.line_number) == ("2004", "Elk", 3)
    assert first.above == ["one", "two"]
    assert first.below == ["four", "five"]
    assert (first.before, first.after) == ("the ", " here")


def test_build_check_page_contains_words_and_key(tmp_path):
    rows = check_rows.load_check_rows(_write_table(tmp_path))
    page = check_rows.build_check_page(rows, "my_key")
    assert '"wrong": "elk"' in page
    assert "my_key" in page


def test_find_occurrences_line_start_only(tmp_path):
    root = tmp_path / "in"
    write_text(root / "2004" / "a.txt", "prev\n  elk szerint\nnem elk itt\n")
    rows = check_rows.load_check_rows(_write_table(tmp_path))
    check_rows.find_occurrences(root, rows, examples=5, context_lines=1, line_start_only=True)
    assert [occurrence.line_number for occurrence in rows["elk"].occurrences] == [2]
    assert rows["elk"].count == 1
