import csv

from hu_legal_cleaning import pipeline
from hu_legal_cleaning.cli import main
from hu_legal_cleaning.text_files import read_text, write_text

TEXT = "A törvény sze-\nrint\nértett elmondta, igy a biróság döntött.\x00\n"


class FakeHunspell:
    """Stands in for Hunspell so the tests do not need the program installed."""

    known = {"szerint", "elmondta", "a", "így", "bíróság", "döntött"}

    def unknown_words(self, words):
        return {word for word in words if word not in self.known}

    def suggestions(self, words):
        return {"biróság": ["bíróság"], "igy": ["így"]}


def read_rows(path):
    with path.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def make_corpus(root):
    write_text(root / "2015" / "a.txt", TEXT)
    return root


def test_clean_characters_folder_writes_copy_and_log(tmp_path):
    source = make_corpus(tmp_path / "in")
    changed = pipeline.clean_characters_folder(source, tmp_path / "out", tmp_path / "log.csv")
    assert changed == 1
    assert "\x00" not in read_text(tmp_path / "out" / "2015" / "a.txt")
    assert "\x00" in read_text(source / "2015" / "a.txt")


def test_find_linebreak_candidates(tmp_path):
    source = make_corpus(tmp_path / "in")
    pipeline.find_linebreak_candidates(source, FakeHunspell(), tmp_path / "pairs.csv")
    [row] = read_rows(tmp_path / "pairs.csv")
    assert (row["joined"], row["decision"], row["example"]) == ("szerint", "join", "2015/a.txt:1")


def test_find_line_start_candidates(tmp_path):
    root = tmp_path / "in"
    write_text(root / "a.txt", "Sértett szerint.\n" * 300 + "értett szerint.\n" * 5)
    assert pipeline.find_line_start_candidates(root, tmp_path / "starts.csv") == 1
    assert (tmp_path / "starts.csv").read_text(encoding="utf-8").strip().endswith("a.txt:300")


def test_check_words_sorts_unknown_words(tmp_path):
    root = tmp_path / "in"
    write_text(
        root / "a.txt",
        "a bíróság döntött " * 30 + "biróság nevetel nevetel nevetel biróság biróság",
    )
    pipeline.check_words(root, FakeHunspell(), tmp_path / "words.csv")
    kinds = {row["word"]: row["kind"] for row in read_rows(tmp_path / "words.csv")}
    assert kinds == {"biróság": "probable_mistake", "nevetel": "anonymisation_leftover"}


def test_audit_abbreviations_folder(tmp_path):
    root = tmp_path / "in"
    write_text(root / "a.txt", "a hrsz. alatti ingatlan\n" * 40)
    assert pipeline.audit_abbreviations_folder(root, tmp_path / "abbr.csv") == 1


def test_apply_approved_fixes(tmp_path):
    source = make_corpus(tmp_path / "in")
    starts, joins = tmp_path / "starts.csv", tmp_path / "joins.csv"
    starts.write_text("damaged,correction,decision\nértett,Sértett,apply\n", encoding="utf-8")
    joins.write_text("first_part,second_part,decision\nsze,rint,join\n", encoding="utf-8")
    fixes = pipeline.load_approved_fixes(starts, joins, {"igy": "így"})
    totals = pipeline.apply_approved_fixes(source, tmp_path / "out", fixes, tmp_path / "log.csv")
    assert dict(totals) == {
        "line_starts": 1,
        "joins": 1,
        "corrections": 1,
        "corrections_left_in_quotes": 0,
    }
    assert read_text(tmp_path / "out" / "2015" / "a.txt").startswith(
        "A törvény szerint\nSértett elmondta, így"
    )


def test_apply_approved_fixes_leaves_lay_quotes_as_written(tmp_path):
    source = tmp_path / "in"
    court_prose = "a bíróság szerint igy döntött a tanács elnöke "
    write_text(source / "court.txt", court_prose * 20)
    write_text(
        source / "case.txt",
        "A bíróság „a bíróság szerint igy döntött a tanács elnöke” mondatot idézte. "
        "Az sms szövege: „igy irtad nekem tegnap hogy nemjossz haza”",
    )
    fixes = pipeline.load_approved_fixes(None, None, {"igy": "így"})
    totals = pipeline.apply_approved_fixes(source, tmp_path / "out", fixes, tmp_path / "log.csv")
    corrected = read_text(tmp_path / "out" / "case.txt")
    assert "„a bíróság szerint így döntött" in corrected
    assert "„igy irtad nekem" in corrected
    assert totals["corrections_left_in_quotes"] == 1
    [row] = read_rows(tmp_path / "log_protected_quotes.csv")
    assert (row["word"], row["lead_in"]) == ("igy", "sms")


def test_apply_approved_fixes_can_correct_quotes_too(tmp_path):
    source = tmp_path / "in"
    write_text(source / "case.txt", "Az sms szövege: „igy irtad nekem tegnap hogy nemjossz haza”")
    fixes = pipeline.load_approved_fixes(None, None, {"igy": "így"})
    pipeline.apply_approved_fixes(
        source, tmp_path / "out", fixes, tmp_path / "log.csv", is_protecting_quotes=False
    )
    assert "„így irtad" in read_text(tmp_path / "out" / "case.txt")
    assert not (tmp_path / "log_protected_quotes.csv").exists()


def test_load_approved_fixes_ignores_notes_in_the_correction_column(tmp_path):
    starts = tmp_path / "starts.csv"
    starts.write_text(
        "damaged,correction,decision\nlott,manual linebreak (vádlott),apply\n", encoding="utf-8"
    )
    assert pipeline.load_approved_fixes(starts, None, {}).line_starts == {}


def test_review_items_from_csv(tmp_path):
    source = make_corpus(tmp_path / "in")
    candidates = tmp_path / "pairs.csv"
    candidates.write_text(
        "first_part,joined,count,example\nsze,szerint,1,2015/a.txt:1\n", encoding="utf-8"
    )
    [item] = pipeline.review_items_from_csv(candidates, "first_part", "joined", "count", source)
    assert item.proposal == "sze -> szerint"
    assert item.contexts[0].before == "A törvény sze-"


def test_find_false_space_candidates(tmp_path):
    root = tmp_path / "in"
    write_text(
        root / "2015" / "a.txt",
        "Az els ő fokú bíróság döntött.\nA k e r ü l e t és az a bíróság.\nels ő itt is.\n",
    )

    class SplitWordHunspell:
        known = {"az", "a", "és", "bíróság", "döntött", "első", "fokú", "itt", "is"}

        def unknown_words(self, words):
            return {word for word in words if word.lower() not in self.known}

    out = tmp_path / "pairs.csv"
    assert pipeline.find_false_space_candidates(root, SplitWordHunspell(), out) == 1
    [row] = read_rows(out)
    assert (row["wrong"], row["proposed"], row["occurrences"]) == ("els ő", "első", "2")


def test_cli_clean_characters(tmp_path):
    source = tmp_path / "in"
    write_text(source / "2015" / "a.txt", "A bűnös\x00\n")
    main(
        ["clean-characters", str(source), str(tmp_path / "out"), "--log", str(tmp_path / "log.csv")]
    )
    assert read_text(tmp_path / "out" / "2015" / "a.txt") == "A bűnös\n"
