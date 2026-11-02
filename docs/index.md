# Hungarian legal text cleaning

This project cleans the text of Hungarian court decisions so that they can be searched,
counted and analysed reliably. It grew out of cleaning the about 225,000 decisions of the
Collection of Court Decisions (Bírósági Határozatok Gyűjteménye, BHGY), but the tools and
word lists work for any Hungarian legal corpus: decisions of courts and authorities,
published contracts, statutes.

## What it does

| Step | What it fixes | Module |
|---|---|---|
| Convert | RTF and DOCX to plain text, keeping table cells, Central European code pages and anonymisation symbols | `convert` |
| Clean characters | NUL padding, Unicode NFC, õ/û written for ő/ű | `normalise` |
| Line breaks | words split by a hyphen at a line end ("sze-" / "rint") | `linebreaks` |
| Line starts | lines that lost their first letter ("értett" for "Sértett") | `line_starts` |
| Word check | OCR damage and typos, after filtering names, abbreviations and anonymisation leftovers | `dictionary`, `hunspell`, `corrections` |
| Abbreviations | measures which dotted words are abbreviations in your corpus | `abbreviations` |
| Sentences | rule-based sentence splitter for court decisions | `sentences`, `evaluation` |
| Review | keyboard-driven review pages for every list of candidates | `review_page` |

Every step that changes text writes a copy and a log; the original files are never
changed. Automatic rules only propose changes; a person approves them on a review page
before they are applied. See [the pipeline](pipeline.md).

## What is included besides code

Word lists built from the BHGY decisions and reviewed by a person, see
[word lists](word-lists.md):

- a correction table of OCR errors and typos, rated safe / check / no;
- the words Hunspell does not know but that are correct in legal texts, by category;
- abbreviations found in court decisions, legal and general, with their meaning;
- the reviewed fixes for damaged line starts and for words split across lines;
- a gold set of 40 passages for testing sentence splitters.

What the cleaning found in BHGY, year by year, is in [BHGY findings](bhgy-findings.md).
Where the cleaning leads next is in [further analysis](further-analysis.md).
