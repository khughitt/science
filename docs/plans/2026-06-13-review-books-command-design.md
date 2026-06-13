# Design: `/review-books` — chapter-decomposed book ingestion

**Date:** 2026-06-13
**Status:** Design (approved, pre-implementation)
**Motivating case:** natural-systems `task:t688` — review Kelly (1982), a book that does not fit the single-source `/research-papers` flow.
**Upstream tracking:** natural-systems `task:t687` (build this command + subagents).

> **Revision (post code-review, 2026-06-13):** corrected after a review of the actual
> `science_tool` / `science_model` code. Key changes from the first draft: the book entity
> lives under `entities/books/` (not `doc/`), chapters live separately under `doc/books/`,
> `book` is registered as a **core** profile kind (not a project-local `entity_kinds.py`
> add), section validation is added in `document_structure.py` (not `entity_conformance.py`),
> the orchestration flow gains an existing-directory gate, and all paths use the real
> package root `science/src/science_tool/...`. See §11 for the resolved review items.

## 1. Goal & shape

Add a Science command that ingests a **book** — large, multi-chapter, typically no DOI —
the way `/research-papers` ingests a paper, but with a *decompose-then-synthesize* strategy:

> split into chapters → summarize each chapter in parallel → roll up to (optional)
> sub-topic parts → whole-book synthesis.

It mirrors the existing **command + subagents** pattern (`/research-papers` +
`paper-researcher`) exactly. There is **no separate methodology skill** — the
chapter-decomposition strategy lives in the command file, read by both the orchestrator
and the subagents.

Net new upstream surface: **one core entity kind** (`book`), **one CLI subcommand**
(`science book-split`), **one command file**, **two agent files**, **one template**.

## 2. On-disk / entity model

The book *overview* is a first-class **core** entity in the entity home; the chapters and
part rollups are lightweight sub-artifacts under `doc/`. The two MUST live in different
roots — see §11 finding 1/2 for why.

```
entities/books/<citekey>.md        # book: core entity (validated; templates/book.md + _BOOK_SECTIONS)
doc/books/<citekey>/
  ch01-<slug>.md                   # lightweight chapter note (no registered type: → validators skip it)
  ch02-<slug>.md
  ...
  part-1-<slug>.md                 # OPTIONAL sub-topic rollup — only when the book has explicit Parts
  part-2-<slug>.md                 #   or more than ~8 chapters
```

- **`entities/books/<citekey>.md`** is a first-class core `book:` entity:
  - frontmatter `id: book:<citekey>`, `type: book`, `title`, `status`, `created`,
    `updated`, `source_refs: [cite:<citekey>]`, `related: [...]` (hypotheses / questions).
    The six-field required set (`id, type, title, status, created, updated`) is enforced by
    `check_entity_frontmatter_completeness`.
  - filename and id convention **mirror the `paper` core kind**: `book:<citekey>` id,
    `<citekey>.md` filename. The path policy, filename strategy, and default statuses for
    `book` are cloned from `paper` so `check_entity_filename_conformance` and
    `check_entity_location_coherence` pass.
  - holds the overview, whole-book synthesis, and a chapter map linking out to the chapter
    notes under `doc/books/<citekey>/`.
- **Chapter / part files** are *lightweight sub-artifacts*, not entities:
  - a consistent heading set (`## Summary`, `## Key Concepts`, `## Notable Claims`,
    `## Relevance`) for predictability,
  - **no registered `type:` frontmatter**. They live under `doc/books/` (a legacy root that
    `check_entity_location_coherence` only flags for files whose `type` *is* a registered
    markdown entity kind). Because chapters carry no registered kind, the location check
    skips them. They are NOT placed under `entities/books/`, where the non-recursive
    `*.md` completeness scan would flag every frontmatter-less file.
  - They MAY carry minimal provenance frontmatter (`book: <citekey>`, `chapter: N`,
    `pages: "25-58"`) — just nothing that registers them as an entity kind.

**Rationale.** The book overview is the citable, KG-resident artifact (a clean
`source_refs` / `related` target). The chapters are reading notes that support it. A
dedicated core `book` kind (sibling to the existing `paper` and `article` core kinds) keeps
the overview section-validated and KG-resolvable in every project that uses the shipped
command, while the chapters stay out of the validator's rigid required-section path.

## 3. New Science machinery

> Package root is **`science/src/science_tool/`** and the model package is
> **`science/model/src/science_model/`** (the repo root `~/d/science` contains the
> `science/` project dir). All paths below are relative to the repo root.

### 3a. `science book-split <pdf> [--json]`

New click subcommand registered in `science/src/science_tool/cli.py` (alongside
`@main.command("paper-fetch")`), backed by a new
`science/src/science_tool/book_split.py` module.

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
    (and a `part` grouping where a hierarchy exists) so the synthesizer can decide on
    `part-N-*.md` rollups.
- **No outline present:** exit non-zero with a clear, machine-greppable message (e.g.
  `error: no outline/bookmarks in PDF`). This is the signal that triggers the
  orchestrator's ToC-reading fallback (§5 step 3). Fail early; do not silently emit an
  empty or guessed manifest.
