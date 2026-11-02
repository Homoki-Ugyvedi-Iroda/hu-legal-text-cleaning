"""Ask the Hunspell spell checker which words it knows and what it suggests.

Hunspell runs as a command-line program (see ADR-2026-11-01-hunspell-command-line).
On Linux and macOS it is called directly; on Windows it is called inside WSL, the
Windows Subsystem for Linux, where `sudo apt install hunspell hunspell-hu` installs it.
"""

import platform
import shutil
import subprocess
from collections.abc import Iterable

HUNGARIAN_DICTIONARY = "hu_HU"
# Hunspell's "-a" (pipe) mode answers each word with one line starting with:
# "*" known, "+" known by its stem, "-" known compound, "&" unknown with suggestions,
# "#" unknown without suggestions.
KNOWN_MARKERS = ("*", "+", "-")
SUGGESTION_MARKER = "&"
ANSWER_MARKERS = KNOWN_MARKERS + (SUGGESTION_MARKER, "#")


class Hunspell:
    """A Hungarian Hunspell spell checker run as a separate program.

    Attributes:
        dictionary: Name of the Hunspell dictionary, e.g. "hu_HU".
        command: The command line prefix that starts Hunspell.
    """

    def __init__(self, dictionary: str = HUNGARIAN_DICTIONARY) -> None:
        """Find the Hunspell program.

        Args:
            dictionary: Name of the Hunspell dictionary to use.

        Raises:
            FileNotFoundError: If neither `hunspell` nor (on Windows) `wsl` is installed.
        """
        self.dictionary: str = dictionary
        self.command: list[str] = self._find_command()

    @staticmethod
    def _find_command() -> list[str]:
        if shutil.which("hunspell"):
            return ["hunspell"]
        if platform.system() == "Windows" and shutil.which("wsl"):
            return ["wsl", "-e", "hunspell"]
        raise FileNotFoundError("Hunspell not found: install hunspell and hunspell-hu.")

    def _run(self, words: Iterable[str], mode: str) -> str:
        word_list = "\n".join(words) + "\n"
        # Runs Hunspell once for the whole list, feeding the words on standard input.
        result = subprocess.run(
            [*self.command, "-d", self.dictionary, "-i", "utf-8", mode],
            input=word_list.encode("utf-8"),
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8", "replace")

    def unknown_words(self, words: Iterable[str]) -> set[str]:
        """Return the words Hunspell does not know.

        Args:
            words: Single words, without spaces.

        Returns:
            The unknown ones.
        """
        output = self._run(words, "-l")
        return {line.strip() for line in output.splitlines() if line.strip()}

    def suggestions(self, words: list[str]) -> dict[str, list[str]]:
        """Return Hunspell's correction suggestions for each unknown word.

        Args:
            words: Single words, without spaces.

        Returns:
            Word -> suggestions, best first. Known words and words without suggestions
            are left out.
        """
        output = self._run(words, "-a")
        answers = [line for line in output.splitlines() if line[:1] in ANSWER_MARKERS]
        return parse_suggestions(words, answers)


def parse_suggestions(words: list[str], answers: list[str]) -> dict[str, list[str]]:
    """Pair Hunspell's "-a" answer lines with the words they answer.

    Args:
        words: The words in the order they were sent.
        answers: One answer line per word, e.g. "& tanu 4 0: tanú, taun, tabu, tani".

    Returns:
        Word -> suggestions for the words answered with "&".
    """
    found: dict[str, list[str]] = {}
    for word, answer in zip(words, answers, strict=False):
        if answer.startswith(SUGGESTION_MARKER) and ":" in answer:
            found[word] = [part.strip() for part in answer.split(":", 1)[1].split(",")]
    return found
