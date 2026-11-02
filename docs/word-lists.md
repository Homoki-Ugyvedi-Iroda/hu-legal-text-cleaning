# Word lists

The lists are in `src/hu_legal_cleaning/data/`, so they are installed with the package.
All were built from the BHGY court decisions. "Reviewed" means a person checked every
row; "draft" means the rows were sorted automatically or by an AI assistant and still need
a person's check.

| File | Content | Rows | Status |
|---|---|---:|---|
| `correction_table.csv` | OCR errors and typos with the correction, the error type and whether it is safe to apply | 112 | reviewed |
| `words_unknown_to_hunspell.csv` | words Hunspell does not know but that a reviewer accepted, with a category | 372 | reviewed |
| `abbreviations_court_decisions.csv` | dotted words measured in 30,000 decisions, with category and meaning | 846 | reviewed |
| `abbreviations_statutes_njt.txt` | statute short names of the National Legislation Database (NJT) | 375 | as published |
| `line_start_fixes.csv` | damaged line-start words with their correction and the reviewer's decision | 118 | 68 answered |
| `hyphen_join_decisions.csv` | split words the spell checker could not decide, with the reviewer's decision | 140 | reviewed |
| `sentence_gold.jsonl` | 40 passages with their correct sentence split | 40 | reviewed |
| `review_page_template.html` | template of the review page (not a list) | | |
| `check_rows_template.html` | template of the page for the "check" rows (not a list) | | |

## Correction table

Columns: `wrong`, `proposed`, `type`, `safe_to_apply`, `occurrences`, `decisions`,
`first_year`, `last_year`, `hunspell_suggestions`, `occurrences_if_not_NFC`,
`review_note`.

- `yes`: the wrong form is never a correct word; apply everywhere.
- `check`: usually wrong but may be correct in some contexts; look at each case. After
  the review of 2 November 2026 two rows remain: "gatlan" (the second half of "in gatlan"
  or "in-" / "gatlan", where the space or line break should go rather than the word) and
  "els" (mostly "els ő" split by a false space). `review_note` says what was found.
- `no`: kept for reference: the "error" disappears with NFC normalisation, or the
  occurrences need different corrections ("elk").

Current counts: 104 `yes`, 6 `no`, 2 `check`. The 104 `yes` rows were applied to the BHGY
cleaned copy on 2 November 2026: 46,173 replacements in 18,216 files. The 35 former `check` rows were reviewed
with `hu-legal-clean review-check-rows` (six examples per word with ten lines of context):
32 became `yes`, 1 became `no`, 2 stayed `check`.

Error types: accent (65), one character (18), letter cut off by a space (10), two
characters (5), decomposed accent (5), missing space (4), doubled letter (2), letter lost
(1), hyphenation fragment (1), brand-name capitals (1).

## Words unknown to Hunspell

Each word was marked valid by a reviewer. The categories help to decide which words to add
to a custom spell-checker dictionary:

| Category | Rows | Examples | Add to a dictionary? |
|---|---:|---|---|
| `domain_word` | 162 | ellenkérelem, védirat, terhelti, perbeni, álképviselő, kógens | yes |
| `spelling_variant` | 82 | ekörben, figyelembevéve, ingatlannyilvántartás, jóhírnév | yes, if variants are wanted |
| `foreign_latin_or_technical` | 76 | res iudicata, sui generis, pendrive, eIDAS | yes, as needed |
| `number_word` | 10 | kettőszázezer, egyszázötvenezer | yes |
| `name_or_place` | 14 | Székesfehérvár, Mosonmagyaróvár | in a name list instead |
| `lost_letter_fragment` | 13 | érelmezte, ásodfokú | no: fixed by the line-start step |
| `anonymisation_leftover` | 11 | településra, nevevádlott | no: placeholders |
| `abbreviation_without_dot` | 2 | frsz, össz | in the abbreviation list |
| `word_part` | 2 | pót, utó | no |

## Abbreviations found in court decisions

Built with `hu-legal-clean audit-abbreviations` on 30,000 decisions of the cleaned BHGY
copy, plus a short hand list. Columns: `token` (lowercase, without the final dot),
`commonest_form`, `occurrences`, `lowercase_share` (how often a lowercase word follows),
`number_share` (how often a number or "§" follows), `verdict`, `in_njt_list`,
`is_abbreviation`, `category`, `meaning`, `source`.

| Category | Rows | Examples |
|---|---:|---|
| `legal` | 447 | Ptk., Btk., Pp., Be., bek., hrsz., s.k., rb., jkv., BH, rPtk. |
| `general` | 65 | kb., pl., stb., db., ún., ker., krt., fszt., szül. |
| `initials` | 228 | K.J., Sz.L. (initials of anonymised persons) |
| `party_numbering` | 56 | I.r., II.r., XXIII.r. (numbered parties) |
| `company_form` | 28 | Kft., Zrt., Bt., Nyrt., GmbH, s.r.o. |
| `placeholder` | 22 | neve., címe., szám. (anonymisation artefacts, not abbreviations: the dot may end a sentence) |

The categories and meanings were drafted by an AI assistant and reviewed by a person on
2 November 2026. 22 abbreviations have no meaning yet (e.g. "hb.", "gyk.", "iü.",
"nyá."). Some forms are artefacts: "neveI.r", "azI.r" and "vádlottVI.r" are a
placeholder or a word glued to a party number.

## Statute short names (NJT)

Copied from the list of commonly known statute abbreviations of the National Legislation
Database (Nemzeti Jogszabálytár). Abbreviations change as statutes are replaced, so the
corpus audit above found many older ones that are not on the current list
("Ket.", "Csjt.", "Mt." of 1992, "rPtk.").