- **Implementation note:** use the PDF library already available to the project (e.g.
  `pypdf`/`pymupdf`); confine PDF parsing to `book_split.py`.

### 3b. `book` as a core entity kind

Register `book` as a **core profile** kind (not a project-local kind via
`entity_kinds.py`). Mirror the existing `paper` kind at each site:

1. `science/model/src/science_model/entities.py` — add `BOOK = "book"` to the
   `EntityType` enum.
2. `science/model/src/science_model/profiles/core.py` — add an
   `EntityKind(name="book", canonical_prefix="book", layer="layer/core", description=...)`
   to `CORE_PROFILE.entity_kinds`.
3. **Path policy / home / filename strategy / default statuses** — clone `paper`'s:
   home `entities/books/`, citekey filename strategy, the same default status set. (These
   live alongside the other core-kind definitions in `science_model` / the path-policy
   layer surfaced through `science_tool/entities.py`.)
4. `science/src/science_tool/graph/entity_registry.py` — register `book` so it resolves in
   the knowledge graph (mirror `paper`).
5. **Markdown-entity wiring** — ensure `book` is recognized as a markdown entity kind
   (`science/src/science_tool/entities.py`) so `is_markdown_entity_kind("book")` is true
   and `entities/books/` is treated as the kind's home.
6. **Template packaging** — `templates/book.md` (§6) is packaged/discoverable the same way
   `templates/paper.md` is, so the command preamble's template resolution finds it.

### 3c. Section validation

Required-section checks are **hard-coded per kind in**
`science/src/science_tool/validate/checks/document_structure.py` — `entity_conformance.py`
does NOT do section checks. So:

- Add `_BOOK_SECTIONS = ("## Overview", "## Whole-Book Synthesis", "## Chapter Map",
  "## Key Themes", "## Relevance", "## Limitations", "## Follow-up")`.
- Add a `books_dir = ctx.project_root / "entities" / "books"` branch in
  `check_document_structure` that runs `_check_documents(ctx, books_dir, _BOOK_SECTIONS)`.
- Chapters under `doc/books/` are deliberately NOT added here — they are unvalidated notes.

## 4. Command + subagents

- **`commands/review-books.md`** — orchestrator dispatcher; holds the canonical workflow
  (parse → split → confirm → fan out → synthesize → integrate → reflect). Both subagents
  read this file for the shared procedure, exactly as `paper-researcher` reads
  `research-papers.md`.
