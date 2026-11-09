"""Find verbatim quoted lay writing that word corrections must leave as written.

Court decisions quote text messages, e-mails, letters and posts word for word, mistakes
included. Correcting them changes evidence (see docs/protected-text.md). Court prose
quoted from another decision is a different matter, so not every quote is protected: a
quote is protected when at least `MIN_RARE_SHARE` of its lowercase words are rare in the
whole corpus (lay writing without accents is full of rare forms, court prose is not).

Counting every word of a large corpus takes a lot of memory, so the counts are taken in
two passes: first the words that occur inside quotes (`quote_words`), then how often
those words occur anywhere (`count_words`).
"""

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

# A quote runs from „ to ” (or to a straight quote mark), or to the end of its paragraph
# when the closing mark is missing; or between two straight quote marks on one line.
QUOTE = re.compile(r"„[^„”\"]*?(?:[”\"]|\n\n|$)|\"[^\"\n]{3,}?\"")
# Lowercase words of four or more letters, not part of a hyphenated or numbered token.
WORD = re.compile(r"(?<![\w-])[a-záéíóöőúüű]{4,}(?![\w-])")
RARE_COUNT = 2
MIN_RARE_SHARE = 0.10
MIN_QUOTE_WORDS = 5
# Words before a quote that name a message or letter; reported to help a reviewer, not
# used for the decision (on the test corpus they missed a third of the lay quotes).
LEAD_IN = re.compile(
    r"(?i)\bsms|üzenet|e-?mail|levél|level\b|facebook|messenger|viber|chat|bejegyzés"
    r"|kommentet|posztot|írta|szövegű"
)
LEAD_IN_WINDOW = 400


@dataclass(frozen=True)
class Quote:
    """A quotation in a text.

    Attributes:
        start: Position of the opening quote mark.
        end: Position after the closing mark.
        rare_share: Share of the quote's words that are rare in the corpus.
        lead_in: A word naming a message or letter shortly before the quote, or "".
    """

    start: int
    end: int
    rare_share: float
    lead_in: str


def find_quotes(text: str) -> list[tuple[int, int]]:
    """Return the (start, end) positions of the quotations in a text."""
    return [(match.start(), match.end()) for match in QUOTE.finditer(text)]


def quote_words(text: str) -> set[str]:
    """Return the lowercase words that occur inside the quotations of a text."""
    words: set[str] = set()
    for start, end in find_quotes(text):
        words.update(WORD.findall(text[start:end]))
    return words


def count_words(texts: Iterable[str], wanted: set[str]) -> Counter[str]:
    """Count how often each wanted word occurs in the texts.

    Args:
        texts: The whole corpus, one text at a time.
        wanted: The words to count, e.g. the union of `quote_words` over the corpus.
    """
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(word for word in WORD.findall(text) if word in wanted)
    return counts


def rare_share(quote: str, word_counts: Counter[str]) -> float:
    """Return the share of the quote's words that occur at most `RARE_COUNT` times.

    A quote of fewer than `MIN_QUOTE_WORDS` words gets 0.0: it is too short to judge.
    """
    words = WORD.findall(quote)
    if len(words) < MIN_QUOTE_WORDS:
        return 0.0
    return sum(word_counts[word] <= RARE_COUNT for word in words) / len(words)


def lead_in(text: str, quote_start: int) -> str:
    """Return a word naming a message or letter shortly before a quote, or ""."""
    match = LEAD_IN.search(text[max(0, quote_start - LEAD_IN_WINDOW) : quote_start])
    return match.group() if match else ""


def protected_quotes(
    text: str, word_counts: Counter[str], min_rare_share: float = MIN_RARE_SHARE
) -> list[Quote]:
    """Return the quotations of a text that word corrections must leave as written.

    Args:
        text: The text.
        word_counts: Corpus counts of the quoted words, from `count_words`.
        min_rare_share: The share of rare words from which a quote is protected.
    """
    quotes = []
    for start, end in find_quotes(text):
        share = rare_share(text[start:end], word_counts)
        if share >= min_rare_share:
            quotes.append(Quote(start, end, share, lead_in(text, start)))
    return quotes
