# ADR-2026-11-04-skip-corrections-in-lay-quotes: Leave word corrections out of quoted lay writing by default

- **Status:** Proposed

## Context
On a corpus of 225,401 court decisions the correction table made 46,173 replacements.
727 of them fell inside quotation marks. A person checked them and marked 24 as verbatim
lay writing (text messages, letters), quoted errors or old spelling, which must stay as
written; the rest were court prose. The same review found that anonymisation placeholders
such as "tanu1" had been turned into "tanú1", because a digit after a word counted as a
word boundary. The undoing had to be done by hand from backups.

Two signals separate lay writing from court prose: a word naming a message or letter
before the quotation, and the share of words inside it that are rare in the corpus.
Measured against the 24 marked places:

| Test | Quotations' replacements caught | Of the 24 |
|---|---:|---:|
| naming word and rare share ≥ 10% | 23 | 15 |
| naming word | 92 | 15 |
| rare share ≥ 10% | 105 | 24 |

## Decision
- A word touching a digit or underscore is never corrected (placeholders).
- `apply_approved_fixes` and `apply --corrections` leave a correction out when it falls
  in a quotation whose rare-word share is at least 10%, and list every one left out in
  `<log name>_protected_quotes.csv` for review. `--correct-quotes` turns this off.
- Corpus counts are taken only for words that occur inside quotations, in a separate
  pass, so memory stays small on large corpora.

## Alternatives considered
- **Correct everything, flag the quotations for review afterwards:** the harm is done
  first and has to be undone from backups, which is what happened on the test corpus.
- **Skip every quotation:** about 700 legitimate corrections of court prose lost for 24
  protected places.
- **Require the naming word as well:** fewer corrections left out (23 instead of 105),
  but a third of the lay writing still corrected.

## Consequences
- About 80 legitimate corrections per 46,000 are left out; the log lets a person apply
  them by hand.
- On a small corpus nearly every quotation is protected, because nearly every word is
  rare there.
- The apply step reads the corpus three times instead of once.
- Lay writing quoted without quotation marks is not detected.
