"""Command-line interface: `hu-legal-clean <step> ...`.

Run `hu-legal-clean --help` for the list of steps, and `hu-legal-clean <step> --help`
for the arguments of one step. The order of a full run is described in
docs/pipeline.md.
"""

import argparse
import logging
from pathlib import Path

from hu_legal_cleaning import check_rows, pipeline, sentences
from hu_legal_cleaning.corrections import bundled_table_path, load_corrections
from hu_legal_cleaning.evaluation import evaluate_splitter
from hu_legal_cleaning.hunspell import Hunspell
from hu_legal_cleaning.review_page import build_review_page
from hu_legal_cleaning.text_files import read_text


def _convert(args: argparse.Namespace) -> None:
    statuses = pipeline.convert_folder(args.source, args.target, args.log)
    print(f"Converted: {dict(statuses)}; log: {args.log}")


def _clean_characters(args: argparse.Namespace) -> None:
    changed = pipeline.clean_characters_folder(args.source, args.target, args.log)
    print(f"{changed} files changed; log: {args.log}")


def _find_encoding_damage(args: argparse.Namespace) -> None:
    to_repair = pipeline.find_encoding_damage(args.source, args.out)
    print(f"{to_repair} files to repair; list: {args.out}")


def _repair_encoding(args: argparse.Namespace) -> None:
    changed = pipeline.repair_encoding_folder(args.source, args.target, args.log, args.only_changed)
    print(f"{changed} files repaired; log: {args.log}")


def _find_linebreaks(args: argparse.Namespace) -> None:
    count = pipeline.find_linebreak_candidates(args.source, Hunspell(), args.out)
    print(f"{count} split-word pairs written to {args.out}")


def _find_line_starts(args: argparse.Namespace) -> None:
    count = pipeline.find_line_start_candidates(args.source, args.out)
    print(f"{count} candidates written to {args.out}")


def _check_words(args: argparse.Namespace) -> None:
    count = pipeline.check_words(args.source, Hunspell(), args.out, args.sample)
    print(f"{count} unknown words written to {args.out}")


def _audit_abbreviations(args: argparse.Namespace) -> None:
    count = pipeline.audit_abbreviations_folder(args.source, args.out, args.sample)
    print(f"{count} dotted words written to {args.out}")


def _review_page(args: argparse.Namespace) -> None:
    items = pipeline.review_items_from_csv(
        args.candidates, args.key, args.proposal, args.count, args.source
    )
    page = build_review_page(items, args.options.split(","), args.title, args.out.stem)
    args.out.write_text(page, encoding="utf-8")
    print(f"Review page with {len(items)} items: {args.out}")


def _review_check_rows(args: argparse.Namespace) -> None:
    rows = check_rows.load_check_rows(args.table)
    check_rows.find_occurrences(args.source, rows, args.examples, args.context_lines)
    page = check_rows.build_check_page(rows, args.out.stem)
    args.out.write_text(page, encoding="utf-8")
    print(f"Review page with {len(rows)} words: {args.out}")


def _apply(args: argparse.Namespace) -> None:
    corrections = load_corrections(args.corrections) if args.corrections else {}
    fixes = pipeline.load_approved_fixes(args.line_starts, args.joins, corrections)
    totals = pipeline.apply_approved_fixes(args.source, args.target, fixes, args.log)
    print(f"Applied: {dict(totals)}; log: {args.log}")


def _split(args: argparse.Namespace) -> None:
    for segment, cause in sentences.split_with_causes(read_text(args.file)):
        print(f"[{cause}] {segment}" if cause else segment)


def _evaluate(_: argparse.Namespace) -> None:
    score = evaluate_splitter(sentences.split_sentences)
    print(f"Boundary precision {score.precision}, recall {score.recall}, F1 {score.f1}")


