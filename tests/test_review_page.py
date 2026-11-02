from hu_legal_cleaning.review_page import (
    Context,
    ReviewItem,
    build_review_page,
    file_link,
    original_of,
)


def test_build_review_page_embeds_items_safely():
    context = Context("a ", "értett", "</script>", "f.txt")
    item = ReviewItem("értett", "értett", "értett -> Sértett", 3, [context])
    page = build_review_page([item], ["apply", "no"], "Line starts", "line_starts")
    assert '"értett -> Sértett"' in page
    assert "<\\/script>" in page
    assert '["apply", "no"]' in page


def test_file_link(tmp_path):
    assert file_link(tmp_path / "a b.txt").startswith("file:///")


def test_original_of_finds_the_source_document(tmp_path):
    originals = tmp_path / "originals"
    (originals / "2006").mkdir(parents=True)
    (originals / "2006" / "P.1_2006.rtf").write_bytes(b"{\rtf1}")
    assert original_of("2006/P.1_2006.txt", originals) == originals / "2006" / "P.1_2006.rtf"
    assert original_of("2006/P.2_2006.txt", originals) is None
