"""Tests for finding and repairing text decoded with the wrong code page."""

from hu_legal_cleaning import encoding_repair, pipeline
from hu_legal_cleaning.text_files import read_text, write_text


def _damage(text: str, wrong_codec: str = "cp1256") -> str:
    """Simulate the fault: cp1250 bytes read with another code page."""
    return text.encode("cp1250").decode(wrong_codec)


HUNGARIAN = "A bíróság határozata szerint a felperes keresetét elutasítja, és az ítélet jogerős."


def test_damage_helper_reproduces_the_bhgy_fault():
    assert _damage("határozat") == "hatلrozat"


def test_is_mixed_script():
    assert encoding_repair.is_mixed_script("hatلrozat")
    assert not encoding_repair.is_mixed_script("határozat")
    assert not encoding_repair.is_mixed_script("Σωκράτης")


def test_repair_word_keeps_correct_letters_of_the_same_word():
    damaged = "k" + _damage("ö") + "zgyűlés"
    assert encoding_repair.repair_word(damaged, "cp1256") == "közgyűlés"


def test_repair_word_handles_capitals_written_as_punctuation():
    assert encoding_repair.repair_word(_damage("ŰRLAP"), "cp1256") == "ŰRLAP"


def test_diagnose_finds_the_code_page():
    diagnosis = encoding_repair.diagnose(_damage(HUNGARIAN))
    assert diagnosis.wrong_codec == "cp1256"
    assert diagnosis.repairable_words == diagnosis.damaged_words >= 3


def test_diagnose_ignores_a_correct_greek_quotation():
    diagnosis = encoding_repair.diagnose("A görög λόγος szó jelentése: beszéd.")
    assert diagnosis.damaged_words == 0
    assert not encoding_repair.needs_repair(diagnosis)


def test_repair_document_restores_the_text():
    repaired, diagnosis, changed = encoding_repair.repair_document(_damage(HUNGARIAN))
    assert repaired == HUNGARIAN
    assert changed == diagnosis.damaged_words


def test_repair_document_leaves_a_single_odd_word():
    text = "Egy hatلrozat, minden más rendben van."
    assert encoding_repair.repair_document(text)[0] == text


def test_repair_utf8_misread():
    damaged = "A bíróság ítélete jogerős.".encode().decode("cp1252")
    assert encoding_repair.repair_utf8_misread(damaged) == ("A bíróság ítélete jogerős.", 3)


def test_find_and_repair_encoding_folder(tmp_path):
    source = tmp_path / "in"
    write_text(source / "2010" / "bad.txt", _damage(HUNGARIAN))
    write_text(source / "2010" / "good.txt", HUNGARIAN)
    assert pipeline.find_encoding_damage(source, tmp_path / "damage.csv") == 1
    changed = pipeline.repair_encoding_folder(
        source, tmp_path / "out", tmp_path / "log.csv", only_changed=True
    )
    assert changed == 1
    assert read_text(tmp_path / "out" / "2010" / "bad.txt") == HUNGARIAN
    assert not (tmp_path / "out" / "2010" / "good.txt").exists()


def test_scientific_greek_symbols_are_not_repaired():
    text = "A vérben Δ9-THC és α-PVP volt, 26 μg/ml, 22ºC mellett, mᵌ-enként."
    repaired, diagnosis, changed = encoding_repair.repair_document(text)
    assert (repaired, changed) == (text, 0)
    assert not encoding_repair.needs_repair(diagnosis)


def test_repair_word_gbk_two_byte_damage():
    assert encoding_repair.repair_word("K鷕ia", "gbk") == "Kúria"


def test_repair_word_shift_jis_section_sign_read_as_arabic():
    assert encoding_repair.repair_word("پک-ban", "cp1256") == "§-ban"


def test_repair_word_shift_jis_quotation_mark_and_micro_sign():
    assert encoding_repair.repair_word("voltپh", "cp1256") == "volt”"
    assert encoding_repair.repair_word("ƒتg/ml", "cp1256") == "μg/ml"
