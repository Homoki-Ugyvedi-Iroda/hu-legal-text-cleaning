"""Corpus-level steps: each reads a folder tree, and writes a new tree or a candidate list.

The rules of the pipeline:

- the source folder is never changed; every step that changes text writes a copy;
- every change is written to a log (CSV), so it can be checked and repeated;
- automatic rules only produce candidates; a person approves them on a review page
  (see `review_page`), and `apply_approved_fixes` applies only what was approved.
"""

import csv
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from hu_legal_cleaning import (
    abbreviations,
    convert,
    encoding_repair,
    false_spaces,
    line_starts,
    linebreaks,
    normalise,
    protected_text,
)
from hu_legal_cleaning.corrections import apply_corrections, correction_pattern
from hu_legal_cleaning.dictionary import (
    WordStats,
    collect_word_stats,
    is_abbreviation_or_suffix,
    is_anonymisation_leftover,
    is_name_like,
    is_probable_mistake,
)
from hu_legal_cleaning.hunspell import Hunspell
from hu_legal_cleaning.review_page import Context, ReviewItem, file_link
from hu_legal_cleaning.text_files import (
    iter_lines,
    list_text_files,
    output_path,
    read_text,
    sample_text_files,
    write_text,
)

logger = logging.getLogger(__name__)

SOURCE_SUFFIXES = (".docx", ".rtf")
WORD_LOCK_PREFIX = "~$"  # temporary lock files that Word leaves next to open documents
REPLACEMENT_CHARACTER = "�"
PROGRESS_EVERY = 5000
MIN_WORD_COUNT = 3
MAX_SUGGESTED_WORDS = 2500
CONTEXT_WIDTH = 120


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # "utf-8-sig" adds a byte-order mark so that Excel opens the accents correctly.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def convert_folder(source_root: Path, target_root: Path, log_path: Path) -> Counter[str]:
    """Convert every .docx and .rtf file of a folder tree to a .txt file in another tree.

    Args:
        source_root: Folder with the original documents.
        target_root: Folder for the text files (same sub-folders).
        log_path: CSV log of files that failed, are empty, or contain replacement characters.

    Returns:
        The number of files per status ("ok", "empty", "check", "failed").
    """
    sources = sorted(
        path
        for path in source_root.rglob("*")
        if path.suffix.lower() in SOURCE_SUFFIXES and not path.name.startswith(WORD_LOCK_PREFIX)
    )
    statuses: Counter[str] = Counter()
    log_rows: list[list[object]] = []
    for number, source in enumerate(sources, 1):
        target = output_path(source, source_root, target_root).with_suffix(".txt")
        try:
            text = convert.to_text(source)
        except (OSError, ValueError, KeyError) as error:
            statuses["failed"] += 1
            log_rows.append([source, "failed", f"{type(error).__name__}: {error}"])
            continue
        write_text(target, text)
        status = "ok"
        if not text.strip():
            status = "empty"
        elif REPLACEMENT_CHARACTER in text:
            status = "check"
        statuses[status] += 1
        if status != "ok":
            log_rows.append([source, status, f"{text.count(REPLACEMENT_CHARACTER)} replaced"])
        if number % PROGRESS_EVERY == 0:
            logger.info("%d / %d converted", number, len(sources))
    _write_csv(log_path, ["source", "status", "note"], log_rows)
    return statuses


def clean_characters_folder(source_root: Path, target_root: Path, log_path: Path) -> int:
    """Copy a text tree, removing NUL and soft hyphens, applying NFC and repairing õ/û.

    Args:
        source_root: Folder of text files.
        target_root: Folder for the cleaned copy.
        log_path: CSV log with one row per changed file.

    Returns:
        The number of changed files.
    """
    log_rows: list[list[object]] = []
    for path in list_text_files(source_root):
        text = read_text(path)
        cleaned, counts = normalise.clean_characters(text)
        write_text(output_path(path, source_root, target_root), cleaned)
        if cleaned != text or counts["combining_marks_left"]:
            log_rows.append([path.relative_to(source_root), *counts.values()])
    header = ["file", "nul_removed", "soft_hyphens_removed", "lookalikes_fixed"]
    header += ["script_lookalikes_fixed", "combining_marks_left"]
    _write_csv(log_path, header, log_rows)
    return len(log_rows)


