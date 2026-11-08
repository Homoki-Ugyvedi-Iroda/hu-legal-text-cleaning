# The pipeline: conversion, cleaning and normalisation

This page describes a repeatable process for Hungarian legal text collections and the
commands that carry it out.

## Terms

- **Preprocessing** is the broader term: it brings a collection, such as the texts of
  decisions, into a form that suits one particular use (everyday legal search, language
  modelling, an analysis of damages awarded). Conversion between formats, cleaning and
  normalisation are parts of it.
- **Cleaning** removes data errors, unjustified differences and missing data that would
  spoil the result: a wrong code page, symbol-font characters, damaged letters, OCR
  errors, typos already in the source. Even cleaning depends on the use: correcting the
  spelling of a quoted defendant's words is a mistake if those words must be reproduced
  exactly (see [Protected text](protected-text.md)).
- **Normalisation** goes beyond cleaning: it brings layout and writing variants into one
  canonical form. Examples are letter-spaced words ("Í T É L E T"), extra spaces, line
  breaks and tabs, NUL characters, soft hyphens, page numbers and running headers, hard
  line breaks at every line end, one set of quotation marks and Unicode NFC. Whether a
  normalisation is wanted depends on the use: a decision cited by page needs its page
  breaks and page numbers.

The *Kind* column says which of these each stage is.

## Stages

| # | Stage | Kind | Command | Output |
|---|---|---|---|---|
| 1 | Download and record source, date, file hash, format and the website's metadata | collection | (your downloader) | originals + manifest |
| 2 | Convert by format | conversion | `convert` | text tree + log |
| 3 | Wrong code page ("hatلrozat") | cleaning | `find-encoding-damage` → `repair-encoding` | file list, repaired tree + log |
| 4 | Characters: õ/û and look-alike letters; NUL, soft hyphens and NFC | cleaning; normalisation | `clean-characters`, then `review-characters` | text tree + log, overview page |
| 5 | Words split at line ends | normalisation | `find-linebreaks` → `review-page` → `apply --joins` | candidates, answers, copy |
| 6 | Lines that lost their first letter | cleaning | `find-line-starts` → `review-page` → `apply --line-starts` | candidates, answers, copy |
| 6b | Words split by a false space | cleaning | `find-false-spaces` → `review-check-rows` → `apply --corrections` | candidate pairs, answers, copy |
| 6c | Letter-spaced words, then whitespace | normalisation | library only: `spacing.join_letter_spaced`, then `spacing.normalise_whitespace` | copy + log |
| 6e | Page numbers and running case-number headers | normalisation | library only: `page_furniture.remove_page_furniture`; inventory and review pages first | patterns, answers, copy + log |
| 6f | Hard-wrapped decisions | normalisation | library only: `unwrap.unwrap_lines` | copy + log |
| 6g | Fixed-pattern leftovers: glued labels, joined compounds, link code, empty table rows | cleaning | library only: `leftovers.fix_leftovers` | copy + log |
| 7 | Word-level OCR errors and typos | cleaning | `check-words` → review → `apply --corrections`; corrections inside quoted lay writing are left out and listed (see [Protected text](protected-text.md)) | word list, correction table, copy, list of corrections left out |
| 8 | Abbreviations, so that a dot after them is not taken for a sentence end | preprocessing for sentence splitting | `audit-abbreviations` → review | abbreviation list |

### Stage 2: conversion

- **RTF:** the code page is chosen per font. A font declared as Central European
  (charset 238) is decoded as cp1250 even when the document declares cp1252. A Western
  font (charset 0, e.g. "Times New Roman" without "CE") is cp1252 even in a Hungarian
  document: read as cp1250, its "¼", "³" and "º" became "Ľ", "ł" and "ş". Fonts with
  charset 128 are Shift-JIS: in more than 600 BHGY decisions "§" and the one-character
  "…" used for anonymisation are stored in such a font.
- **Symbol fonts** draw their own picture for each byte, so the font name decides:
  "Symbol" is mapped to Unicode (Greek letters, "®", "°", "•"); Wingdings, Webdings
  and similar picture fonts get the private-use code U+F0hh, as Word itself does, so a
  Wingdings arrow used as a bullet no longer reads as "Ř". OpenOffice's StarSymbol and
  OpenSymbol declare the symbol charset but use ordinary cp1252 signs at these bytes.
- **Bytes stored as Unicode:** some RTF writers wrote a byte as a Unicode code point:
  `\u150` for the cp1252 en dash, and Shift-JIS pairs as `\u129` + a character
  (`\u129\u732` is "§", `\u129` + "h" is "”"). These go back among the text bytes.
- **Wrongly declared fonts:** if a font of another script (Arabic, Shift-JIS, Greek,
  Cyrillic, ...) produces words that mix that script with Latin letters, the font was
  declared by mistake, and that stretch of text is decoded with the document's own code
  page instead. Real Greek or Japanese text keeps its font's code page.
