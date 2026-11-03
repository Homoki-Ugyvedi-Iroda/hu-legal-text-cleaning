"""Tests for joining the lines of hard-wrapped decisions."""

from hu_legal_cleaning.unwrap import (
    LOWERCASE_JOIN,
    UPPERCASE_JOIN,
    is_open,
    join_kind,
    profile_wrapping,
    unwrap_lines,
)

WIDTH = 60
FILLER = "A bíróság a felperes keresetét részben alaposnak találta, mert"


def wrapped_text(paragraphs: int = 12) -> str:
    """Return a synthetic text wrapped at about WIDTH characters."""
    lines = ["Városi Bíróság", "1.P.20.000/2020/5.", ""]
    for _ in range(paragraphs):
        lines += [
            FILLER,
            "az alperes a szerződésben vállalt kötelezettségét nem teljesítette,",
            "ezért a kereset nagyobbik része megalapozott.",
        ]
    return "\n".join(lines)


def test_is_open():
    assert is_open("a felperes keresetét")
    assert is_open("2015. április 13. napján, a lakás 2019.")
    assert not is_open("A bíróság a keresetet elutasítja.")


def test_profile_of_a_wrapped_text():
    profile = profile_wrapping(wrapped_text().split("\n"))
    assert profile.is_hard_wrapped
    assert profile.wrapped_lines == 24
    assert abs(profile.width - WIDTH) < 10


def test_one_paragraph_per_line_is_not_hard_wrapped():
    long_paragraph = FILLER + " " + FILLER + " " + FILLER + "."
    lines = []
    for _ in range(12):
        lines += [long_paragraph, "a tanács elnöke", "dr. Kovács Anna", FILLER, "az alperes ellen"]
    assert not profile_wrapping(lines).is_hard_wrapped
    text = "\n".join(lines)
    assert unwrap_lines(text)[0] == text


def test_wrapped_text_is_joined_into_sentences():
    fixed, joins, _ = unwrap_lines(wrapped_text())
    lines = fixed.split("\n")
    assert lines[:3] == ["Városi Bíróság", "1.P.20.000/2020/5.", ""]
    assert lines[3] == (
        FILLER + " az alperes a szerződésben vállalt kötelezettségét nem teljesítette,"
        " ezért a kereset nagyobbik része megalapozott."
    )
    assert joins[LOWERCASE_JOIN] == 24


def test_capitalised_word_carried_over_needs_a_full_line():
    full = "A felperes keresetét a bíróság az alábbiak miatt a Fővárosi"
    assert join_kind(full, "Törvényszékhez küldte meg.", WIDTH) == UPPERCASE_JOIN
    assert join_kind("meghozta az alábbi", "Ítéletet hozott.", WIDTH) is None
    # A line opening with "A" or "Az" starts a new sentence whose full stop is missing.
    assert join_kind(full, "A felperes ezt vitatta.", WIDTH) is None


def test_words_that_only_look_like_layout_are_joined():
    for following in (
        "tanú16 rendőr nyomozó a helyszínre ment.",
        "b) pontja alapján a kérelmet elutasította.",
        "km/h sebességgel közlekedett az ütközés előtt.",
        "bírósági felülvizsgálatát kérte a felperes a keresetlevelében.",
        "végzés).",
    ):
        assert join_kind(FILLER, following, WIDTH) == LOWERCASE_JOIN, following
    assert join_kind(FILLER + " (3) bekezdés", "b) pontja szerint", WIDTH) == LOWERCASE_JOIN


def test_layout_breaks_are_kept():
    assert join_kind(FILLER, "ÍTÉLETET:", WIDTH) is None
    assert join_kind(FILLER, "ítéletet:", WIDTH) is None
    assert join_kind(FILLER, "bűnös", WIDTH) is None
    assert join_kind(FILLER, "a) a kereset elutasítását,", WIDTH) is None
    assert join_kind(FILLER + " | 2009", "szövetkezet1 | 2010", WIDTH) is None
    assert join_kind("a felperes", "keresetét elutasítja.", WIDTH) is None
    assert join_kind(FILLER, "", WIDTH) is None


def test_sentence_end_is_never_joined():
    assert join_kind(FILLER + " vége.", "a következő mondat", WIDTH) is None


def test_crlf_is_kept():
    fixed, _, _ = unwrap_lines(wrapped_text().replace("\n", "\r\n"))
    assert "\r\n" in fixed
    assert "\n" not in fixed.replace("\r\n", "")
