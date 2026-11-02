# AGENTS.md — Documentation and Readability Rules (Python)

Apply these rules to every change in this repository, in addition to task-specific
instructions.

## 1. Project settings

Review these when you create a project from this template.

- **Repository visibility:** public
- **Efficiency thresholds:** a single operation over 30 seconds or 2 GB memory on realistic data

If a setting is missing, treat the repository as **public**, use the threshold above, and say
in your summary that the setting was missing.

**Language:** English, British spelling in prose, comments, docstrings and docs.
Do not change identifiers, library APIs or established technical terms
(`color`, `initialize`, `serializer`) to British spelling.

## 2. Audience and priority

- Readers are **junior developers who know Python but may not know the libraries used**.
- **Explainability takes priority over efficiency.** Write the simplest readable solution.
- **Efficiency exception:** use a more efficient but less readable approach only if the user
  has reported a performance problem, or a measured run exceeds the thresholds in section 1.
  When you use it, write a decision record (section 6) and add a one-line comment stating why
  that cites the record's ID (e.g. `# Vectorised for speed; see ADR-2026-10-30-vectorised-fees`).
- If you suspect a performance problem but it has not been reported or measured, write the
  simple version and mention the concern in your summary.
- Do not explain standard algorithms or textbook techniques. Do explain any choice a junior
  reader could not work out from the code alone.

## 3. Code style

- Follow PEP 8. Run `ruff format` first, then `ruff check`. You may apply `ruff check --fix`
  for safe fixes; review what it changed.
- Use descriptive names (`invoice_due_date`, not `d`). Booleans read as questions (`is_active`).
- Keep functions short and focused on one task. Prefer early returns to deep nesting.
- Use named constants instead of magic numbers or strings.
- Do not use `from module import *` or bare `except:`.
- Use `logging` for diagnostics, not `print()`. `print()` is fine for output that a CLI is
  meant to show its user.
- Remove commented-out code and debug output before finishing.

## 4. Docstrings, type hints and comments

- **Type hints** are required on all public functions, methods and class attributes.
  Do not repeat types in docstrings.
- **Google-style docstrings** are required on every public module, class, function and method.
  Private helpers (`_name`) need one only if the name does not make the purpose obvious.
- **Comments explain *why*, not *what*.** Exception: where a library call is not
  self-explanatory, add a one-line comment saying what it does, the first time it appears
  in a module. Do not explain basic Python.

## 5. Business rules

**Test:** it is a business rule if the value or logic would change because the organisation's
obligations or policies changed (law, regulation, client agreement, client instruction,
internal policy). It is not a business rule if it would change because the technical
environment changed (vendor limits, infrastructure, performance), even when that environment
is governed by a contract. If unsure, treat it as a business rule and flag it in your summary.

1. Each business rule has one file in `docs/business-rules/`, named after its ID:
   `BR-<short-slug>.md` (e.g. `BR-late-fee-cap.md`), based on
   `docs/business-rules/_template.md`. Never rename an existing ID.
2. Tag the code where the rule is implemented with the ID only. Tag constants with a comment,
   and functions with an `Implements BR-<short-slug>.` line in their docstring:

   ```python
   MAX_LATE_FEE_EUR = 500.0  # BR-late-fee-cap


   def calculate_late_fee(days_overdue: int) -> float:
       """Return the late fee for an overdue invoice.

       Implements BR-late-fee-cap.
       """
   ```

   Do not explain the business reasoning in the code. That belongs in the register file.
3. Each example in a rule's file has a matching test, named after the rule
   (e.g. `test_br_late_fee_cap_large_invoice`). When you change a rule's examples, update
   its tests, and the reverse.
4. If you change a rule's logic, update its file. If a rule is withdrawn, set its status to
   `Retired`. Do not delete the file.
5. **Never invent a source or rationale.** If the task does not give it, write
   `Source: To be confirmed` and list the rule in your summary. Only the user replaces
   `To be confirmed`, with a source they have supplied.
6. If a rule seems contradictory or incomplete, **stop and ask** before implementing it.

## 6. Decision records

