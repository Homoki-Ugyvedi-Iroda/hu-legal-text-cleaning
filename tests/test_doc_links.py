"""Every relative link in the repository's Markdown files must point to a file that exists.

GitHub shows a broken link only when someone clicks it, so this test catches a renamed or
deleted page before it is pushed.
"""

import re
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
# Folders that are not part of the published repository.
SKIPPED_FOLDERS = {".git", ".venv", "site", ".pytest_cache", ".ruff_cache"}
# A Markdown link: [text](target). Images (![alt](target)) match too, which is wanted.
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# Code blocks and inline code may show link syntax as an example, so they are not checked.
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")


def markdown_files() -> list[Path]:
    return [
        path
        for path in REPOSITORY.rglob("*.md")
        if not SKIPPED_FOLDERS.intersection(path.relative_to(REPOSITORY).parts)
    ]


def broken_links(path: Path) -> list[str]:
    text = CODE.sub("", path.read_text(encoding="utf-8"))
    broken = []
    for target in LINK.findall(text):
        if target.startswith(EXTERNAL_PREFIXES):
            continue
        # "page.md#section" points to page.md; the anchor is not checked.
        file_part = target.split("#", 1)[0]
        if not (path.parent / file_part).exists():
            broken.append(target)
    return broken


def test_relative_links_point_to_existing_files():
    problems = {
        str(path.relative_to(REPOSITORY)): links
        for path in markdown_files()
        if (links := broken_links(path))
    }
    assert problems == {}


def test_broken_link_is_found(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("[ok](page.md) [gone](missing.md) [web](https://example.com)", "utf-8")
    assert broken_links(page) == ["missing.md"]
