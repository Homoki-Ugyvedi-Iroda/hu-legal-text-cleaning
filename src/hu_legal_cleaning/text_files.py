"""Find, read and write the plain-text files of a corpus.

A corpus is a folder tree of UTF-8 `.txt` files, for example
`decisions/2015/Fővárosi_Törvényszék/P.12345_2014_10.txt`. Every cleaning step reads
from one folder tree and writes to another, so the original files are never changed.
"""

import random
from collections.abc import Iterator
from pathlib import Path

TEXT_SUFFIX = ".txt"
# Files whose name starts with this are logs or manifests written next to the texts.
SKIPPED_PREFIX = "_"


def list_text_files(root: Path) -> list[Path]:
    """Return every text file under `root`, sorted by path.

    Args:
        root: Top folder of the corpus.

    Returns:
        The paths of the `.txt` files, skipping files whose name starts with `_`.
    """
    return sorted(
        path
        for path in root.rglob("*" + TEXT_SUFFIX)
        if path.is_file() and not path.name.startswith(SKIPPED_PREFIX)
    )


def sample_text_files(root: Path, sample_size: int, seed: int = 7) -> list[Path]:
    """Return a reproducible random sample of the corpus.

    Args:
        root: Top folder of the corpus.
        sample_size: Number of files to return; 0 means all files.
        seed: Seed of the random generator, so the same sample comes back every time.

    Returns:
        The sampled paths.
    """
    files = list_text_files(root)
    if sample_size <= 0 or sample_size >= len(files):
        return files
    return random.Random(seed).sample(files, sample_size)


def read_text(path: Path) -> str:
    """Read a text file as UTF-8, replacing undecodable bytes and keeping line endings."""
    # newline="" keeps "\r\n" as it is, so writing the text back changes nothing else.
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        return handle.read()


def write_text(path: Path, text: str) -> None:
    """Write a text file as UTF-8, creating its folder and keeping line endings as given."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def iter_lines(path: Path) -> Iterator[str]:
    """Yield the lines of a text file without their line endings."""
    yield from read_text(path).replace("\r\n", "\n").split("\n")


def output_path(path: Path, source_root: Path, target_root: Path) -> Path:
    """Return where a file of the source tree goes in the target tree."""
    return target_root / path.relative_to(source_root)
