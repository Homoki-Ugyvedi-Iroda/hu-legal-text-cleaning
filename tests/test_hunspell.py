from hu_legal_cleaning.hunspell import parse_suggestions


def test_parse_suggestions_pairs_answers_with_words():
    answers = ["& tanu 4 0: tanú, taun, tabu, tani", "*", "# xqzw 0"]
    assert parse_suggestions(["tanu", "bíróság", "xqzw"], answers) == {
        "tanu": ["tanú", "taun", "tabu", "tani"]
    }
