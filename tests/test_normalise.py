from hu_legal_cleaning.normalise import (
    clean_characters,
    fix_latin1_lookalikes,
    fix_script_lookalikes,
    remove_nul,
    remove_soft_hyphens,
    to_nfc,
)


def test_remove_nul_counts_padding():
    assert remove_nul("ítélet\x00\x00") == ("ítélet", 2)


def test_to_nfc_composes_accent():
    assert to_nfc("áll") == ("áll", 0)


def test_to_nfc_keeps_marks_without_composed_form():
    _, marks_left = to_nfc("x̶")
    assert marks_left == 1


def test_fix_latin1_lookalikes():
    assert fix_latin1_lookalikes("elõfizetõ Ûr") == ("előfizető Űr", 3)


def test_clean_characters_runs_nfc_before_lookalike_repair():
    text, counts = clean_characters("õ\x00")
    assert text == "ő"
    assert counts == {
        "nul_removed": 1,
        "soft_hyphens_removed": 0,
        "lookalikes_fixed": 1,
        "script_lookalikes_fixed": 0,
        "combining_marks_left": 0,
    }


def test_fix_script_lookalikes_repairs_latin_words_only():
    assert fix_script_lookalikes("2014/17/ЕU Citroёn Grüβen") == (
        "2014/17/EU Citroën Grüßen",
        3,
    )
    assert fix_script_lookalikes("Адрес μg Δ9-THC") == (
        "Адрес μg Δ9-THC",
        0,
    )


def test_clean_characters_removes_soft_hyphens():
    text, counts = clean_characters("in\u00adgatlan")
    assert (text, counts["soft_hyphens_removed"]) == ("ingatlan", 1)


def test_remove_soft_hyphens_keeps_the_one_at_a_line_end():
    assert remove_soft_hyphens("in\u00adgatlan\nalkal\u00ad\nmazott") == (
        "ingatlan\nalkal\u00ad\nmazott",
        1,
    )
