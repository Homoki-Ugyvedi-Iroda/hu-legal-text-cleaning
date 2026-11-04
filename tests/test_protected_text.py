from collections import Counter

from hu_legal_cleaning import protected_text

SMS_QUOTE = "Az sms szövege: „igy irtad nekem tegnap hogy nemjossz haza” volt."
QUOTE_ONLY = SMS_QUOTE[SMS_QUOTE.index("„") : SMS_QUOTE.index("”") + 1]


def test_find_quotes_closes_at_the_end_of_a_paragraph():
    text = "„nincs záró jel\n\nÚj bekezdés."
    assert protected_text.find_quotes(text) == [(0, text.index("\n\n") + 2)]


def test_find_quotes_straight_marks():
    assert protected_text.find_quotes('azt mondta: "menj haza" este') == [(12, 23)]


def test_quote_words_only_inside_quotes():
    assert protected_text.quote_words(SMS_QUOTE) == {
        "irtad",
        "nekem",
        "tegnap",
        "hogy",
        "nemjossz",
        "haza",
    }


def test_count_words_counts_only_wanted_words():
    counts = protected_text.count_words(["haza haza tegnap bíróság"], {"haza", "tegnap"})
    assert counts == Counter({"haza": 2, "tegnap": 1})


def test_rare_share_of_short_quote_is_zero():
    assert protected_text.rare_share("„igy irtad”", Counter()) == 0.0


def test_rare_share_counts_words_seen_at_most_twice():
    counts = Counter({"irtad": 1, "nekem": 50, "tegnap": 50, "hogy": 90, "nemjossz": 2, "haza": 50})
    assert protected_text.rare_share(QUOTE_ONLY, counts) == 2 / 6


def test_lead_in_names_the_message():
    assert protected_text.lead_in(SMS_QUOTE, SMS_QUOTE.index("„")) == "sms"


def test_protected_quotes_keeps_lay_writing_only():
    court = "„a bíróság szerint igy döntött a tanács elnöke”"
    text = court + " " + SMS_QUOTE
    counts = Counter({"bíróság": 900, "szerint": 900, "döntött": 900, "tanács": 900, "elnöke": 900})
    [quote] = protected_text.protected_quotes(text, counts)
    assert text[quote.start : quote.end].startswith("„igy irtad")
    assert (quote.rare_share, quote.lead_in) == (1.0, "sms")
