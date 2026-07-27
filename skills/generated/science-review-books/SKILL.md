---
name: science-review-books
description: "Review and summarize a book chapter-by-chapter, then synthesize a whole-book overview."
user-invocable: true
---

# Review Books

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the relevant generated methodology router skills (e.g. `science-literature`, `science-literature`, `science-epistemics`).
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. the `science-command-preamble` skill's `references/aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under the `science-command-preamble` skill's `references/aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `references/templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Verify the project-local Science CLI:** Execute the top-level CLI
   Compatibility Gate below before the command's first Science invocation. It
   uses the consumer's frozen lock; do not route through a toolkit checkout or
   another environment.

## CLI Compatibility Gate

```bash
SCIENCE_REQUIRED_VERSION=0.3.0
if output=$(uv run --frozen science --version 2>&1); then
  SCIENCE_INSTALLED_VERSION=${output##* }
elif uv run --frozen science --help >/dev/null 2>&1; then
  # The CLI runs but has no --version option, so it predates the baseline.
  # Decided by behavior, never by matching Click's version-dependent wording.
  SCIENCE_INSTALLED_VERSION=
else
  # The CLI cannot run at all: missing/stale lock, Git fetch failure, import
  # error. Report the real diagnosis; never advise moving the Science pin.
  printf '%s\n' "$output" >&2
  exit 1
fi

if ! SCIENCE_INSTALLED_VERSION="$SCIENCE_INSTALLED_VERSION" \
     SCIENCE_REQUIRED_VERSION="$SCIENCE_REQUIRED_VERSION" \
     uv run --no-project python - <<'PY'
import os
import re
import sys

def release(name: str) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None

installed = release(os.environ["SCIENCE_INSTALLED_VERSION"])
required = release(os.environ["SCIENCE_REQUIRED_VERSION"])
sys.exit(0 if installed is not None and required is not None and installed >= required else 1)
PY
then
  display=${SCIENCE_INSTALLED_VERSION:-unknown-or-pre-0.3.0}
  echo "This Science agent command requires science >=$SCIENCE_REQUIRED_VERSION; found $display." >&2
  echo "upgrade with: uv lock --upgrade-package science && uv sync --frozen" >&2
  exit 1
fi
```

After the gate succeeds, run the command through the consumer's project-local
environment as `uv run science <command>`. Missing dependency, missing or stale
lock, and Git fetch failures are surfaced directly and must be fixed in the
consumer project.

A CLI that answers `--help` but rejects `--version` predates the baseline;
malformed successful output and a version below the floor are likewise
compatibility failures, and all three stop with the upgrade command. A CLI that
cannot run at all is an environment failure: its output is printed verbatim and
must be fixed as reported.

The `--help` probe is what separates those two classes. Do not substitute a match
against Click's error text — its wording changed in Click 8.4, and `science`
allows any `click>=8.1`, so a freshly locked consumer can emit either form. The
root `--version` probe is the permanent bootstrap surface; do not replace it with
a preflight subcommand, which an older CLI could not recognize either.

Ingest the book at the user input (a PDF path, optionally with title/author/citekey hints) by
splitting it into chapters, summarizing each in parallel, and synthesizing a book overview
entity. One invocation handles ONE book.

## Setup

Additionally read `.ai/templates/book.md` if present, else
`references/templates/book.md`.

## Dispatch Strategy

This command runs in two roles.

### If you are the orchestrator

You received `/review-books` directly. Execute the orchestration flow below; dispatch the
reading/synthesis to subagents — do not read every chapter yourself.

### If you are a `book-chapter-researcher` or `book-synthesizer` subagent

Skip to your agent definition's workflow for your one assigned chapter (researcher) or for
the synthesis (synthesizer), then report back.

## Orchestration flow

1. **Parse** the user input: the PDF path plus optional title/author/citekey. If no PDF path
   is given, ask the user for one — books are not fetchable through the paper-fetch tiers.
2. **Metadata + citekey.** Derive author/year/title/publisher from the PDF's first pages or
   the user's hints; build `<citekey>` = `<FirstAuthorLastName><Year>` (e.g. `Kelly1982`),
   suffixing on collision.
3. **Split.** Run `uv run science book-split <pdf> --json`.
   - On success, use the manifest under the `chapters` key. A `truncation` sibling key
     means the book has more chapters than fit the bounded view; pass `--output PATH`
     to get the complete manifest.
   - On a non-zero exit mentioning "no outline", read the ToC pages yourself
     (`Read` with `pages=` over the front matter, ~first 15-20 pp) and build the manifest by
     hand: a list of `{n, title, start_page, end_page, level, part}`.
4. **Printed numbering reconciliation.** Before fan-out, compare the split manifest against the book's printed table of contents and chapter headings. Front matter, Introduction, Bibliography, Appendix, and Index often appear in the PDF outline and can shift the manifest's sequential `n` away from printed chapter numbers. Add `printed_chapter` when it differs from `n`, show both values in the confirmation table, and tell chapter researchers which number to use in headings and citations. Use printed chapter numbers for prose references; keep manifest `n` only for stable filenames and dispatch bookkeeping.
5. **Existing-target gate.** Before writing, check whether `entities/books/<citekey>.md` or
   `doc/books/<citekey>/` already exists. If so, ask the user to **overwrite / skip /
   supplement**, and honor that choice. Never clobber prior notes silently.
6. **Confirmation gate.** Show the user the chapter count + titles (and detected Parts).
   Proceed only on confirmation — this guards against fanning out on a bad split.
7. **Fan out.** Create `doc/books/<citekey>/`. Dispatch one `book-chapter-researcher` per
   chapter **in parallel** (multiple Agent calls in one message), each given
   `{pdf_path, start_page, end_page, n, printed_chapter, title, citekey, out_path}` where
   `out_path` is `doc/books/<citekey>/ch<NN>-<slug>.md`.
8. **Synthesize.** When all chapter subagents return, dispatch ONE `book-synthesizer` with
   the citekey, metadata, the chapter-note paths, and the Part structure. It writes
   `entities/books/<citekey>.md` and any `doc/books/<citekey>/part-N-*.md` rollups.
9. **Integrate (orchestrator, once per book).**
   - Add the BibTeX entry — **never** edit `references.bib` directly:
     ```bash
     uv run science bib add --project-root . <<'EOF'
     @book{<citekey>, title={...}, author={...}, year={...}, publisher={...} }
     EOF
     ```
   - Reserve any new questions via `uv run science questions reserve --slug "<slug>"
     --title "<title>" --source-refs "cite:<citekey>" --json` (the CLI passes refs through
     unchanged, so it needs the `cite:` namespace prefix, not the bare key; never write
     `entities/questions/` directly).
   - Link relevant hypotheses in the overview entity's `related:`.
   - Commit: `git add -A && git commit -m "docs(books): review <citekey> — <short title>"`.

## Annotation tokens

Use `[UNVERIFIED]` (verifiable but unchecked), `[INACCESSIBLE]` (image-only/unreadable),
`[SPECULATION]` (your extrapolation), `[MISSING_CITATION]` per
`references/docs/conventions/annotation-tokens.md`. For a PDF in hand, chapter facts are
`[UNVERIFIED]`, not `[INACCESSIBLE]`.

## Cost note

A 20-chapter book ≈ 20 sonnet chapter subagents + 1 opus synthesizer. The confirmation gate
(step 5) is the spend control.

## Process Reflection

Report friction/gaps/wins via
`science feedback add --target "command:review-books" --category <friction|gap|guidance|suggestion|positive> --summary "<one-line>"`.
Skip if everything worked smoothly.
