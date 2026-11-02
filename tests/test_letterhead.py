"""Tests for removing letterhead residue."""

from hu_legal_cleaning.letterhead import remove_letterhead_residue


def test_run_before_heading_is_removed():
    text, removed = remove_letterhead_residue("őáÍéőá... Ítélőtábla\r\nPf.1/2017/4.")
    assert text == "... Ítélőtábla\r\nPf.1/2017/4."
    assert removed == "őáÍéőá"


def test_short_run_glued_to_court_name_and_whole_line_run():
    assert remove_letterhead_residue("őFővárosi Bíróság")[0] == "Fővárosi Bíróság"
    assert remove_letterhead_residue("\néáóööí\nTörvényszék")[0] == "\n\nTörvényszék"


def test_real_words_placeholders_and_later_lines_stay():
    for text in ["Ítélőtábla", "ÍTÉLET", "ÉS", "ÉÉÉÉ tanú vallotta", "A bíróság\néáóööí"]:
        assert remove_letterhead_residue(text) == (text, "")


def test_run_before_damaged_heading_stays():
    text = "éíööíÉőáővárosi Közigazgatási és Munkaügyi Bíróság"
    assert remove_letterhead_residue(text) == (text, "")
