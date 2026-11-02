# ADR-2026-11-01-hunspell-command-line: Hunspell as a command-line program

- **Status:** Accepted

## Context
The word check and the line-break check need a Hungarian spell checker that knows
inflected forms. Hunspell with the `hu_HU` dictionary is the standard one. Its Python
bindings (`pyhunspell`, `cyhunspell`) need a C compiler and the Hunspell library at
install time, and are hard to install on Windows.

## Decision
Call the `hunspell` program through `subprocess`, sending all words of a batch at once on
standard input (`hunspell_lines` in the original scripts, `Hunspell` class here). On
Windows, run it inside WSL (`wsl -e hunspell`).

## Alternatives considered
- **Python bindings:** faster per word, but difficult to install and not needed, because
  the words are checked in large batches.
- **spylls (pure-Python Hunspell):** no compiler needed, but much slower on hundreds of
  thousands of words and a third-party runtime dependency.

## Consequences
- No Python dependency; Hunspell and the Hungarian dictionary are system packages.
- Windows users need WSL. Tests replace Hunspell with a small fake object, so they run
  without it.
