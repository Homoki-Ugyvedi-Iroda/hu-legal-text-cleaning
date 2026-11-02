# Further analysis

Several cleaning steps produce exactly the signals that later analyses need. This page
lists where each one leads.

| Cleaning signal | Leads to |
|---|---|
| Lowercase line starts | Sentence splitting: the same signal found both lost letters and anonymisation leftovers that break sentences in the wrong place. |
| Header and footer lines inside the text | Metadata extraction: the case number, court and page number removed as noise are the metadata, and reading them from the header is more reliable than guessing them from the body. They also let you check the publisher's metadata. |
| Role labels and hyphenation exceptions ("VÁDLOTT BŰNÖS", "ítélet", "indokolás", "rendelkező rész") | Structure of decisions: these mark the sections. Each decision type (criminal or civil, first or second instance, judgment or order) has its own layout, so a section splitter can be built from these patterns. |
| Abbreviation list | Legal citations: references such as "Ptk. 6:519. §" become extractable, and the dated forms ("rPtk.", "Ptk.") tell which version of an Act a decision applies. |
| Party numbering and initials ("I.r.", "K.J.") | Party roles: who is the first, second, third defendant, consistently through a decision. |
| Anonymisation leftovers and the name filter | Named-entity recognition and anonymisation quality: the same evidence (capitals, titles, signature block) finds judges and lawyers, whose names are published, and shows where the anonymiser left traces. |
| Tables kept during conversion | Structured data such as sentences imposed, amounts and dates. |
| Error profile by year | Sampling and weighting: analyses can choose samples by quality, or leave out the most damaged years for tasks such as training data. |
| Words unknown to Hunspell | A Hungarian legal dictionary that improves later OCR checks, search and tokenisation. |

The step most of these depend on is reliable **sections and metadata**. With them,
sentence splitting, citation extraction and comparisons by decision type all work within
a known structure instead of on raw text.

## Named-entity recognition: a plan

A practical pipeline for a corpus of this size (7 GB of text):

1. A statistical named-entity recogniser over the running text (for example huSpaCy, or a
   Hungarian BERT model trained on the NerKor corpus), measured first on 1,000 decisions
   for speed and quality.
2. Judges and lawyers found by rule: signature blocks ("dr. X Y s.k. bíró"), counsel
   ("dr. X Y ügyvéd által képviselt").
3. Settlement names from the official list of Hungarian place names, including their
   suffixed forms.
4. Everything recognised in steps 2 and 3 removed from the model's output; the remaining
   list checked by hand on a review page.
