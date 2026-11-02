from hu_legal_cleaning.review_page import Context, ReviewItem, build_review_page, file_link


def test_build_review_page_embeds_items_safely():
    context = Context("a ", "értett", "</script>", "f.txt")
    item = ReviewItem("értett", "értett", "értett -> Sértett", 3, [context])
    page = build_review_page([item], ["apply", "no"], "Line starts", "line_starts")
    assert '"értett -> Sértett"' in page
    assert "<\\/script>" in page
    assert '["apply", "no"]' in page


def test_file_link(tmp_path):
    assert file_link(tmp_path / "a b.txt").startswith("file:///")
