# Design: `/review-books` — chapter-decomposed book ingestion

**Date:** 2026-06-13
**Status:** Design (approved, pre-implementation)
**Motivating case:** natural-systems `task:t688` — review Kelly (1982), a book that does not fit the single-source `/research-papers` flow.
**Upstream tracking:** natural-systems `task:t687` (build this command + subagents).

## 1. Goal & shape

Add a Science command that ingests a **book** — large, multi-chapter, typically no DOI —
the way `/research-papers` ingests a paper, but with a *decompose-then-synthesize* strategy:

> split into chapters → summarize each chapter in parallel → roll up to (optional)
> sub-topic parts → whole-book synthesis.

It mirrors the existing **command + subagents** pattern (`/research-papers` +
`paper-researcher`) exactly. There is **no separate methodology skill** — the
chapter-decomposition strategy lives in the command file, read by both the orchestrator
and the subagents.

Net new upstream surface: **one entity type** (`book`), **one CLI subcommand**
(`science book-split`), **one command file**, **two agent files**, **one template**.

## 2. On-disk / entity model

A book is a directory; the book overview is a first-class entity, the chapters are
lightweight sub-artifacts.

```
doc/books/<citekey>/
  _book.md              # book: entity (validated) — overview + whole-book synthesis + chapter map
  ch01-<slug>.md        # lightweight chapter note (consistent headings, NOT entity-validated)
  ch02-<slug>.md
  ...
  part-1-<slug>.md      # OPTIONAL sub-topic rollup — only when the book has explicit Parts
  part-2-<slug>.md      #   or more than ~8 chapters
```

- **`_book.md`** is a first-class `book:` entity:
  - frontmatter `id: book:<citekey>`, `type: book`, `source_refs: [cite:<citekey>]`,
    `related: [...]` linking to hypotheses / questions.
  - validated against a new `templates/book.md`.
  - The `book:<citekey>` id convention mirrors the project's paper-note convention
    (`paper:<citekey>` in natural-systems). Projects whose paper template uses
    `paper:{{nn}}-{{slug}}` should use the matching `book:{{nn}}-{{slug}}` form; the
    template ships the `{{nn}}-{{slug}}` form and projects override via `.ai/templates/`
    as they already do for papers.
- **Chapter / part files** are *lightweight sub-artifacts*, not entities:
  - a consistent heading set (`## Summary`, `## Key Concepts`, `## Notable Claims`,
    `## Relevance`) for predictability,
  - **no registered `type:` frontmatter**, so the entity-conformance validator skips
    them. This is deliberate: it keeps N chapter files out of the rigid required-section
    path. (A book with 30 chapters should not generate 30 template-conformance warnings.)
  - They MAY carry minimal frontmatter (`book`, `chapter`, `pages`) for provenance, but
    nothing that registers them as a validated entity kind.

**Rationale.** The book overview is the citable, KG-resident artifact (a clean
`source_refs` / `related` target). The chapters are reading notes that support it.
Making chapters first-class entities would multiply the validator-rigidity cost per
chapter for little KG benefit; making the book itself lightweight would leave it unable
to be a clean citation target. The split chosen captures the value at one entity type.

## 3. New Science machinery (`~/d/science/science/`, package `science_tool`)

### 3a. `science book-split <pdf> [--json]`

New click subcommand registered in `src/science_tool/cli.py` (alongside
`@main.command("paper-fetch")`), backed by a new `src/science_tool/book_split.py` module.

- **Input:** a PDF path.
- **Behavior:** extract the embedded PDF outline / bookmarks into a chapter manifest.
- **Output (`--json`):** a list of entries:

  ```json
  [
    {"n": 1, "title": "Introduction", "start_page": 1,  "end_page": 24, "level": 0},
    {"n": 2, "title": "...",          "start_page": 25, "end_page": 58, "level": 0}
  ]
  ```

  - `end_page` is derived as the next entry's `start_page − 1` (last chapter runs to the
    final page).
  - **Parts** are detected from outline hierarchy: a level-0 outline entry that *contains*
    level-1 entries is a Part; its children are the chapters. The manifest exposes `level`
    (and, where a hierarchy exists, a `part` grouping) so the synthesizer can decide on
    `part-N-*.md` rollups.
- **No outline present:** exit non-zero with a clear, machine-greppable message (e.g.
  `error: no outline/bookmarks in PDF`). This is the signal that triggers the
  orchestrator's ToC-reading fallback (§5 step 3). Fail early; do not silently emit an
  empty or guessed manifest.
- **Implementation note:** use the PDF library already available to the project (e.g.
  `pypdf`/`pymupdf`); confine PDF parsing to `book_split.py`.

### 3b. `book` entity type

- Register `book` in `src/science_tool/entity_kinds.py`.
- Add `templates/book.md` (§6).
- Add a `book` case to the entity-conformance validator
  (`src/science_tool/validate/checks/entity_conformance.py`) with required sections
  matching the template.
- **Confirm** that files under `doc/books/*/` other than `_book.md` are excluded from
  entity validation (they have no registered `type:`). Add a focused test asserting that
  a `doc/books/<citekey>/chNN-*.md` file does not raise a conformance/missing-frontmatter
  warning.

## 4. Command + subagents

- **`commands/review-books.md`** — orchestrator dispatcher; holds the canonical workflow
  (parse → split → confirm → fan out → synthesize → integrate → reflect). Both subagents
  read this file for the shared procedure, exactly as `paper-researcher` reads
  `research-papers.md`.
