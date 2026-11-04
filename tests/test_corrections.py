from hu_legal_cleaning.corrections import (
    apply_corrections,
    bundled_table_path,
    correction_pattern,
    load_corrections,
)


def test_apply_corrections_keeps_case_and_word_boundaries():
    corrections = {"igy": "így", "biróság": "bíróság"}
    text, count = apply_corrections("Igy a biróság, igy tovább; igyekszik", corrections)
    assert text == "Így a bíróság, így tovább; igyekszik"
    assert count == 3


def test_apply_corrections_leaves_placeholders_with_digits_or_underscores():
    text, count = apply_corrections("tanu1 és Tanu_2 szerint a tanu.", {"tanu": "tanú"})
    assert text == "tanu1 és Tanu_2 szerint a tanú."
    assert count == 1


def test_apply_corrections_skips_protected_spans():
    text = "igy a bíróság; „igy irta”"
    quote_start = text.index("„")
    corrected, count = apply_corrections(text, {"igy": "így"}, [(quote_start, len(text))])
    assert corrected == "így a bíróság; „igy irta”"
    assert count == 1


def test_correction_pattern_prefers_the_longer_word():
    pattern = correction_pattern({"biro": "bíró", "birosag": "bíróság"})
    assert pattern.findall("a birosag") == ["birosag"]


def test_load_corrections_safe_rows_only(tmp_path):
    table = tmp_path / "table.csv"
    table.write_text(
        "wrong,proposed,safe_to_apply\n"
        "igy,így,yes\n"
        "felöli,felőli,check\n"
        "mla,(normalise the text to NFC),no\n",
        encoding="utf-8",
    )
    assert load_corrections(table) == {"igy": "így"}
    assert load_corrections(table, only_safe=False) == {"igy": "így", "felöli": "felőli"}


def test_bundled_table_loads():
    assert load_corrections(bundled_table_path())["tanu"] == "tanú"
