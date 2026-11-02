# ADR-2026-11-02-text-level-encoding-repair: Repair wrong code pages on the text, not only in the RTF reader

- **Status:** Accepted

## Context
Some BHGY decisions were full of words such as "hatلrozat" and "bيrَsلg". The RTF files
declare one of their fonts as Arabic (`\fcharset178`, "Times New Roman"), but the text
written in that font is Hungarian in the Central European code page (cp1250). The RTF
reader follows the font's declaration, as the RTF specification says, so every accented
letter in that font became an Arabic letter. Other collections may have the same fault in
files that are already plain text, and the RTF source is not always available.

## Decision
Handle it at two levels.

1. **In the RTF reader:** a stretch of text in a font of another script is decoded with
   that script's code page as before, but if the result has words in which a letter of
   that script stands next to a Latin letter, the stretch is decoded with the document's
   own code page instead. This is lossless, because it works on the original bytes.
2. **On the text** (`hu_legal_cleaning.encoding_repair`), for damage carried inside the
   source as Unicode and for collections that arrive as plain text:
   - a word in which a letter of another script stands directly next to a Latin letter
     is damaged;
   - the code page that explains most damaged words of a document is found by trying
     each candidate (Arabic, Hebrew, Greek, Cyrillic, Thai, Shift-JIS, GBK);
   - each foreign character is turned back into bytes with that code page and decoded
     with cp1250; a repair is kept only if it gives a Hungarian accented letter (plus,
     for two-byte code pages, the ASCII letter that followed it);
   - a document is repaired only if it has at least 3 damaged words and the chosen code
     page explains at least 80% of them.

The RTF reader also runs the text repair on its output. `find-encoding-damage` and
`repair-encoding` run it on any folder of text files.

## Alternatives considered
- **Ignore non-Latin font charsets in the RTF reader:** simpler, but it would break real
  Greek or Cyrillic text in the rare decisions that quote it, and it does not help with
  collections that arrive as plain text.
- **A general encoding detector (such as charset-normalizer):** it guesses the code page
  of a whole file from its bytes. Here the file is valid and only some runs of text are
  wrong, so a whole-file guess does not help; it would also be a runtime dependency.

## Consequences
- Correct Greek or Cyrillic words stay unchanged, because they do not mix scripts, and a
  single odd word does not trigger a repair. Greek symbols written next to Latin letters
  ("μg/ml") are listed as damaged but not repaired, since "μ" read as cp1250 is not a
  Hungarian letter.
- The text repair cannot bring back letters that a decoder had already replaced with
  "?" or "�"; for those, convert the source again.
- "Ű" in the Arabic code page is a punctuation mark ("؛"), so the repair also re-reads
  punctuation of the foreign script inside a damaged word.
- Latin code pages (cp1252, cp1254) are not covered here: they turn ő/ű into õ/û, which
  `clean-characters` repairs.
