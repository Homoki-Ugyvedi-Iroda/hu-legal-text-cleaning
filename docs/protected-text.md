# Protected text: what word corrections must leave alone

Cleaning can do harm. A correction table that turns "igy" into "így" improves court prose,
but a decision may also quote a text message, an e-mail or a letter word for word, with
the writer's own spelling. There the misspelling is part of the evidence, and "correcting"
it changes what the decision says. When you decide what to clean and how, weigh this harm
against the gain.

## What counts as protected

| Kind | Example | How the package handles it |
|---|---|---|
| Anonymisation placeholders | "tanu1", "Tanu_2" next to "tanú1" | never changed: a word touching a digit or underscore is not a whole word (`corrections.correction_pattern`) |
| Verbatim lay writing in quotation marks | „igy irtad nekem tegnap hogy nemjossz haza” | left out by `apply --corrections` and listed for review (below) |
| Lay writing quoted without quotation marks | a message copied into the reasoning as its own paragraph | not detected yet; check the decisions a reviewer knows about |
| Quoted errors, titles, old spelling | "a szerződés »kölcsön« szava", 19th-century text | partly caught by the rare-word test; otherwise by hand |

Making the text uniform is not always cleaning. If a source writes both "tanu1" and
"tanú1" in the same decision, choosing one form loses the information that the source
mixed them. Keep the source's form unless you have a reason to change it.

## How lay quotations are found

`protected_text.protected_quotes` looks at every quotation („…”, or "…" on one line;
a „ without its closing mark runs to the end of the paragraph). A quotation is protected
when at least 10% of its lowercase words of four or more letters occur at most twice in
the whole corpus. Lay writing typed without accents or with typing errors is full of such
rare forms; court prose quoted from another decision is not. Quotations of fewer than
five such words are too short to judge and are not protected.

A word before the quotation that names a message or letter ("sms", "üzenet", "e-mail",
"levél", "írta" …) is reported in the log to help the reviewer, but does not decide.

**Measured on 225,401 court decisions:** the correction table made 46,173 replacements;
727 fell inside quotation marks, and a person marked 24 of those as verbatim lay writing
or quoted errors to be undone. The rare-word test leaves out 105 of the 727
replacements, including all 24. Requiring a naming word as well would have protected
only 15 of the 24, so it is not used.

The rare-word counts only make sense on a large corpus (thousands of documents). On a
small one almost every word is rare, so almost every quotation is protected: the safe
side, but run with `--correct-quotes` if you have checked the quotations yourself.

## Running it

`hu-legal-clean apply SOURCE TARGET --corrections` leaves corrections out inside
protected quotations and writes them to `<log name>_protected_quotes.csv` (file, word,
correction left out, share of rare words, naming word, context). A person reads that list;
anything that is court prose after all can be corrected by hand or by running again with
`--correct-quotes`. Finding the quotations reads the corpus twice before the copy is
written.