def find_encoding_damage(root: Path, out_csv: Path) -> int:
    """List the files with words decoded with a wrong code page, e.g. "hatلrozat".

    Args:
        root: Folder of text files.
        out_csv: One row per file with at least one damaged word.

    Returns:
        The number of files that `encoding_repair.needs_repair` would repair.
    """
    rows: list[list[object]] = []
    for path in list_text_files(root):
        diagnosis = encoding_repair.diagnose(read_text(path))
        if not (diagnosis.damaged_words or diagnosis.utf8_misread):
            continue
        rows.append(
            [path.relative_to(root).as_posix(), diagnosis.damaged_words, diagnosis.wrong_codec]
            + [diagnosis.repairable_words, diagnosis.utf8_misread]
            + [encoding_repair.needs_repair(diagnosis), " ".join(diagnosis.examples)]
        )
    header = ["file", "damaged_words", "wrong_codec", "repairable_words", "utf8_misread"]
    _write_csv(out_csv, [*header, "needs_repair", "examples"], rows)
    return sum(1 for row in rows if row[5])


def repair_encoding_folder(
    source_root: Path, target_root: Path, log_path: Path, only_changed: bool = False
) -> int:
    """Copy a text tree, repairing words decoded with a wrong code page.

    Args:
        source_root: Folder of text files (never changed).
        target_root: Folder for the repaired copy.
        log_path: CSV log with one row per changed file.
        only_changed: If True, write only the changed files, e.g. to check them before
            copying them over an existing cleaned copy.

    Returns:
        The number of changed files.
    """
    log_rows: list[list[object]] = []
    for path in list_text_files(source_root):
        text = read_text(path)
        repaired, diagnosis, changed = encoding_repair.repair_document(text)
        if changed:
            relative = path.relative_to(source_root).as_posix()
            log_rows.append([relative, diagnosis.wrong_codec, changed, diagnosis.utf8_misread])
        if changed or not only_changed:
            write_text(output_path(path, source_root, target_root), repaired)
    _write_csv(log_path, ["file", "wrong_codec", "words_changed", "utf8_misread"], log_rows)
    return len(log_rows)


def find_false_space_candidates(
    root: Path, hunspell: Hunspell, out_csv: Path, sample_size: int = 0
) -> int:
    """List neighbouring words that probably are one word split by a false space.

    The list has the layout of the correction table, so the approved rows can be added to
    the table and applied with `apply`, and `review-check-rows` can show them in context.

    Args:
        root: Folder of text files.
        hunspell: The spell checker.
        out_csv: The candidate pairs, the most frequent first.
        sample_size: Number of files to read; 0 reads all.

    Returns:
        The number of candidate pairs.
    """
    paths = sample_text_files(root, sample_size)
    words: Counter[str] = Counter()
    for path in paths:
        words.update(false_spaces.vocabulary(iter_lines(path)))
    unknown = hunspell.unknown_words(sorted(words))
    texts = ((path.relative_to(root).as_posix(), list(iter_lines(path))) for path in paths)
    pairs = false_spaces.collect_pairs(
        texts, lambda first, second: first in unknown or second in unknown
    )
    joined_unknown = hunspell.unknown_words(sorted(false_spaces.joined_forms(pairs)))
    candidates = false_spaces.false_space_pairs(pairs, unknown, joined_unknown)
    rows = [
        [f"{first} {second}".lower(), joined.lower(), "false space", "check", stats.count]
        + [stats.documents, "", "", f"example {stats.example}", ""]
        for first, second, joined, stats in candidates
    ]
    header = ["wrong", "proposed", "type", "safe_to_apply", "occurrences", "decisions"]
    header += ["first_year", "last_year", "hunspell_suggestions", "occurrences_if_not_NFC"]
    _write_csv(out_csv, header, rows)
    return len(rows)