- Write a decision record in `docs/decisions/`, named `ADR-YYYY-MM-DD-<short-slug>.md`
  (e.g. `ADR-2026-10-30-sqlite-cache.md`) and based on `docs/decisions/_template.md`, when you:
  - use the efficiency exception;
  - add a third-party runtime dependency (development-only tools such as pytest or ruff
    do not need one);
  - choose between materially different designs (storage, structure, external services).
- If you are unsure whether a choice needs a record, ask.
- Always write new records with status `Proposed`. You may revise a record while it is
  `Proposed`. Only the user sets `Accepted`.
- When a business rule forces a technical design (e.g. a legal retention period dictates how
  data is stored), write both: the ADR's Context cites the BR ID, and the BR file does not
  describe the technical design. Business rules never depend on decision records.
- Never rewrite an accepted record. If a decision changes, write a new one and set the old
  one's status to `Superseded by <new ID>`.

## 7. Documentation (MkDocs)

- Docs are Markdown files in `docs/`, built with MkDocs (`mkdocs.yml`). Leave `nav` out of
  `mkdocs.yml` so MkDocs generates navigation from the folder structure. Do not add a `nav`
  section or edit index pages by hand.
- Keep the `_template.md` files out of the built site with `exclude_docs` in `mkdocs.yml`.
- `docs/index.md`: what the project does. `docs/getting-started.md`: install, configure and run,
  written for a junior developer.
- `README.md` stays short: a one-paragraph description, install and run steps, and a link to the docs.

## 8. Confidentiality

- Never add credentials, API keys, tokens or real personal data anywhere. Use environment
  variables for credentials and synthetic data in examples and tests.
- **Public repositories:** do not name clients or quote confidential terms. Describe sources
  generically (e.g. "Client agreement, fee provisions").
- **Private repositories:** specific sources (contract clauses, client instructions) may be cited.

## 9. Tools, tests and dependencies

- Write tests with `pytest` in `tests/`. Every new public function gets at least one test,
  and every business-rule example gets one (section 5). Tests use synthetic data only.
- Declare dependencies in `pyproject.toml`: runtime dependencies under `dependencies`,
  development-only tools (ruff, pytest, mkdocs) under a `dev` optional-dependency group.
  Keep tool settings (ruff, pytest) in `pyproject.toml` too, not in separate config files.
- Run `ruff format`, `ruff check`, `pytest` and `mkdocs build --strict` if they are available.
  If a tool is missing or fails, say so in your summary. Do not skip it silently.

## 10. Missing scaffolding

If `docs/business-rules/_template.md`, `docs/decisions/_template.md`, `mkdocs.yml` or
`docs/index.md` is missing when you need it, create it using the defaults below and
mention this in your summary.

`docs/business-rules/_template.md`:

```markdown
# BR-<short-slug>: <Title>

- **Status:** Active | Retired
- **Source:** <contract clause / regulation / client instruction / To be confirmed>

## Rule
<One or two plain-English sentences.>

## Explanation
<Why the rule exists, for a reader with no business or legal background.>

## Examples
<One or two worked examples with inputs and expected outcomes.>
```

`docs/decisions/_template.md`:

```markdown
# ADR-YYYY-MM-DD-<short-slug>: <Title>

- **Status:** Proposed | Accepted | Superseded by <ID>

## Context
<What led to the decision.>

## Decision
<What was decided.>

## Alternatives considered
<Other options and why they were rejected.>

## Consequences
<Trade-offs and anything readers should watch out for.>
```

`mkdocs.yml` (minimum):

```yaml
site_name: <Project name>
exclude_docs: |
  _template.md
```

## 11. Definition of done

"Summary" means your final message at the end of each task.

- [ ] Formatted, lint clean, tests pass
- [ ] Type hints and docstrings on public items
- [ ] Non-obvious library calls explained
- [ ] Business rules tagged; register files current; each rule example has a test
- [ ] Efficiency exception (if used) commented with its decision record's ID
- [ ] New decision records left as `Proposed`
- [ ] Docs build
- [ ] No secrets, personal data or (public repos) confidential client details
- [ ] Summary lists: unconfirmed sources, possible business rules, missing project settings,
      created scaffolding, missing tools, performance concerns
