# ADR-2026-11-01-own-rtf-docx-reader: Own RTF and DOCX reader instead of pandoc

- **Status:** Accepted

## Context
The BHGY decisions are published as RTF (older years) and DOCX files. A test on 101 files
compared pandoc's plain-text output with the source documents. Pandoc lost the text of
table cells (empty `||` rows) and turned ő/ű into õ/û in most RTF files, because those
files declare the Western European code page but use Central European fonts. It was also
about 30 times slower (about 130 ms against 4 ms per file). Some anonymisation tools also
wrote "…" and "§" in a Japanese (Shift-JIS) font, which generic readers turn into
replacement characters.

## Decision
Read RTF and DOCX with a small reader written with the Python standard library only
(`hu_legal_cleaning.convert`). The RTF reader chooses the code page per font, skips
headers, footers, footnotes and pictures, and keeps RTF special characters. The DOCX
reader reads only `word/document.xml`.

## Alternatives considered
- **pandoc:** loses table cells and accents on this corpus (see above), and is an
  external program to install.
- **LibreOffice in headless mode:** handles the formats well but is a large external
  dependency and slow for hundreds of thousands of files.
- **python-docx and striprtf:** two third-party dependencies; striprtf does not choose
  code pages per font.

## Consequences
- No runtime dependency; the reader is easy to fix when a new kind of file appears.
- The reader covers what court decisions use, not the whole RTF specification. Unusual
  documents (embedded objects, fields with visible results) may lose text: check the
  conversion log for empty files and replacement characters.
- On 300 randomly chosen BHGY files the packaged reader gave exactly the same text as the
  original conversion script.