def find_linebreak_candidates(root: Path, hunspell: Hunspell, out_csv: Path) -> int:
    """List every word split by a hyphen at a line end, with a suggested decision.

    Args:
        root: Folder of text files.
        hunspell: The spell checker.
        out_csv: Candidate list: parts, joined form, count, decision, hold reason, example.

    Returns:
        The number of distinct pairs.
    """
    counts: Counter[tuple[str, str]] = Counter()
    examples: dict[tuple[str, str], str] = {}
    for path in list_text_files(root):
        for pair in linebreaks.find_hyphen_pairs(list(iter_lines(path))):
            key = (pair.first_part, pair.second_part)
            counts[key] += 1
            examples.setdefault(key, f"{path.relative_to(root).as_posix()}:{pair.line_index + 1}")
    words = {(a + b).lower() for a, b in counts} | {part.lower() for key in counts for part in key}
    unknown = hunspell.unknown_words(sorted(words))
    rows = []
    for (first, second), count in counts.most_common():
        decision = linebreaks.classify_pair(first, second, lambda word: word not in unknown)
        reason = linebreaks.hold_reason(first, second)
        rows.append(
            [first, second, first + second, count, decision, reason, examples[(first, second)]]
        )
    header = ["first_part", "second_part", "joined", "count", "decision", "hold_reason", "example"]
    _write_csv(out_csv, header, rows)
    return len(rows)


def find_line_start_candidates(root: Path, out_csv: Path) -> int:
    """List lowercase line-start words that probably lost their first letter(s).

    Args:
        root: Folder of text files.
        out_csv: Candidate list with counts and one example each.

    Returns:
        The number of candidates.
    """
    counts = line_starts.LineStartCounts(Counter(), Counter())
    examples: dict[str, str] = {}
    for path in list_text_files(root):
        lines = list(iter_lines(path))
        line_starts.count_line_starts(lines, counts)
        _remember_line_start_examples(lines, path.relative_to(root).as_posix(), examples)
    candidates = line_starts.find_lost_letter_candidates(counts)
    rows = [
        [c.damaged, c.probable_word, c.lost_letters, c.damaged_lines, c.original_lines]
        + [examples[c.damaged]]
        for c in candidates
    ]
    header = ["damaged", "correction", "lost_letters", "damaged_lines", "correction_lines"]
    _write_csv(out_csv, [*header, "example"], rows)
    return len(rows)


def _remember_line_start_examples(
    lines: list[str], relative: str, examples: dict[str, str]
) -> None:
    """Keep the first "path:line" for each lowercase line-start word.

    The line number is that of the line before the word's line, so that the review page
    shows the end of the previous line followed by the start of the damaged line.
    """
    for index, line in enumerate(lines):
        match = line_starts.FIRST_WORD.match(line)
        if index == 0 or not match or match.group(1) in examples:
            continue
        if match.group(1)[0].islower() and line_starts.starts_sentence(lines[index - 1]):
            examples[match.group(1)] = f"{relative}:{index}"


def _word_rows(
    stats: WordStats, unknown: set[str], suggestions: dict[str, list[str]]
) -> list[list[object]]:
    rows: list[list[object]] = []
    for word in sorted(unknown, key=lambda item: -stats.count[item]):
        if stats.count[word] < MIN_WORD_COUNT:
            continue
        if is_anonymisation_leftover(word):
            kind = "anonymisation_leftover"
        elif is_name_like(word, stats):
            kind = "name"
        elif is_abbreviation_or_suffix(word, stats):
            kind = "abbreviation_or_suffix"
        else:
            best = next(iter(suggestions.get(word, [])), "")
            kind = "probable_mistake" if is_probable_mistake(word, best, stats.count) else "unsure"
        suggested = " | ".join(suggestions.get(word, [])[:4])
        rows.append([word, stats.count[word], stats.documents[word], kind, suggested])
    return rows


