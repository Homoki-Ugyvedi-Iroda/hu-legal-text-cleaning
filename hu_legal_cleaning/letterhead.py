"""Remove the accented letters left over from an anonymised letterhead.

In some decisions the first line starts with a run of Hungarian accented letters glued
to the court name: "őáÍéőá... Ítélőtábla", "ááíóá... Járásbíróság", "íööáóVAS MEGYEI
BÍRÓSÁG". The run holds exactly the accented letters of words that were removed from the
letterhead ("Fővárosi Ítélőtábla" -> ő, á, Í, é, ő, á), so the tool that removed them
kept the accented characters. No Hungarian word starts with such a run, so it is removed.

Only the first non-empty line is checked, and these runs stay:

- one letter repeated at least four times ("ÉÉÉÉ tanú"): an anonymisation placeholder
  like "GGGGGG";
- a run followed by a small letter, where the heading itself is damaged
  ("...áővárosi Közigazgatási");
- up to three capitals followed by a capital, which may begin an all-caps heading
  ("ÍTÉLET", "ÉS").
"""

import re

ACCENTED = "áéíóöőúüűÁÉÍÓÖŐÚÜŰ"
# "++" is possessive: the run is never shortened to satisfy the lookahead.
LEADING_RUN = re.compile(rf"^([{ACCENTED}]++)(?![a-záéíóöőúüű])")
MIN_PLACEHOLDER_LENGTH = 4
MAX_CAPITALS_STARTING_A_WORD = 3
LINE_BREAK = "\n"


def _is_residue(run: str, following: str) -> bool:
    if len(set(run)) == 1 and len(run) >= MIN_PLACEHOLDER_LENGTH:
        return False
    starts_capital_word = following.isupper() and run.isupper()
    return not (starts_capital_word and len(run) <= MAX_CAPITALS_STARTING_A_WORD)


def remove_letterhead_residue(text: str) -> tuple[str, str]:
    """Remove the letterhead residue from the first non-empty line.

    Args:
        text: A decision's text.

    Returns:
        The new text and the removed run ("" if nothing was removed).
    """
    lines = text.split(LINE_BREAK)
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        match = LEADING_RUN.match(line)
        if not match or not _is_residue(match.group(1), line[match.end() : match.end() + 1]):
            return text, ""
        lines[index] = line[match.end() :]
        return LINE_BREAK.join(lines), match.group(1)
    return text, ""
