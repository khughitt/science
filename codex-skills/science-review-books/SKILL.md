---
name: science-review-books
description: "Review and summarize a book chapter-by-chapter, then synthesize a whole-book overview."
---

# Review Books

Converted from Claude command `/science:review-books`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from layout-v3 entity roots first:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
   - Read legacy specs/research-question.md only if it exists.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

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
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

Ingest the book at the user input (a PDF path, optionally with title/author/citekey hints) by
splitting it into chapters, summarizing each in parallel, and synthesizing a book overview
entity. One invocation handles ONE book.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.
Additionally read `.ai/templates/book.md` if present, else
`templates/book.md`.

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
   - On success, use the manifest.
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
`docs/conventions/annotation-tokens.md`. For a PDF in hand, chapter facts are
`[UNVERIFIED]`, not `[INACCESSIBLE]`.

## Cost note

A 20-chapter book ≈ 20 sonnet chapter subagents + 1 opus synthesizer. The confirmation gate
(step 5) is the spend control.

## Process Reflection

Report friction/gaps/wins via
`science feedback add --target "command:review-books" --category <friction|gap|guidance|suggestion|positive> --summary "<one-line>"`.
Skip if everything worked smoothly.
