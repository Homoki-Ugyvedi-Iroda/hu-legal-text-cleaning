# BHGY findings

What the cleaning found in the Collection of Court Decisions (Bírósági Határozatok
Gyűjteménye, BHGY): about 225,000 published, anonymised decisions from 1996 to 2026,
downloaded as RTF and DOCX files. The original text was never changed; all fixes went
into a cleaned copy, with a log of every change.

## Summary of the cleaning

| # | Step | What it fixed | Scale |
|---|---|---|---|
| 1 | Conversion of RTF and DOCX | Kept table cells and ő/ű (a generic converter lost both); decoded Central European fonts with cp1250; turned the "…" and "§" placeholders written in a Shift-JIS font back into those characters; kept en dashes, quotation marks and bullets | about 62,000 RTF and DOCX files in the first batch; a first version had dropped special characters in 6,811 files |
| 2 | Error profile by year | Header and footer text inside the body, letter-spaced headings, odd characters, OCR word errors | see the tables below |
| 3 | Word check with Hunspell | Unknown words after filtering names, anonymisation leftovers and abbreviations; reviewed by a person; result: a correction table | 112 words (72 safe, 35 to check, 5 not to apply) |
| 4 | Lost first letters | "értett" → "Sértett", "ővárosi" → "Fővárosi" | 2,801 lines fixed |
| 5 | Words split at line ends | "alkalma-" / "zottai" → "alkalmazottai" | 1,914 joins |
| 6 | NUL padding | removed | 10,875 files |
| 7 | Unicode NFC | composed separately stored accents | 170 files changed; 76 files keep marks without a composed form |
| 8 | Unaccented typing | decisions typed mostly without accents | very rare: 2 in a sample of about 5,900 |
| 9 | Wrong code page | Hungarian text in a font declared as Arabic, Shift-JIS, Greek or Hebrew ("hatلrozat", "bekezd駸"); re-converted from the source | 617 decisions, about 89,000 damaged words |
| 10 | Soft hyphens | invisible hyphens inside words ("in" + soft hyphen + "gatlan") removed; 54 at line ends kept, as they mark split words | 9,630 removed in 1,618 decisions |
| 11 | Correction table | the 104 "yes" rows applied | 46,173 replacements in 18,216 files |
| 12 | Look-alike letters | Cyrillic and Greek letters inside Latin words replaced ("ЕU", "Citroёn", "Kӓrcher") | 47 words in 39 files |

Steps 4 and 5 together changed 2,649 files. The correction table of step 3 (step 11) was
applied afterwards.

## Wrong code pages

Some RTF files declare one of their fonts with the character set of another script,
most often Arabic (`\fcharset178`) for a font called "Times New Roman", while the text
in that font is Hungarian in the Central European code page. Read as the declaration
says, every accented letter in that font becomes a letter of the other script:
"határozat" → "hatلrozat", "bíróság" → "bيrَsلg". Other variants found:

| Variant | Example | Decisions repaired |
|---|---|---:|
| Arabic font (cp1256) | "vلdlott" for "vádlott" | 550 |
| Shift-JIS font (cp932), the font of the anonymisation placeholders | "bekezd駸" for "bekezdés" | 35 |
| only part of a word, or the code page could not be named | | 26 |
| Greek (cp1253) and Hebrew (cp1255) fonts | | 5 |
| Chinese (GBK) carried inside the RTF as Unicode | "K鷕ia" for "Kúria" | 1 |

The damage is concentrated in 2008–2013 (543 of the 617) and in the Fővárosi Törvényszék
(372). It also misled the later steps: in the review of the correction table, "elk" and
"els" occurrences came from these decisions ("elkِvetés").

The 733 decisions with any suspicious word were converted again from their RTF or DOCX
source with the fixed converter; the earlier line-start fixes and joins of 5 of them were
applied again. The replaced versions are kept as a backup. 116 decisions still have such
words, and they are correct: Greek symbols next to Latin letters ("μg/ml"), Ukrainian
text, and look-alike letters of other scripts typed by mistake ("2014/17/ЕU" with a
Cyrillic "Е", "Grüβen" with a Greek "β").

Where the anonymisation tool had already lost a letter in the source (written as the
Shift-JIS "・"), the text now shows "�": 145 such places in 21 decisions.

## Error profile by year

### Share of sampled decisions containing a word from the correction table

| Period | Decisions with an error | Most frequent words |
|---|---:|---|
| 1996–2006 | 16.8% (150 of 895) | hogya, tanu, gatlan, aluminium, extasy |
| 2007–2013 | 9.3% (163 of 1,750) | tanu, negativ, biróság, avádlott, vadlott |
| 2014–2021 | 6.6% (132 of 2,000) | alapjan, tarsashaz, onkormanyzat, berleti |
| 2022–2026 | 11.8% (147 of 1,250) | felepres, extasy, iphone, üzletrészadásvételi |

The 2022–2026 rise comes from typos and spelling variants in newly written decisions,
not from OCR.

### Layout leftovers, whole corpus

| Years | Decisions with a header or footer line inside the text | Decisions with a page marker | Hyphenated line ends per decision |
|---|---:|---:|---:|
| 2003–2014 | 2.9–9.3% | 1.9–4.2% | 0.01–0.37 |
| 2015 | 1.5% | 0.6% | 0.01 |
| 2016–2020 | 3.5–4.4% | 0.1–0.3% | 0.01–0.02 |
| 2021–2026 | 1.4–2.8% | 0.0–0.4% | 0.00–0.01 |

Page markers almost disappear from 2015, but header and footer lines inside the text
remain at a few per cent until 2020.

## Sentence splitting: why lines start in lowercase

After a first rule-based split of the whole corpus (222,362 files, 35.8 million
segments), 552,874 segments started in lowercase. The rules sorted them by cause:

| Cause | Segments |
|---|---:|
| signature block | 250,771 |
| list item | 84,405 |
| anonymisation placeholder | 82,065 |
| role word or article at the start | 50,026 |
| after a colon or semicolon | 27,316 |
| other | 24,904 |
| letter-spaced heading | 9,669 |
| damaged wrap (a 1–3 letter fragment) | 8,431 |
| wrapped line after an abbreviation or number | 8,028 |
| blank form field | 5,765 |
| bullet exported as a letter | 1,494 |

A review of 470 flagged lines found that a lowercase start after an abbreviation,
ordinal or date was a wrongly split wrapped line in 80 of 80 cases; the other causes were
correct splits of layout or anonymisation artefacts. The splitter in this package joins
the first kind and keeps the others apart.

## Open points

- Two correction-table rows stay "check": "gatlan" and "els", which need a different fix per
  occurrence.
- Words split by a false space ("els ő", "elk övetési") are a separate error type, found
  during the review; no step looks for them yet.
- 54 soft hyphens at line ends (50 decisions) mark split words that the line-break step
  does not yet recognise.
- 25 hyphen pairs are on hold (number words, role labels) and 134 joins across blank
  lines were not applied.
- 50 line-start candidates are still unanswered in `line_start_fixes.csv`.
- 76 files keep combining marks without a composed form.
- Greek symbols next to Latin letters ("μg/ml", "Δ9-THC") and the Cyrillic "Н" in "Нarketan"
  (which may stand for H or N) are left as they are.
