# Sentence splitting

`hu_legal_cleaning.sentences` is a rule-based sentence splitter for Hungarian court
decisions. It does not use a neural network, runs on any machine, and splits the whole
BHGY corpus in minutes.

## How it works

1. **Wrapped lines are joined.** Decision texts break lines both at paragraph ends and in
   the middle of sentences. A line that starts in lowercase continues the previous one
   when the previous line is unfinished, or ends in an abbreviation, an ordinal or date
   number, or a roman numeral. It stays a line of its own when it is a list item,
   signature line, anonymisation placeholder, bullet, letter-spaced heading or blank form
   field.
2. **Paragraphs are split** at ".", "!", "?" or "…" followed by a capital letter or a
   digit, except after:
   - a known abbreviation (the statute names are case-sensitive: "Be." is the Code of
     Criminal Procedure, "be." an ordinary word);
   - an initial ("K.", "Sz.L.");
   - an ordinal or date number ("2015.", "22.");
   - a roman numeral ("III.");
   - "§" followed by a paragraph number ("228. §. (1)").

   A statute name followed by a capitalised word does end a sentence:
   "… a Ptk. Ezért a bíróság …".

## Results

On the bundled gold set of 40 passages (140 segments), counted on sentence boundaries:

| Splitter | Boundary F1 |
|---|---:|
| this package | 99.3 |
| earlier version of the rules (hand list only) | 95.2 |
| wtpsplit SaT (pre-trained neural model) | 98.0 |
| huSpaCy, with line breaks as hard boundaries | 92.1 |
| Stanza, with line breaks as hard boundaries | 91.3 |
| BlingFire | 86.2 |
| Punkt, trained on the corpus | 76.3 |

The gold set was drafted from an earlier version of the rules and then corrected by hand,
so it is not fully independent of them; the scores of the rules are probably somewhat too
favourable. A larger, independent gold set that deliberately includes the artefact cases
is the next step before any neural model is trained.

## Flags for lowercase starts

`split_with_causes` tags every segment that starts in lowercase with its likely cause
(signature block, list item, placeholder, damaged wrap and so on), so later analyses can
filter out layout and anonymisation artefacts. The causes found in BHGY are counted in
[BHGY findings](bhgy-findings.md).