def check_words(root: Path, hunspell: Hunspell, out_csv: Path, sample_size: int = 0) -> int:
    """List the words Hunspell does not know, sorted into kinds, with suggestions.

    Kinds: "anonymisation_leftover", "name", "abbreviation_or_suffix",
    "probable_mistake" (close to a much more frequent word) and "unsure".

    Args:
        root: Folder of text files.
        hunspell: The spell checker.
        out_csv: The word list.
        sample_size: Number of files to read; 0 reads all.

    Returns:
        The number of words listed.
    """
    stats = WordStats()
    for path in sample_text_files(root, sample_size):
        collect_word_stats(list(iter_lines(path)), stats)
    unknown = hunspell.unknown_words(sorted(stats.count))
    frequent = sorted(unknown, key=lambda word: -stats.count[word])[:MAX_SUGGESTED_WORDS]
    suggestions = hunspell.suggestions(frequent)
    rows = _word_rows(stats, unknown, suggestions)
    _write_csv(out_csv, ["word", "count", "documents", "kind", "suggestions"], rows)
    return len(rows)


def audit_abbreviations_folder(root: Path, out_csv: Path, sample_size: int = 0) -> int:
    """Measure what follows each dotted word and list the probable abbreviations.

    Args:
        root: Folder of text files.
        out_csv: One row per frequent dotted word, with its verdict.
        sample_size: Number of files to read; 0 reads all.

    Returns:
        The number of rows written.
    """
    followers = abbreviations.DotFollowers()
    for path in sample_text_files(root, sample_size, seed=11):
        abbreviations.count_dot_followers(list(iter_lines(path)), followers)
    rows = abbreviations.audit_abbreviations(followers)
    header = ["token", "commonest_form", "total", "lowercase_share", "number_share", "verdict"]
    _write_csv(out_csv, header, [list(vars(row).values()) for row in rows])
    return len(rows)


@dataclass
class ApprovedFixes:
    """The fixes a person approved, ready to apply.

    Attributes:
        line_starts: Damaged line-start word -> correction.
        joins: (first part, second part) pairs to join across a line break.
        corrections: Lowercase wrong word -> correction.
    """

    line_starts: dict[str, str]
    joins: set[tuple[str, str]]
    corrections: dict[str, str]


def load_approved_fixes(
    line_start_csv: Path | None, joins_csv: Path | None, corrections: dict[str, str]
) -> ApprovedFixes:
    """Read the approved decisions.

    Args:
        line_start_csv: CSV with columns damaged, correction, decision ("apply" to use).
        joins_csv: CSV with columns first_part, second_part, decision ("join" to use).
        corrections: Word corrections, e.g. from `corrections.load_corrections`.
    """
    starts = {}
    if line_start_csv:
        for row in _read_csv(line_start_csv):
            # A note in the correction column ("manual linebreak") is not a replacement word.
            if row["decision"] == "apply" and row["correction"].isalpha():
                starts[row["damaged"]] = row["correction"]
    joins = set()
    if joins_csv:
        for row in _read_csv(joins_csv):
            if row["decision"] == "join":
                joins.add((row["first_part"], row["second_part"]))
    return ApprovedFixes(starts, joins, corrections)


def _fix_lines(text: str, fixes: ApprovedFixes) -> tuple[str, int, int]:
    """Apply the line-start fixes and joins; return the text and both counts."""
    line_ending = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    lines, started = line_starts.fix_line_starts(lines, fixes.line_starts)
    joined_lines = linebreaks.join_hyphenated_lines(lines, fixes.joins)
    return line_ending.join(joined_lines), started, len(lines) - len(joined_lines)


def _quote_word_counts(paths: list[Path], fixes: ApprovedFixes) -> Counter[str]:
    """Count, over the whole corpus, the words that occur inside quotations."""
    wanted: set[str] = set()
    for path in paths:
        wanted |= protected_text.quote_words(_fix_lines(read_text(path), fixes)[0])
    return protected_text.count_words((_fix_lines(read_text(p), fixes)[0] for p in paths), wanted)