- **Control words glued to text:** the publisher's original conversion program sometimes
  left out the space that ends a control word, as in `\tabDr.`, `\qjBudapest` or
  `\tab981 092 Ft` (`\qj` sets justified alignment). This affects 28% of BHGY decisions,
  though Word and other programs do not show it. Read by the rules,
  `\tabDr` is one unknown control word, and "Dr" (or "981") would be lost with the tab.
  Control words that precede text and never take a number (`\tab`, `\par`, `\pard`,
  `\cell`, `\qj`, ...) are split off such a run; real longer words such as `\pararsid` and
  `\cellx` with their number are kept.
- **DOCX:** only the body (`word/document.xml`) is read; headers, footers, footnotes and
  text boxes are left out, because in decisions they hold case and page numbers. Tabs are
  written both as `<w:tab/>` and as `<w:tab />`; both become a tab.
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

- NUL characters (padding at the end of the source files, in nearly 5% of BHGY
  decisions) are removed.
- Soft hyphens (U+00AD, invisible "hyphenate here" marks) are removed: inside a word
  ("in" + soft hyphen + "gatlan") they make whole-word searches and the spell checker see
  two words. A soft hyphen at a line end is kept: it marks a split word for stage 5.
- Control characters U+0080 to U+009F, left by the stored bytes above in texts converted
  by other tools, are turned back into "§", "”", "–" and so on; the leftovers of UTF-8
  quotation marks read as cp1250 ("„€ž") are removed.
- Unicode NFC joins a letter and a separately stored accent into one character; a
  dotless "ı" with an accent (from PDF conversions) becomes "í".
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
- The exported decisions are applied with `character_decisions.apply_character_decisions`,
  which adds context rules: "remove" on a space variant gives an ordinary space; a
  Cyrillic or Greek look-alike is replaced only on a line without other letters of that
  script (Ukrainian text stays); a fraction replacing a letter ("Ľ" → "1/4") is used
  only apart from letters; a line of one repeated symbol (a decorative separator drawn
  with a symbol font) is emptied. Characters marked "check" are settled word by word:
  a candidate letter is used only if exactly one candidate makes an unknown word known
  to the spell checker ("egészségbiztosĺtási" → "egészségbiztosítási").
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

On a whole corpus the candidate list is too long to review pair by pair (9,577 pairs in
BHGY), so the real splits are picked out first. A pair is kept when the joined word is
common in the corpus, written correctly at least ten times as often as the split form and
at least 20 times: a split of a common word ("magy ar", "s zámú") passes, while two real
words that Hunspell does not know ("euro alapú", "a domain", "néhai id.") do not, because
their joined form hardly exists. The families a person kept apart stay out: compounds the
source writes apart ("mikro vállalkozás", "három féle"), a bare suffix as first piece (part
of a word cut in three), initials before a suffix. `join_false_spaces` then removes the
space, keeping the letters as written ("MAGY AR" -> "MAGYAR"). It never joins after a digit
or hyphen ("PN10-es és"), before a closing bracket ("pont ba)"), across a line end, or an
abbreviation in capitals before a lowercase word ("AB a"), and it leaves quoted lay writing
as written.

### Stage 6c: letter-spaced words and whitespace