- **`agents/book-chapter-researcher.md`** — model `claude-sonnet-4-6` (mechanical
  extraction; matches `paper-researcher`'s tier). One instance per chapter, dispatched in
  parallel. Reads its assigned page range from the PDF, writes one
  `doc/books/<citekey>/chNN-<slug>.md` with the standard chapter heading set. Reports back
  a ≤150-word summary (chapter n, path, any `[UNVERIFIED]`/`[INACCESSIBLE]` flags).
- **`agents/book-synthesizer.md`** — model `claude-opus-*` (judgment / cross-chapter
  synthesis). Reads all chapter files; writes the book entity
  `entities/books/<citekey>.md` and, adaptively, the
  `doc/books/<citekey>/part-N-<slug>.md` rollups. Does **not** do bib/question/commit work
  — that is the orchestrator's single-owner responsibility (§5 step 7).

## 5. Orchestration flow (in `review-books.md`)

1. **Parse** `$ARGUMENTS`: a PDF path (primary input), plus optional title / author /
   citekey hints. If no PDF path is given, ask for one — books are not fetchable through
   the paper-fetch tiers, so there is no DOI-probing path here.
2. **Metadata + citekey.** Derive author / year / title / publisher from the PDF's first
   pages (or user hints); build `<citekey> = <FirstAuthorLastName><Year>` (e.g.
   `Kelly1982`), with a suffix on collision.
3. **Split.** Run `science book-split <pdf> --json` → manifest.
   - On success: use the manifest.
   - On `no outline` exit: orchestrator reads the ToC pages itself (Read tool, `pages=`
     over the front matter, ~first 15–20 pp) and constructs the manifest by hand.
4. **Existing-target gate.** Before any writes, check whether
   `entities/books/<citekey>.md` or `doc/books/<citekey>/` already exists. If so, mirror
   `/research-papers`' pre-dispatch behavior: ask the user to **overwrite / skip /
   supplement**, and carry that decision into the run. Never clobber prior chapter notes or
   user edits silently.
5. **Confirmation gate.** Present the chapter count + titles (and detected Parts, if any)
   to the user before fan-out. This is the spend control: it prevents dispatching dozens of
   subagents on a mis-parsed split. Proceed on confirmation.
6. **Fan out.** Create `doc/books/<citekey>/`. Dispatch one `book-chapter-researcher` per
   chapter **in parallel** (multiple Agent tool uses in one message), each given
   `{pdf path, start_page, end_page, n, title, citekey, out_path}`.
7. **Synthesize.** When all chapter subagents return, dispatch a single `book-synthesizer`
   with the chapter file list and the Part structure. It writes
   `entities/books/<citekey>.md` and the adaptive `doc/books/<citekey>/part-N-*.md`
   rollups (parts only when the outline has explicit Parts or chapter count > ~8).
8. **Integrate (orchestrator, once per book).**
   - `science bib add` an `@book{<citekey>, title, author, year, publisher, ...}` entry
     (locked append; never hand-edit `references.bib`).
   - `science question reserve` for any new questions the book raises (atomic slot claim).
   - Link relevant hypotheses in the entity's `related:`.
   - `git commit -m "docs(books): review <citekey> — <short title>"`.
9. **Process reflection.** `science feedback add --target command:review-books
   --category <...> --summary <...>` for any friction/gaps/wins (skip if smooth).

## 6. `templates/book.md` — validated sections

Required sections on `entities/books/<citekey>.md` (must match `_BOOK_SECTIONS` in §3c):

- `## Overview` — bibliographic block (authors, year, publisher, BibTeX key, `Source: PDF`)
  + scope/intended-audience.
- `## Whole-Book Synthesis` — the cross-chapter argument and through-lines.
- `## Chapter Map` — a table: chapter number → link to
  `../../doc/books/<citekey>/chNN-*.md` → one-line gist.
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

A 20-chapter book ≈ 20 sonnet chapter subagents + 1 opus synthesizer. The confirmation gate
(step 5) is the primary spend control; the command file documents the rough cost so the
operator opts in knowingly. Chapter subagents are deliberately the cheaper tier because
per-chapter work is extraction, not judgment; synthesis — which needs the whole book in view
— is the opus step.

## 9. Out of scope (YAGNI)

- No EPUB/HTML ingestion in v1 — PDF only. (`book-split` can grow formats later.)
- No incremental / resume-after-partial mode beyond the overwrite/skip/supplement gate.
- No automatic cross-book synthesis (the `/research-papers` batch-synthesis analogue);
  one invocation = one book.
- No methodology skill leaf — revisit only if the strategy proves reusable outside the
  command.

## 10. Implementation checklist (for the plan phase)

1. **`book` core kind wiring** (§3b): `EntityType.BOOK` in
   `science/model/src/science_model/entities.py`; `EntityKind` in
   `science/model/src/science_model/profiles/core.py`; path policy / home / filename
   strategy / default statuses cloned from `paper`; graph registration in
   `science/src/science_tool/graph/entity_registry.py`; markdown-entity recognition in
   `science/src/science_tool/entities.py`. Add tests that `book:<citekey>` resolves and
   that `entities/books/<citekey>.md` passes location/filename/frontmatter conformance.
2. **`templates/book.md`** (§6), packaged like `templates/paper.md`.
3. **Section validation** (§3c): `_BOOK_SECTIONS` + `entities/books` branch in
   `science/src/science_tool/validate/checks/document_structure.py`; test a conforming and
   a missing-section book.
4. **Chapter-note exclusion test:** assert a `doc/books/<citekey>/chNN-*.md` file (no
   registered `type:`) raises no conformance / missing-frontmatter / location warning.
5. **`science book-split`** (§3a): `science/src/science_tool/book_split.py` +
   `@main.command("book-split")` in `cli.py`; tests for outline-present, outline-absent
   (non-zero exit), and Part-hierarchy detection.
6. **`agents/book-chapter-researcher.md`** (sonnet).
7. **`agents/book-synthesizer.md`** (opus).
8. **`commands/review-books.md`** — including the existing-target gate (step 4) and the
   confirmation gate (step 5).
9. **Smoke test** end-to-end against Kelly (1982) — this is `task:t688`, downstream of the
   build.

## 11. Resolved review items (code-review, 2026-06-13)

1. **(High) Entity home.** First draft put the book entity at `doc/books/<citekey>/_book.md`.
   `check_entity_location_coherence` treats `doc/` as a legacy root and flags any registered
   markdown entity there as "outside its home." **Resolved:** the entity lives at
   `entities/books/<citekey>.md`.
2. **(High) Chapter-note flagging.** `check_entity_frontmatter_completeness` scans every
   `*.md` directly under an entity home and flags frontmatter-less files regardless of
   `type:`. **Resolved:** chapters live under `doc/books/<citekey>/` (not the entity home)
   and carry no registered kind, so the location check skips them and the completeness scan
   never sees them.
3. **(High) Registration site.** `entity_kinds.py` registers *project-local* kinds, not core
   kinds. **Resolved:** `book` is wired as a core kind across `science_model` enum + core
   profile + path policy + graph registry + markdown-entity recognition + template packaging
   (§3b). Decision recorded: **core kind** (sibling to `paper`/`article`).
4. **(Medium) Section checks.** Section validation is hard-coded in `document_structure.py`,
   not `entity_conformance.py`. **Resolved:** add `_BOOK_SECTIONS` + an `entities/books`
   branch there (§3c).
5. **(Medium) Overwrite gate.** First draft said reruns overwrite the directory with no gate.
   **Resolved:** step 4 adds an existing-target overwrite/skip/supplement check mirroring
   `/research-papers`.
6. **(Low) Package path.** Paths corrected from `src/science_tool/...` to the real
   `science/src/science_tool/...` (and `science/model/src/science_model/...`) throughout.
