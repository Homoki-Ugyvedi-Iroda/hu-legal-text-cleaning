from hu_legal_cleaning.text_files import (
    iter_lines,
    list_text_files,
    output_path,
    read_text,
    sample_text_files,
    write_text,
)


def test_list_text_files_skips_logs(tmp_path):
    write_text(tmp_path / "2015" / "a.txt", "x")
    write_text(tmp_path / "_log.txt", "x")
    assert list_text_files(tmp_path) == [tmp_path / "2015" / "a.txt"]


def test_sample_text_files_is_reproducible(tmp_path):
    for number in range(10):
        write_text(tmp_path / f"{number}.txt", "x")
    assert sample_text_files(tmp_path, 3) == sample_text_files(tmp_path, 3)
    assert len(sample_text_files(tmp_path, 0)) == 10


def test_read_and_write_keep_line_endings(tmp_path):
    path = tmp_path / "a.txt"
    write_text(path, "első\r\nmásodik")
    assert read_text(path) == "első\r\nmásodik"
    assert list(iter_lines(path)) == ["első", "második"]


def test_output_path(tmp_path):
    source = tmp_path / "in" / "2015" / "a.txt"
    assert (
        output_path(source, tmp_path / "in", tmp_path / "out")
        == tmp_path / "out" / "2015" / "a.txt"
    )
