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
| 13 | Western and symbol fonts | characters of Western fonts read as cp1250 ("Ľ" for "¼", "ł" for "³") and of symbol fonts read as letters ("Ř" for a Wingdings arrow bullet); corrected character by character from the source | 83,456 characters in 9,966 decisions |
| 14 | Split words, second round | the reviewed pairs joined with Hungarian spelling ("ösz-" / "szegére" → "összegére"), real hyphenated words put back on one line ("Rendőr-" / "főkapitányság") | 497 joins in 348 decisions |
| 15 | False spaces | 13 of the 15 approved pairs ("n em", "k ésedelmi", "els őfokú") and three reviewed "gatlan" places; "pont ba" and "fordulat ba" were undone, as "ba)" is a sub-point label | 112 replacements and 3 fixes in 66 decisions |
| 16 | Line starts, second round | the reviewed answers: lost first letters ("érleti" → "Bérleti"), whole words given by the reviewer ("ánya, 2006. május 25." → "Tatabánya, …" in the Tatabánya courts, "óvár" → "Mosonmagyaróvár"), split words joined to the line above ("kap" / "csolatos"), "e" / "körben" | 229 changes in 216 decisions |
| 17 | Characters, second review | the reviewer's 578 character decisions with context rules, stored control characters, separator lines, "check" characters settled by the spell checker | 82,025 decisions (47.4 million no-break spaces) |
| 18 | Quotation signs | "«" → '"' (it closes the inner quotation »…«, and "»" became '"'), "‘" → "'" (pairs with "’"), "‚" → "," ("barátját‚ majd"); first held back, as removing them would unbalance quotation marks or drop a comma | 4,162 replacements in 1,503 decisions |
| 19 | Letter-spaced words and whitespace | spaced-out headings joined when Hunspell knows the word ("I n d o k o l á s" → "Indokolás", "A  M A G Y A R   K Ö Z T Á R S A S Á G" → "A MAGYAR KÖZTÁRSASÁG"); spaces at line ends and runs of spaces and tabs collapsed | 425,992 words joined in 174,755 decisions; 15.3 million lines tidied in 224,968 decisions |
| 20 | Damaged spaced headings | what step 19 left: "I N D OKOL Á S" → "INDOKOLÁS", "I n d o k o 1 á s" → "Indokolás", "n d o k o l á s" → "Indokolás", "b ü n ö s" → "bűnös" | 2,096 headings in 1,918 decisions |
| 21 | Letterhead residue | runs of accented letters left over from anonymised letterhead words, glued to the court name on the first line ("őáÍéőá... Ítélőtábla" → "... Ítélőtábla", "íööáóVAS MEGYEI BÍRÓSÁG"); found by the character language model pilot, as every character is a valid Hungarian letter | 3,020 decisions (2,091 runs of four or more letters) |
| 22 | Page numbers and running headers | page numbers ("- 2 -", "3 / 6 oldal", bare numbers) and repeated case-number lines ("Pf.III.20.106/2013/8. szám") removed; sentences split by a page break rejoined | 22,285 page numbers and 11,650 case numbers in 4,448 decisions; 9,730 sentences rejoined |

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

## Characters, second review

The reviewer decided on 578 unusual characters (keep, replace, remove, check). Applied
with the context rules of `character_decisions` (see [the pipeline](pipeline.md)), the
decisions changed 82,025 decisions; most changes are no-break spaces turned into ordinary
spaces (47.4 million). Others:

- 2,541 control characters repaired: the publisher's RTF writer had stored Shift-JIS
  pairs as two characters ("\x81" + "˜" for "§", "\x81" + "h" for "”") and cp1252
  signs as control characters ("\x96" for "–");
- 586 decorative separator lines emptied: centred rows of one glyph from a symbol font
  ("ججججججج", "ઋઋઋઋ", "ÒÒÒÒÒ"), mostly in the Miskolc courts;
- 207 words settled by the spell checker for the "check" characters ("SZERZÔDÉS" →
  "SZERZŐDÉS", "egészségbiztosĺtási" → "egészségbiztosítási"), while Romanian, Slovak,
  Croatian and Polish names ("Bucureşti", "Pohotovosť", "Bodrožić", "Łódź") stayed;
- Cyrillic "а" was replaced only on Hungarian lines: three Debrecen decisions on entry
  refusals are bilingual, and their Ukrainian text stays.

## The most garbled files