- **`agents/book-chapter-researcher.md`** — model `claude-sonnet-4-6` (mechanical
  extraction; matches `paper-researcher`'s tier). One instance per chapter, dispatched in
  parallel. Reads its assigned page range from the PDF, writes one `chNN-<slug>.md` with
  the standard chapter heading set. Reports back a ≤150-word summary (chapter n, path,
  any `[UNVERIFIED]`/`[INACCESSIBLE]` flags).
- **`agents/book-synthesizer.md`** — model `claude-opus-*` (judgment / cross-chapter
  synthesis). Reads all chapter files; writes `_book.md` and, adaptively, the
  `part-N-<slug>.md` rollups. Does **not** do bib/question/commit work — that is the
  orchestrator's single-owner responsibility (§5 step 7).

## 5. Orchestration flow (in `review-books.md`)

1. **Parse** `$ARGUMENTS`: a PDF path (primary input), plus optional title / author /
   citekey hints. If no PDF path is given, ask for one — books are not fetchable through
   the paper-fetch tiers, so there is no DOI-probing path here.
2. **Metadata + citekey.** Derive author / year / title / publisher from the PDF's first
   pages (or user hints); build `<citekey> = <FirstAuthorLastName><Year>` (e.g.
   `Kelly1982`), with a suffix on collision.
3. **Split.** Run `science book-split <pdf> --json` → manifest.
   - On success: use the manifest.
   - On `no outline` exit: orchestrator reads the ToC pages itself (Read tool,
     `pages=` over the front matter, ~first 15–20 pp) and constructs the manifest by hand.
4. **Confirmation gate.** Present the chapter count + titles (and detected Parts, if any)
   to the user before fan-out. This is the spend control: it prevents dispatching dozens
   of subagents on a mis-parsed split. Proceed on confirmation.
5. **Fan out.** Create `doc/books/<citekey>/`. Dispatch one `book-chapter-researcher` per
   chapter **in parallel** (multiple Agent tool uses in one message), each given
   `{pdf path, start_page, end_page, n, title, citekey, out_path}`.
6. **Synthesize.** When all chapter subagents return, dispatch a single
   `book-synthesizer` with the chapter file list and the Part structure. It writes
   `_book.md` and the adaptive `part-N-*.md` rollups (parts only when the outline has
   explicit Parts or chapter count > ~8).
7. **Integrate (orchestrator, once per book).**
   - `science bib add` an `@book{<citekey>, title, author, year, publisher, ...}` entry
     (locked append; never hand-edit `references.bib`).
   - `science question reserve` for any new questions the book raises (atomic slot claim).
   - Link relevant hypotheses in `_book.md`'s `related:`.
   - `git commit -m "docs(books): review <citekey> — <short title>"`.
8. **Process reflection.** `science feedback add --target command:review-books
   --category <...> --summary <...>` for any friction/gaps/wins (skip if smooth).

## 6. `templates/book.md` — validated sections

Required sections on `_book.md`:

- `## Overview` — bibliographic block (authors, year, publisher, BibTeX key, `Source: PDF`)
  + scope/intended-audience.
- `## Whole-Book Synthesis` — the cross-chapter argument and through-lines.
- `## Chapter Map` — a table: chapter number → link to `chNN-*.md` → one-line gist.
- `## Key Themes` — the recurring concepts that span chapters.
- `## Relevance` — connection to the project's research questions / hypotheses (reference
  hypothesis and question IDs).
- `## Limitations` — what the book does not cover; dated or contested positions.
- `## Follow-up` — derived questions, chapters worth re-reading, related papers to ingest.

The template carries the `_template.frontmatter` + `_template.sections` block (mirroring
`templates/paper.md`) so it round-trips through the entity tooling.

## 7. Conventions reused as-is

- **Annotation tokens** — `[UNVERIFIED]` / `[INACCESSIBLE]` / `[SPECULATION]` /
  `[MISSING_CITATION]`, per `docs/conventions/annotation-tokens.md`. For a PDF in hand,
  chapter facts are `[UNVERIFIED]` (verifiable), not `[INACCESSIBLE]`.
- **`science bib add`** — concurrency-safe locked append; the only way to touch
  `references.bib`.
- **`science question reserve`** — atomic `O_CREAT|O_EXCL` slot claim; the only way to add
  questions.
- **Command preamble** — `references/command-preamble.md` for profile/role/aspect/template
  resolution; `review-books.md` invokes it like every other command.

## 8. Cost note

A 20-chapter book ≈ 20 sonnet chapter subagents + 1 opus synthesizer. The
confirmation gate (step 4) is the primary spend control; the command file documents the
rough cost so the operator opts in knowingly. Chapter subagents are deliberately the
cheaper tier because per-chapter work is extraction, not judgment; synthesis — which needs
the whole book in view — is the opus step.

## 9. Out of scope (YAGNI)

- No EPUB/HTML ingestion in v1 — PDF only. (`book-split` can grow formats later.)
- No incremental / resume-after-partial mode — a re-run overwrites the book directory.
- No automatic cross-book synthesis (the `/research-papers` batch-synthesis analogue);
  one invocation = one book.
- No methodology skill leaf — revisit only if the strategy proves reusable outside the
  command.

## 10. Implementation checklist (for the plan phase)

1. `science_tool/book_split.py` + `@main.command("book-split")` in `cli.py` + tests
   (outline present, outline absent → non-zero, Part hierarchy detection).
2. `templates/book.md`.
3. Register `book` in `entity_kinds.py`; add `book` case to
   `validate/checks/entity_conformance.py`; test that chapter files are not validated.
4. `agents/book-chapter-researcher.md`.
5. `agents/book-synthesizer.md`.
6. `commands/review-books.md`.
7. Smoke test end-to-end against Kelly (1982) (this is `task:t688`, downstream).