Headings are often spaced out letter by letter ("I n d o k o l á s", "í t é l e t e t",
"b ű n ö s"). `join_letter_spaced` reads such a phrase as pieces separated by two or more
spaces and joins a piece only if Hunspell knows the result, so initials and decorative rows
("o o o o o", "A x M x S") stay. Neighbouring pieces are merged when the merged word is
known ("í t é l  e t e t" → "ítéletet"), but two pieces that are words on their own are
merged only if the merged form is common unspaced in the corpus: Hunspell also accepts
compounds of words written apart on purpose ("kijavító végzést", "Köztársaság nevében").
An unknown piece gets three more tries: a split before capitals ("M a g y a r K ö z t á r s
a s á g" → "Magyar Köztársaság", each part at least three letters), "Í" for a leading "I"
("I t é l e t e t" → "Ítéletet") and the article split off the end ("K ö t e l e z i a
felperest"). The space before punctuation after a joined word goes too ("Indokolás :" →
"Indokolás:"). As with the other dictionary steps, the candidate forms are collected first
and Hunspell is asked once; a few frequent legal words Hunspell lacks ("ellenkérelmében",
"védiratában") are accepted by their corpus count.

`repair_spaced_headings` then handles what the join leaves at the start of a line: irregular
gaps ("I N D OKOL Á S"), OCR confusions ("I n d o k o 1 á s"), a lost letter
("n d o k o l á s") and "ü"/"ö" for "ű"/"ő" ("b ü n ö s"). The run is compared with a short
list of heading words after folding those confusions, and replaced only on a match or
when exactly one heading is one letter away; an extra letter at the end is not counted,
as it is usually a numeral ("Indokolás I."). `repair_spaced_guilty` writes a spaced
"b ü n ö s" as "bűnös" anywhere in a line.

`normalise_whitespace` then removes spaces at the start and end of lines and collapses
runs of spaces and tabs, keeping blank lines and CRLF line endings. It must run after the
join, because the double space is the only sign of a word boundary in a spaced phrase.

### Stage 6d: letterhead residue

Some decisions start with a run of accented letters glued to the court name:
"őáÍéőá... Ítélőtábla", "ááíóá... Járásbíróság", "íööáóVAS MEGYEI BÍRÓSÁG". The run holds
exactly the accented letters of the letterhead words that were anonymised ("Fővárosi
Ítélőtábla" gives ő, á, Í, é, ő, á). The RTF contains them as visible text, so the
converter is not at fault; the tool that removed the words kept their accented characters.
`remove_letterhead_residue` deletes such a run from the first non-empty line. It keeps one
letter repeated four or more times ("ÉÉÉÉ tanú", an anonymisation placeholder), a run
followed by a small letter (the heading itself is damaged: "...áővárosi") and up to three
capitals before a capital ("ÍTÉLET").

### Stage 6e: page numbers and running headers

Converted decisions keep page numbers between paragraphs ("- 2 -", "3 / 6 oldal", a bare
"4") and the case number repeated at the top of every page. `remove_page_furniture`
removes page numbers in those forms, and a case-number line when it repeats an earlier
line of the file, as the first occurrence is the decision's own heading. Everything else
stays even if it repeats: court names, headings, role words, statute lines and separator
lines of several dashes ("--- 0 ---"). "x/y" counts as a page only when x is not larger
than y ("023/6" is a parcel number), and an "x/y." line next to lines that start with the
same kind of reference ("1/12. L.A.") is a list item.

Where the removed line stood inside a sentence (the kept line before has no sentence end
and the kept line after starts in lowercase, but not with a list marker such as "b)"), the
two halves are joined. This test turned out to be reliable in review.

How the rules were found: an inventory grouped every page-marker line and every line
repeated within a file into patterns (digits shown as #), with the share of files where
the numbers rise, the median gap between markers, the share of lines that interrupt a
sentence and whether the first occurrence is at the top of the file. A person decided
the first two dozen patterns; the rule they showed (remove case numbers and page
numbers, keep everything else) settled the rest, and only removals that nothing in the
file confirmed (a bare number outside the file's page numbering, a rejoin after a short
line) went to a second review.

### Stage 6f: hard-wrapped decisions

A few decisions were wrapped at a fixed width of about 90-115 characters, so that their
sentences run over several lines. `unwrap_lines` first decides whether a file is wrapped
throughout: at least ten lines (and a tenth of all lines) end mid-sentence and continue in
lowercase, and at most a tenth of the lines are more than 1.3 times the wrap width (in a
file with one paragraph per line, many lines are much longer). The wrap width is the
median length of the lines that continue in lowercase.

In such a file a line is joined to the next when it does not end a sentence and the next
line follows directly, and either the next line starts in lowercase and the line is at
least half the wrap width, or the next line starts with a capital (a name carried over)
and the line is at least 0.8 of the width. A line that ends a sentence is never joined,
because the next line may start a new paragraph. Headings ("ítéletet:"), verdict words
("bűnös"), list items, signature lines, lines in capitals and table rows stay on their
own. Placeholders ("tanú16"), point references ("b) pontja", "h) pont]") and units
("km/h") are words of the sentence, not layout, inside running text.

Mid-sentence line breaks also occur in ordinary files, about 2% of line pairs, but there
they are nearly always deliberate layout: headings ("meghozta a következő" / "ítéletet:"),
the operative part ("vádlott" / "bűnös"), party blocks and signatures. These are kept;
a sentence splitter, as a later preprocessing step, can join the few real wraps among them.

How it was measured: a first count of files with more than 20% mid-sentence breaks
suggested that a fifth of the corpus was hard-wrapped, but the share was taken over
adjacent line pairs only, and in files with blank lines between paragraphs the few
adjacent pairs are mostly signature blocks. Counting only breaks that the line-kind rules
(`line_kinds`) would join, over all text lines, and adding the long-line test, left 201
decisions (0.09%).

### Stage 6g: fixed-pattern leftovers

`fix_leftovers` handles a few fixed patterns that the earlier steps did not cover:

- A party or defendant label glued to the word before it ("vádlott neveI. r. vádlott",
  "ésII.rendű") gets a space before the roman numeral. Only after a word the spell checker
  knows, and a word of at least three letters or a common short word ("a", "az", "és"):
  otherwise the anonymiser wrote the label into the middle of a word ("terjeI. rendű
  alperesi érdekelttt elő" for "terjesztett elő"), which a space would not repair, and
  Hunspell accepts every single letter. "Il" or "Xl" before the label is a roman numeral
  with "l" misread for "I" and is left alone.
- Compounds written as one word by the letter-spacing step are split again
  ("KÖZTÁRSASÁGNEVÉBEN", "kijavítóvégzést").
- Link code left by a legal database (`<cdp://…>`, `<javascript:LinkUgrik(…)>`) is removed,
  even when the tag is broken over two lines.
- Empty rows of a flattened table ("| | |") are removed.
- "�h" after a word is a closing quotation mark in a wrong code page and becomes "”".

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