Before these decisions were applied, the files were ranked by the share of damaged
characters (letters of other scripts, stray accents, control characters, replacement
characters); `review_hu_legal_clean/garbled_files_top50.csv` lists the 50 worst with
the cause. Only 107 files had ten or more such characters. The causes:

| Cause | Files in the top 50 |
|---|---:|
| decorative separator line drawn with a symbol font | 22 |
| Shift-JIS pairs and cp1252 signs stored as control characters by the publisher's RTF writer | 14 |
| real Ukrainian text (not damage) | 3 |
| letters lost or swapped by the anonymisation tool, which read the text as Shift-JIS | 2 |
| PDF-derived DOCX with separately stored accents ("ı" + acute) | 3 |
| "º" used as a degree sign (not damage) | 2 |
| other (Word equation in italic letters, "§" read as Arabic, UTF-8 quotes read as cp1250, OCR noise) | 4 |

The anonymisation damage is the only kind that cannot be undone from the text: the tool
treated a byte from 0xE0 up (most accented letters in cp1250) as the first half of a
Japanese character and the next byte as its second half, so "íj" became "ú‡", "ír"
became "úŹ" and some letters became the lost-letter mark "�".

## Western and symbol fonts

A review of the unusual characters against the original RTF files showed a second kind
of code-page error, this time in our own converter: it decoded every font that was not
declared as Central European with cp1250. Two kinds of font suffered:

| Font | Byte | Read as | Really | Characters corrected |
|---|---|---|---|---:|
| Western ("Times New Roman", charset 0) | 0xBD, 0xBC, 0xBE, 0xB2, 0xB3, 0xBA | ˝ Ľ ľ ˛ ł ş | ½ ¼ ¾ ² ³ º | 22,726 |
| Symbol (Greek letters, signs) | 0xB7, 0xD2, 0x6D | · Ň m | • ® μ | 50,918 |
| Wingdings and similar picture fonts | 0xD8, 0xA7, 0x76, 0x6C | Ř § v l | bullets and separators | 9,812 |

The Wingdings bullets had been especially misleading: "§" and "v" at the start of list
items looked like a section sign and a letter. They are now private-use characters
(U+F0D8 and so on), so they can be told apart and replaced in one decision. The same
review found that a Greek "μ" in "μg/ml" had turned into "ě" through the repair of
wrongly declared fonts, which now keeps a symbol next to a Latin letter.

Some odd characters are in the publisher's own files and were left alone: an
OCR-damaged DOCX ("papír alapŮ vagy elektrot)ikus"), a bullet exported as "Ø" without
its Wingdings font, and "ô" typed for "ő" in some 2002–2008 decisions.

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

Step 22 removed the page numbers and the repeated case numbers. The dashed page numbers
come mostly from the Szeged Court of Appeal (Szegedi Ítélőtábla). In review, the rule
was wrong once in 39 doubtful cases: "1/9." was a defendant's reference in a list
("1/12. L.A."), which the rule now recognises.

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

- About ten decisions keep a letterhead residue run, because the heading after it lost a
  letter too ("...áővárosi Közigazgatási") or the run is not on the first line; these need
  a person. Runs of one repeated letter ("ÉÉÉÉ tanú", "öööö") are placeholders and stay.
- Empty table rows ("| | | |"): 5,534 rows in 1,490 decisions, from flattened tables.
- "gatlan" stays "check" in the correction table: it needs a different fix per occurrence.
- False spaces were reviewed on a sample of 300 decisions; the full corpus still needs a
  run of `find-false-spaces` and a review.
- 54 soft hyphens at line ends (50 decisions) mark split words that the line-break step
  does not yet recognise.
- 22 joins were applied with a spelling the spell checker does not know (mostly typos in
  the source, e.g. "tárgyalá-" / "lon"); the word check will list them.
- Some 2012 decisions (Esztergom, Budakörnyék, Fővárosi Törvényszék) are damaged at the
  source: "búŹóság" for "bíróság", "munkadú‡" for "munkadíj" (see "The most garbled
  files"); they need a repair table or a new copy from the publisher.
- Letter-spaced runs left as they are: acronyms after an article ("a K H P") and
  decorative rows ("o o o o o"); the misspelt and broken headings were repaired in step 20. About 80 joins wrote as one word a compound that is
  normally written apart ("KÖZTÁRSASÁGNEVÉBEN" 45, "kijavítóvégzést" 8), because Hunspell
  accepts the compound and the run had no double space to mark the boundary.
- Greek symbols next to Latin letters ("μg/ml", "Δ9-THC") and the Cyrillic "Н" in "Нarketan"
  (which may stand for H or N) are left as they are.
