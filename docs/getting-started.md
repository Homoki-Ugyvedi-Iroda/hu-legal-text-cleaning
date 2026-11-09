# Getting started

## Requirements

- Python 3.12 or later
- Git
- For the word check and the line-break check: the Hunspell spell checker with the
  Hungarian dictionary. On Linux or macOS install `hunspell` and `hunspell-hu`
  (Debian/Ubuntu: `sudo apt install hunspell hunspell-hu`). On Windows install it inside
  WSL (Windows Subsystem for Linux) with the same command; the package finds it there.

No other program and no third-party Python package is needed at run time.

## Install

Clone the repository, then create a virtual environment so the project's packages
stay separate from other projects:

```bash
python -m venv .venv
```

Activate it. On Windows:

```bash
.venv\Scripts\activate
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install the project together with the development tools:

```bash
pip install -e ".[dev]"
```

The `-e` flag installs the project in editable mode, so your code changes take effect
without reinstalling. The install also creates the `hu-legal-clean` command.

## Configure

Nothing to configure: there are no credentials or environment variables. Every command
takes its input and output folders as arguments.

## Run

Each step is a sub-command. `hu-legal-clean --help` lists them;
`hu-legal-clean <step> --help` explains the arguments. A small example:

```bash
hu-legal-clean convert originals/ text/ --log convert_log.csv
hu-legal-clean find-encoding-damage text/ encoding_damage.csv
hu-legal-clean repair-encoding text/ text_repaired/ --log encoding_log.csv
hu-legal-clean clean-characters text_repaired/ text_clean/ --log characters_log.csv
hu-legal-clean find-line-starts text_clean/ line_start_candidates.csv
hu-legal-clean review-page line_start_candidates.csv text_clean/ line_starts.html
```

Open `line_starts.html` in a browser, answer with the number keys, export the answers,
and pass the approved list to `apply`. The full order is in [the pipeline](pipeline.md).

## Check your work

The same checks run automatically on GitHub for every push and pull request (see
`.github/workflows/checks.yml`).

```bash
python -m ruff format
python -m ruff check
python -m pytest
```

Every tool is run with `python -m` so that it uses the Python of the active virtual
environment, where the project is installed. The tests also check that every link between
the Markdown files points to a file that exists.
