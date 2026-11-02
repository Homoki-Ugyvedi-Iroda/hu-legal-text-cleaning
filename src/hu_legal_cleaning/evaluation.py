"""Score a sentence splitter against the bundled gold passages.

A split is turned into the set of positions where a segment ends, counted in
non-whitespace characters, so that differences in spacing do not count as errors.
Precision, recall and F1 are then computed on those boundary positions.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

GOLD_FILE = "sentence_gold.jsonl"
WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class GoldPassage:
    """A hand-checked passage of a court decision with its correct sentences.

    Attributes:
        passage_id: Identifier, e.g. "P01".
        source: Path of the decision the passage comes from, relative to the corpus.
        text: The passage with its original line breaks.
        sentences: The correct split.
    """

    passage_id: str
    source: str
    text: str
    sentences: list[str]


@dataclass(frozen=True)
class BoundaryScore:
    """Precision, recall and F1 of sentence boundaries, as percentages."""

    precision: float
    recall: float
    f1: float


def load_gold_passages() -> list[GoldPassage]:
    """Return the gold passages shipped with the package."""
    # importlib.resources finds data files inside an installed package.
    path = Path(str(resources.files("hu_legal_cleaning") / "data" / GOLD_FILE))
    passages = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        passages.append(
            GoldPassage(record["id"], record["source"], record["text"], record["sentences"])
        )
    return passages


def boundaries(segments: list[str]) -> set[int]:
    """Return the end positions of the segments, counted in non-whitespace characters."""
    positions, length = set(), 0
    for segment in segments:
        length += len(WHITESPACE.sub("", segment))
        positions.add(length)
    return positions


def score_boundaries(predicted: list[set[int]], gold: list[set[int]]) -> BoundaryScore:
    """Compare predicted and gold boundary sets, passage by passage.

    Args:
        predicted: Boundary positions of each passage, from the splitter.
        gold: Boundary positions of each passage, from the gold split.

    Returns:
        The pooled scores over all passages.
    """
    true_positives = sum(len(p & g) for p, g in zip(predicted, gold, strict=True))
    predicted_total = sum(len(p) for p in predicted)
    gold_total = sum(len(g) for g in gold)
    precision = true_positives / predicted_total if predicted_total else 0.0
    recall = true_positives / gold_total if gold_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return BoundaryScore(round(100 * precision, 1), round(100 * recall, 1), round(100 * f1, 1))


def evaluate_splitter(split: Callable[[str], list[str]]) -> BoundaryScore:
    """Run a splitter on every gold passage and score its boundaries.

    Args:
        split: A function from text to a list of sentences.

    Returns:
        The boundary scores.
    """
    passages = load_gold_passages()
    predicted = [boundaries(split(passage.text)) for passage in passages]
    gold = [boundaries(passage.sentences) for passage in passages]
    return score_boundaries(predicted, gold)
