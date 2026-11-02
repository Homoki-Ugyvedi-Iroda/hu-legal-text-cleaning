# The cleaning pipeline

This page describes a repeatable cleaning process for Hungarian legal text collections
and the commands that carry it out.

## Principles

1. **Never change the originals.** Every stage reads one folder and writes a new one.
2. **Dry run, review, then apply.** Rules produce candidate lists; a person checks them
   on a review page (with the context and a link to the original document); only the
   approved decisions are applied.
3. **Log every change.** Each stage writes a CSV log, so a change can be traced back and
   the whole run repeated.
4. **Measure by year, court and format.** Errors cluster by period and by the tool a
   court used. In BHGY, OCR damage and line-start losses are concentrated in particular
   years (see [BHGY findings](bhgy-findings.md)).
5. **Flag rather than delete.** A document with damage stays in the corpus with a flag;
   whether to leave it out is the decision of each analysis.

## Stages

| # | Stage | Command | Output |
|---|---|---|---|
| 1 | Download and record source, date, file hash, format and the website's metadata | (your downloader) | originals + manifest |
| 2 | Convert by format | `convert` | text tree + log |
| 3 | Wrong code page ("hatلrozat") | `find-encoding-damage` → `repair-encoding` | file list, repaired tree + log |
| 4 | Characters: NUL, soft hyphens, NFC, õ/û, look-alike letters | `clean-characters`, then `review-characters` | text tree + log, overview page |
| 5 | Words split at line ends | `find-linebreaks` → `review-page` → `apply --joins` | candidates, answers, copy |
| 6 | Lines that lost their first letter | `find-line-starts` → `review-page` → `apply --line-starts` | candidates, answers, copy |
| 6b | Words split by a false space | `find-false-spaces` → `review-check-rows` → `apply --corrections` | candidate pairs, answers, copy |
| 7 | Word-level OCR errors | `check-words` → review → `apply --corrections` | word list, correction table, copy |
| 8 | Abbreviations for sentence splitting | `audit-abbreviations` → review | abbreviation list |
| 9 | Sentences | `split`, `evaluate-splitter` | segments with flags |
| 10 | Quality report and versioning | (your own) | error rates by period, version number |

### Stage 2: conversion

- **RTF:** the code page is chosen per font. A font declared as Central European
  (charset 238) is decoded as cp1250 even when the document declares cp1252. A Western
  font (charset 0, e.g. "Times New Roman" without "CE") is cp1252 even in a Hungarian
  document: read as cp1250, its "¼", "³" and "º" became "Ľ", "ł" and "ş". Fonts with
  charset 128 are Shift-JIS: some anonymisation tools wrote "…" and "§" in such a font.
- **Symbol fonts** draw their own picture for each byte, so the font name decides:
  "Symbol" is mapped to Unicode (Greek letters, "®", "°", "•"); Wingdings, Webdings
  and similar picture fonts get the private-use code U+F0hh, as Word itself does, so a
  Wingdings arrow used as a bullet no longer reads as "Ř". OpenOffice's StarSymbol and
  OpenSymbol declare the symbol charset but use ordinary cp1252 signs at these bytes.
- **Wrongly declared fonts:** if a font of another script (Arabic, Shift-JIS, Greek,
  Cyrillic, ...) produces words that mix that script with Latin letters, the font was
  declared by mistake, and that stretch of text is decoded with the document's own code
  page instead. Real Greek or Japanese text keeps its font's code page.
- **DOCX:** only the body (`word/document.xml`) is read; headers, footers, footnotes and
  text boxes are left out, because in decisions they hold case and page numbers.
- **Tables** become lines of cells separated by " | ".
- **PDF** is not handled here: first check whether the text layer is usable, and only
  run OCR where it is not.
- Compare the number of converted files with the number of source files.

### Stage 3: wrong code page

Old Windows documents store an accented letter as one byte, and the code page says which
letter that byte is. If part of a document declares the wrong code page, Hungarian
letters turn into letters of another script: in BHGY, some RTF files declare an Arabic
font for Hungarian text, so "határozat" became "hatلrozat" and "bíróság" became
"bيrَsلg".

