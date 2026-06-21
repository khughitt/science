---
description: Review and summarize a book chapter-by-chapter, then synthesize a whole-book overview.
---

# Review Books

Ingest the book at `$ARGUMENTS` (a PDF path, optionally with title/author/citekey hints) by
splitting it into chapters, summarizing each in parallel, and synthesizing a book overview
entity. One invocation handles ONE book.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).
Additionally read `.ai/templates/book.md` if present, else
`${CLAUDE_PLUGIN_ROOT}/templates/book.md`.

## Dispatch Strategy

This command runs in two roles.

### If you are the orchestrator

You received `/review-books` directly. Execute the orchestration flow below; dispatch the
reading/synthesis to subagents — do not read every chapter yourself.

### If you are a `book-chapter-researcher` or `book-synthesizer` subagent

Skip to your agent definition's workflow for your one assigned chapter (researcher) or for
the synthesis (synthesizer), then report back.

## Orchestration flow

1. **Parse** `$ARGUMENTS`: the PDF path plus optional title/author/citekey. If no PDF path
   is given, ask the user for one — books are not fetchable through the paper-fetch tiers.
2. **Metadata + citekey.** Derive author/year/title/publisher from the PDF's first pages or
   the user's hints; build `<citekey>` = `<FirstAuthorLastName><Year>` (e.g. `Kelly1982`),
   suffixing on collision.
3. **Split.** Run `uv run science book-split <pdf> --json`.
   - On success, use the manifest.
   - On a non-zero exit mentioning "no outline", read the ToC pages yourself
     (`Read` with `pages=` over the front matter, ~first 15-20 pp) and build the manifest by
     hand: a list of `{n, title, start_page, end_page, level, part}`.
4. **Existing-target gate.** Before writing, check whether `entities/books/<citekey>.md` or
   `entities/books/<citekey>/` already exists. If so, ask the user to **overwrite / skip /
   supplement**, and honor that choice. Never clobber prior notes silently.
5. **Confirmation gate.** Show the user the chapter count + titles (and detected Parts).
   Proceed only on confirmation — this guards against fanning out on a bad split.
6. **Fan out.** Create `entities/books/<citekey>/`. Dispatch one `book-chapter-researcher` per
   chapter **in parallel** (multiple Agent calls in one message), each given
   `{pdf_path, start_page, end_page, n, title, citekey, out_path}` where `out_path` is
   `entities/books/<citekey>/ch<NN>-<slug>.md`.
7. **Synthesize.** When all chapter subagents return, dispatch ONE `book-synthesizer` with
   the citekey, metadata, the chapter-note paths, and the Part structure. It writes
   `entities/books/<citekey>.md` and any `entities/books/<citekey>/part-N-*.md` rollups.
8. **Integrate (orchestrator, once per book).**
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