def _protected_rows(
    relative: Path, text: str, corrections: dict[str, str], quotes: list[protected_text.Quote]
) -> list[list[object]]:
    """One log row per correction left out because it falls in a protected quote."""
    rows: list[list[object]] = []
    for match in correction_pattern(corrections).finditer(text):
        quote = next((q for q in quotes if q.start <= match.start() < q.end), None)
        if quote is None:
            continue
        context = text[
            max(0, match.start() - CONTEXT_WIDTH // 2) : match.end() + CONTEXT_WIDTH // 2
        ]
        word = match.group()
        rows.append(
            [
                relative,
                word,
                corrections[word.lower()],
                round(quote.rare_share, 3),
                quote.lead_in,
                context.replace("\n", " / "),
            ]
        )
    return rows


def apply_approved_fixes(
    source_root: Path,
    target_root: Path,
    fixes: ApprovedFixes,
    log_path: Path,
    is_protecting_quotes: bool = True,
) -> Counter[str]:
    """Copy a text tree, applying the approved line-start fixes, joins and corrections.

    Word corrections are left out inside quotations that look like verbatim lay writing
    (see `protected_text`); each one left out is listed in a second log next to
    `log_path`, named `<log name>_protected_quotes.csv`, for a person to check. Finding
    those quotations reads the corpus twice more before the copy is written.

    Args:
        source_root: Folder of text files (never changed).
        target_root: Folder for the corrected copy.
        fixes: The approved fixes.
        log_path: CSV log with the number of changes per file and step.
        is_protecting_quotes: False applies the corrections inside quotations too.

    Returns:
        The total number of changes per step, and of corrections left out.
    """
    paths = list_text_files(source_root)
    is_protecting = is_protecting_quotes and bool(fixes.corrections)
    word_counts = _quote_word_counts(paths, fixes) if is_protecting else Counter()
    totals: Counter[str] = Counter()
    log_rows: list[list[object]] = []
    protected_log_rows: list[list[object]] = []
    for path in paths:
        relative = path.relative_to(source_root)
        text, started, joined = _fix_lines(read_text(path), fixes)
        quotes = protected_text.protected_quotes(text, word_counts) if is_protecting else []
        protected_log_rows += _protected_rows(relative, text, fixes.corrections, quotes)
        spans = [(quote.start, quote.end) for quote in quotes]
        corrected_text, corrected = apply_corrections(text, fixes.corrections, spans)
        write_text(output_path(path, source_root, target_root), corrected_text)
        if started or joined or corrected:
            log_rows.append([relative, started, joined, corrected])
        totals.update({"line_starts": started, "joins": joined, "corrections": corrected})
    totals["corrections_left_in_quotes"] = len(protected_log_rows)
    _write_csv(log_path, ["file", "line_starts", "joins", "corrections"], log_rows)
    if is_protecting:
        protected_log = log_path.with_name(log_path.stem + "_protected_quotes.csv")
        header = ["file", "word", "correction_left_out", "quote_rare_share", "lead_in", "context"]
        _write_csv(protected_log, header, protected_log_rows)
    return totals


def review_items_from_csv(
    candidates_csv: Path, key_column: str, proposal_column: str, count_column: str, root: Path
) -> list[ReviewItem]:
    """Turn a candidate list into review items, with one context taken from the corpus.

    The context is found by searching the example file named in an "example" column
    ("path:line"), or, without one, by searching for the key in the first file that
    contains it.

    Args:
        candidates_csv: A list written by one of the find_* or check_words steps.
        key_column: Column that identifies the candidate.
        proposal_column: Column with the proposed change.
        count_column: Column with the number of occurrences.
        root: Folder of text files, for the contexts.
    """
    items = []
    for row in _read_csv(candidates_csv):
        key = row[key_column]
        item = ReviewItem(key, key, f"{key} -> {row[proposal_column]}", int(row[count_column]))
        example = row.get("example", "")
        if example:
            relative, _, line_number = example.rpartition(":")
            path = root / relative
            lines = list(iter_lines(path))
            line = lines[int(line_number) - 1] if line_number.isdigit() else ""
            following = lines[int(line_number)] if int(line_number) < len(lines) else ""
            context = Context(line[-CONTEXT_WIDTH:], "", " / " + following[:CONTEXT_WIDTH],
                              relative, file_link(path))  # fmt: skip
            item.contexts.append(context)
        items.append(item)
    return items