- **Find:** `find-encoding-damage` lists every file with words in which a letter of
  another script stands directly next to a Latin letter, the code page that explains
  them and a few examples. Greek letters used as symbols ("Δ9-THC", "α-PVP") stand apart
  from Latin letters and are not counted; "μg/ml" is listed but not repaired.
- **Variants seen in BHGY:** Arabic (cp1256, "hatلrozat"), Greek (cp1253), Shift-JIS
  (cp932, "bekezd駸" for "bekezdés"), Chinese GBK carried inside the RTF as Unicode
  ("K鷕ia" for "Kúria"), and the Shift-JIS "§" read as Arabic ("پک-ban" for "§-ban").
- **Repair:** `repair-encoding` turns the foreign characters back into bytes with that
  code page and reads them as cp1250. A character is replaced only if it gives a
  Hungarian accented letter, and a document is repaired only if it has at least three
  damaged words and one code page explains at least 80% of them.
- **Prefer re-conversion when the source exists.** When a decoder replaced bytes it
  could not read (e.g. Shift-JIS), the letters are gone from the text and only a new
  conversion from the RTF brings them back.
  `--only-changed` writes just the repaired files, for a check before they replace
  files in an existing copy. "Ã¡"-style text (UTF-8 read as cp1252) is repaired too.
- The RTF reader of stage 2 runs the same repair, so new conversions are already clean;
  the separate step is for text collections converted by other tools.
- **Why here:** before the character step, and before any step that counts words.
  Damaged words look like OCR errors to the spell checker, like split words to the
  line-break step and like lost letters to the line-start step ("elk" from
  "elkِvetés"), so leaving them in fills every later review with false candidates.

See [ADR-2026-11-02-text-level-encoding-repair](decisions/ADR-2026-11-02-text-level-encoding-repair.md).

### Stage 4: characters

- NUL characters (padding at the end of many converted files) are removed.
- Soft hyphens (U+00AD, invisible "hyphenate here" marks) are removed: inside a word
  ("in" + soft hyphen + "gatlan") they make whole-word searches and the spell checker see
  two words. A soft hyphen at a line end is kept: it marks a split word for stage 5.
- Unicode NFC joins a letter and a separately stored accent into one character.
  Marks without a composed form (strike-through, a doubled acute on a letter that has no
  such form) remain and are counted in the log.
- õ and û, which do not exist in Hungarian, are replaced with ő and ű.
- Cyrillic and Greek letters that look like a Latin letter and stand inside a Latin word
  ("ЕU" with a Cyrillic Е, "Citroёn") are replaced by the Latin letter. Cyrillic words,
  Greek symbols ("μg", "Δ9-THC") and the ambiguous Cyrillic "Н" are left alone.
- `review-characters` builds a page with every character that is neither ASCII nor a
  Hungarian letter: its count, a few examples in context and a decision (keep, replace,
  remove, check) with a note. It is the check that no damage was left in the character
  clean-up. With `--originals` the examples link to the original RTF or DOCX, where the
  reviewer can see how the character really looks; that comparison is what showed the
  Western and symbol font errors of stage 2.
- Not repaired automatically: ő and ű stored as a dotless ı (seen in PDF text layers of a
  competition authority), because ı may stand for either letter; this needs a dictionary
  decision per word.

### Stage 5: words split at line ends

The spell checker decides per pair: if the joined form is a word, join; if both halves
are words, it is a real hyphenated compound ("magánokirat-hamisítás"), keep the hyphen;
otherwise a person decides. Two patterns are held back from automatic joining:

- spelled-out numbers, which have their own hyphenation rules;
- a role word at the end of a line followed by a verdict or a one-letter label on the
  next line ("vádlott-" / "bűnös"), which is a typographical convention.

Pairs with a blank line between the two halves are not joined automatically: the blank
line may be a real paragraph break. A pair a person confirmed as a split word is joined
across blank lines too, because a word cannot continue after a new paragraph.