def _add_source_target(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", type=Path, help="folder to read (never changed)")
    parser.add_argument("target", type=Path, help="folder to write the copy to")
    parser.add_argument("--log", type=Path, required=True, help="CSV log to write")


def _add_source_out(parser: argparse.ArgumentParser, with_sample: bool = False) -> None:
    parser.add_argument("source", type=Path, help="folder of text files")
    parser.add_argument("out", type=Path, help="CSV file to write")
    if with_sample:
        parser.add_argument("--sample", type=int, default=0, help="files to read (0 = all)")


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser with one sub-command per pipeline step."""
    parser = argparse.ArgumentParser(prog="hu-legal-clean", description=__doc__)
    steps = parser.add_subparsers(dest="step", required=True)

    step = steps.add_parser("convert", help="RTF/DOCX to text")
    _add_source_target(step)
    step.set_defaults(run=_convert)

    step = steps.add_parser("find-encoding-damage", help="words decoded with a wrong code page")
    _add_source_out(step)
    step.set_defaults(run=_find_encoding_damage)

    step = steps.add_parser("repair-encoding", help="repair words decoded with a wrong code page")
    _add_source_target(step)
    step.add_argument("--only-changed", action="store_true", help="write only changed files")
    step.set_defaults(run=_repair_encoding)

    step = steps.add_parser("clean-characters", help="NUL, NFC and õ/û repair")
    _add_source_target(step)
    step.set_defaults(run=_clean_characters)

    step = steps.add_parser("find-linebreaks", help="words split by a hyphen at a line end")
    _add_source_out(step)
    step.set_defaults(run=_find_linebreaks)

    step = steps.add_parser("find-line-starts", help="lines that lost their first letter")
    _add_source_out(step)
    step.set_defaults(run=_find_line_starts)

    step = steps.add_parser("check-words", help="words unknown to Hunspell, sorted into kinds")
    _add_source_out(step, with_sample=True)
    step.set_defaults(run=_check_words)

    step = steps.add_parser("audit-abbreviations", help="find abbreviations in the corpus")
    _add_source_out(step, with_sample=True)
    step.set_defaults(run=_audit_abbreviations)

    step = steps.add_parser("review-page", help="build a keyboard review page from a CSV")
    step.add_argument("candidates", type=Path, help="candidate CSV from a find step")
    step.add_argument("source", type=Path, help="folder of text files, for the contexts")
    step.add_argument("out", type=Path, help="HTML file to write")
    step.add_argument("--key", default="damaged", help="column that identifies an item")
    step.add_argument("--proposal", default="correction", help="column with the proposal")
    step.add_argument("--count", default="damaged_lines", help="column with the count")
    step.add_argument("--options", default="apply,no,unsure", help="answers, comma-separated")
    step.add_argument("--title", default="Review", help="page title")
    step.set_defaults(run=_review_page)

    step = steps.add_parser(
        "review-check-rows", help="page to review the check rows of the correction table"
    )
    step.add_argument("source", type=Path, help="folder of text files")
    step.add_argument("out", type=Path, help="HTML file to write")
    step.add_argument("--table", type=Path, default=bundled_table_path(), help="correction table")
    step.add_argument("--examples", type=int, default=check_rows.DEFAULT_EXAMPLES)
    step.add_argument("--context-lines", type=int, default=check_rows.DEFAULT_CONTEXT_LINES)
    step.set_defaults(run=_review_check_rows)

    step = steps.add_parser("apply", help="apply approved fixes to a copy")
    _add_source_target(step)
    step.add_argument("--line-starts", type=Path, help="approved line-start fixes (CSV)")
    step.add_argument("--joins", type=Path, help="approved hyphen joins (CSV)")
    step.add_argument(
        "--corrections",
        type=Path,
        nargs="?",
        const=bundled_table_path(),
        help="correction table; without a path the bundled table is used",
    )
    step.set_defaults(run=_apply)

    step = steps.add_parser("split", help="split one text file into sentences")
    step.add_argument("file", type=Path)
    step.set_defaults(run=_split)

    step = steps.add_parser("evaluate-splitter", help="score the splitter on the gold set")
    step.set_defaults(run=_evaluate)
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the command line.

    Args:
        argv: The arguments; None means the program's own arguments.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