**Spelling of the joined word.** Putting the two halves together is not always enough:

- a long two-letter consonant is split as two whole digraphs but written with one
  doubled letter: "ösz-" / "szeg" → "összeg", "személy-" / "lyel" → "személlyel";
- some hyphens must stay: the question particle ("megfelelnek-e"), a suffix after an
  abbreviation ("Ft-ban", "ÁSZF-ben") and compounds of more than six syllables
  ("ingatlan-nyilvántartás"); the spell checker knows these rules, so it decides between
  the plain and the hyphenated form;
- spelled-out numbers above two thousand take a hyphen after each group word
  ("hetvenháromezer-nyolcszáz"), others are one word ("négymillió").

A pair whose hyphen is right but whose line break is not ("Rendőr-" / "főkapitányság",
"Ft-" / "ot", "állag-" / "és") is joined keeping the hyphen. Layout breaks stay: a role
word or placeholder before a verdict ("vádlott-" / "bűnös", "XX-" / "bűnös"), a header
("alperes ellen-" / "közigazgatási ügyben") and dashes ("tényre-" / "bizonyítékra").

### Stage 6: lost first letters

A lowercase line-start word is a candidate if a word one to three letters longer at the
front (or a two-character Hungarian letter such as "sz" or "gy") starts at least 200
lines in capitalised form and is at least three times as frequent. Only lines that
follow a finished sentence (the line above ends in `. ! ? : ;` or is blank) are counted:
a line that continues the sentence above ("…, amely" / "mellett az …") is a normal wrap.
The remaining false candidates usually follow a page or paragraph break and are removed
in the review.

The review also finds line-start words that did not lose a letter but are the second
half of a word split at the line above, often without a hyphen ("sze" / "rint"). They
get the decision `join`: `join_line_start` puts them back on the previous non-empty
line when the spell checker knows the joined word. When the reviewer gives a whole word
("óvár" → "Mosonmagyaróvár"), the lines are joined if the line above ends with the
missing part, and the word is replaced otherwise.

### Stage 6b: false spaces

A false space splits one word into two pieces ("els ő" for "első", "k ésedelmi"). The finder
reads the neighbouring words of every line: a pair is a candidate if Hunspell does not
know one of the pieces but knows the pieces joined. Pairs of two real words are never
listed, letter-spaced lines ("k e r ü l e t") are skipped, and a first piece that follows a
digit, hyphen or slash is ignored, because it is usually a suffix ("2010-ig a"). The pairs
are counted, so a person decides once per pair; approved pairs are added to the correction
table, which `apply --corrections` already applies. On a sample of 300 files the finder
takes about 20 seconds and lists about 33 pairs; roughly two thirds are real splits, the rest
are foreign words ("euro alapú") and need a "keep" decision.

### Stage 7: word-level errors

Hunspell flags far more than errors in legal text. Before review, the word check sorts
unknown words into kinds: anonymisation leftovers, names (by their capitalisation, their
neighbours, a title before them, or their position in the signature block),
abbreviations and suffix fragments, probable mistakes (close to a much more frequent
known word) and unsure words. Only a reviewed correction table is applied, never
Hunspell's suggestions directly. Rows rated "check" need a look at each occurrence
before use: `review-check-rows` builds a page with examples spread over the years, each
with ten lines before and after, a decision per occurrence (fix, keep, unsure), a
decision for the word and comment boxes. A word whose examples are all "fix" and that
cannot be a correct word becomes "yes"; a word with mixed examples stays "check" with a
note, and is never applied automatically.

## Hungarian specifics to plan for

- Anonymisation placeholders differ by publisher and period ("név9", "neve", "x felperes",
  "(....)", initials such as "K.J.").
- Statute abbreviations change over time ("Ptk." before and after 2014, "rPtk.").
- Role labels and verdicts are written in capitals or letter-spaced ("b ű n ö s").
- Dates and case numbers contain dots ("2015. évi", "Pf.20.123/2015/5."), which mislead
  generic sentence splitters.
