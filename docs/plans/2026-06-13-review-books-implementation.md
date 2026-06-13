# /review-books Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Science `/review-books` command that ingests a multi-chapter book PDF by splitting it into chapters, summarizing each in parallel, and synthesizing a whole-book overview entity — backed by a new core `book` entity kind.

**Architecture:** Mirror the existing `paper` kind and `/research-papers` command. A new core `book` entity kind (model enum + core profile + path policy + graph registry + templates + section validation) holds the book overview at `entities/books/<citekey>.md`; lightweight chapter/part notes live under `doc/books/<citekey>/`. A new `science book-split` CLI extracts the PDF outline into a chapter manifest; the command dispatches one `book-chapter-researcher` subagent per chapter and one `book-synthesizer` to roll up. The bib layer learns to materialize `@book` entries as `book:` nodes.

**Tech Stack:** Python (pydantic v2, click), `pypdf` (new dep) for PDF outline extraction, pytest (`uv run pytest`), Markdown command/agent/template files.

**Design reference:** `docs/plans/2026-06-13-review-books-command-design.md`.

**Repo geography (read once):**
- Tool package: `science/src/science_tool/` — tests in `science/tests/`, run with `cd science && uv run pytest …`.
- Model package: `science/model/src/science_model/` — tests in `science/model/tests/`, run with `cd science/model && uv run pytest …`.
- Command-facing templates: `templates/` (repo root). Packaged templates: `science/model/src/science_model/templates/`.
- Commands: `commands/`. Agents: `agents/`.
- pytest default flags (`science/pyproject.toml`) exclude `snapshot` and `real_projects` markers — no special flags needed.

---

## Task 1: Add `BOOK` to the EntityType enum and a `BookEntity` typed class

**Files:**
- Modify: `science/model/src/science_model/entities.py` (enum ~line 101; new class after `PaperEntity` ~line 577)
- Test: `science/model/tests/test_typed_entities.py`

- [ ] **Step 1: Write the failing test**

Add to `science/model/tests/test_typed_entities.py` (mirrors the existing `PaperEntity` tests; reuses the module's `_minimal` helper). Also add `BookEntity` to the import block from `science_model.entities`:

```python
def test_book_entity_extends_project_entity() -> None:
    b = BookEntity(**_minimal(EntityType.BOOK, "book:Kelly1982"))
    assert isinstance(b, ProjectEntity)
    assert isinstance(b, Entity)
    assert b.kind == "book"


def test_book_entity_coerces_scalar_authors_and_null_strings() -> None:
    b = BookEntity(
        **_minimal(EntityType.BOOK, "book:Kelly1982"),
        authors="Kelly, J. L.",
        publisher=None,
    )
    assert b.authors == ["Kelly, J. L."]
    assert b.publisher == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest tests/test_typed_entities.py::test_book_entity_extends_project_entity -v`
Expected: FAIL — `ImportError: cannot import name 'BookEntity'` (or `AttributeError: BOOK`).

- [ ] **Step 3: Implement the enum value and the typed class**

In `science/model/src/science_model/entities.py`, add to the `EntityType` enum immediately after `PAPER = "paper"`:

```python
    PAPER = "paper"
    BOOK = "book"
```

Then add a new class immediately after the `PaperEntity` class definition (after its `_coerce_nullable_strings` validator, before `class TalkEntity`):

```python
class BookEntity(ProjectEntity):
    """Book — typed entity for a long-form monograph summarized chapter-by-chapter.

    A source that *provides* evidence (like `paper`) but carries no truth-apt
    claim of its own, so it is OPERATIONAL / non-epistemic — never a
    `bears_on`/belief target.
    """

    bibkey: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1800, le=2200)
    publisher: str = ""
    isbn: str = ""
    doi: str = ""
    url: str = ""
    key_findings: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("authors", mode="before")
    @classmethod
    def _coerce_scalar_authors(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("bibkey", "publisher", "isbn", "doi", "url", mode="before")
    @classmethod
    def _coerce_nullable_strings(cls, value: object) -> object:
        if value is None:
            return ""
        return value
```

Add `BookEntity` to the `science_model.entities` imports at the top of `test_typed_entities.py` (alphabetically, near `PaperEntity`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run pytest tests/test_typed_entities.py -k book -v`
Expected: PASS (both new tests).

- [ ] **Step 5: Commit**

```bash
cd /home/keith/d/science
git add science/model/src/science_model/entities.py science/model/tests/test_typed_entities.py
git commit -m "feat(model): add BOOK entity type and BookEntity typed class"
```

---

## Task 2: Reject `review_state` on the non-epistemic `book` kind

**Files:**
- Modify: `science/model/src/science_model/entities.py` (`_validate_review_state_kind`, ~line 264)
- Test: `science/model/tests/test_review_state_model.py` (`NON_EPISTEMIC_KINDS`, line 101)

- [ ] **Step 1: Write the failing test**

In `science/model/tests/test_review_state_model.py`, add `"book"` to the `NON_EPISTEMIC_KINDS` list so the existing parametrized tests cover it:

```python
NON_EPISTEMIC_KINDS = ["task", "dataset", "workflow-run", "data-package", "paper", "experiment", "book"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest "tests/test_review_state_model.py::test_review_state_rejected_on_non_epistemic_kinds[book]" -v`
Expected: FAIL — `DID NOT RAISE ValidationError` (book is not yet in the validator's set).

- [ ] **Step 3: Add `book` to the non_epistemic set**

In `science/model/src/science_model/entities.py`, in `_validate_review_state_kind`, add `"book"` after `"paper"`:

```python
        non_epistemic = {
            "task",
            "dataset",
            "workflow-run",
            "data-package",
            "paper",
            "book",
            "experiment",
            "code-file",
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run pytest "tests/test_review_state_model.py" -k book -v`
Expected: PASS (both the rejected-on and still-valid-without parametrizations for `book`).

- [ ] **Step 5: Commit**

```bash
cd /home/keith/d/science
git add science/model/src/science_model/entities.py science/model/tests/test_review_state_model.py
git commit -m "feat(model): reject review_state on non-epistemic book kind"
```

---

## Task 3: Declare `book` as a core profile kind

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (after the `paper` EntityKind, ~line 90)
- Test: `science/model/tests/test_core_profile_has_book.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_core_profile_has_book.py`:

```python
from __future__ import annotations

from science_model.profiles import CORE_PROFILE


def test_core_profile_declares_book_kind() -> None:
    by_name = {k.name: k for k in CORE_PROFILE.entity_kinds}
    assert "book" in by_name, "book must be a core profile kind"
    book = by_name["book"]
    assert book.canonical_prefix == "book"
    assert book.layer == "layer/core"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest tests/test_core_profile_has_book.py -v`
Expected: FAIL — `AssertionError: book must be a core profile kind`.

- [ ] **Step 3: Add the EntityKind**

In `science/model/src/science_model/profiles/core.py`, insert immediately after the `paper` `EntityKind(...)` block and before `talk`:

```python
        EntityKind(
            name="book",
            canonical_prefix="book",
            layer="layer/core",
            description="Long-form monograph summarized chapter-by-chapter; an evidence source.",
        ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run pytest tests/test_core_profile_has_book.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/keith/d/science
git add science/model/src/science_model/profiles/core.py science/model/tests/test_core_profile_has_book.py
git commit -m "feat(model): declare book as a core profile kind"
```

---

## Task 4: Register `book` path policy, default status, and status values

**Files:**
- Modify: `science/src/science_tool/entities.py` (`_BUILTIN_MARKDOWN_POLICIES` ~line 62; `_DEFAULT_STATUS` ~line 227; `_STATUS_VALUES` ~line 272)
- Test: `science/tests/test_book_entity_policy.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_book_entity_policy.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.entities import is_markdown_entity_kind, resolve_path_policy


def test_book_is_markdown_entity_kind() -> None:
    assert is_markdown_entity_kind("book") is True


def test_book_path_policy_home_and_strategy() -> None:
    policy = resolve_path_policy("book")
    assert policy.root == Path("entities/books")
    assert policy.strategy == "citekey"
```

> If `resolve_path_policy` is not the exact public accessor in `entities.py`, use the same
> accessor the analogous `paper` test uses — grep `science/tests` for `resolve_path_policy`
> or `EntityPathPolicy` to confirm the import name before writing the test.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_book_entity_policy.py -v`
Expected: FAIL — `is_markdown_entity_kind("book")` is `False` (book not in the policy table).

- [ ] **Step 3: Add the three entries**

In `science/src/science_tool/entities.py`:

In `_BUILTIN_MARKDOWN_POLICIES`, after the `"paper"` line:

```python
    "paper": EntityPathPolicy(Path("entities/papers"), "citekey"),
    "book": EntityPathPolicy(Path("entities/books"), "citekey"),
```

In `_DEFAULT_STATUS`, after the `"paper"` line:

```python
    "paper": "active",
    "book": "active",
```

In `_STATUS_VALUES`, after the `"paper"` line:

```python
    "paper": frozenset({"active", "retired"}),
    "book": frozenset({"active", "retired"}),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_book_entity_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/keith/d/science
git add science/src/science_tool/entities.py science/tests/test_book_entity_policy.py
git commit -m "feat(entities): register book path policy, default status, status values"
```

---

## Task 5: Register `book` in the graph entity registry

**Files:**
- Modify: `science/src/science_tool/graph/entity_registry.py` (import block ~line 24; `_CORE_KIND_CLASSES` ~line 78; `with_core_types` ~line 123)
- Test: `science/tests/graph/test_book_kind_registered.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/graph/test_book_kind_registered.py`:

```python
from __future__ import annotations

from science_model.entities import BookEntity, EntityClass
from science_tool.graph.entity_registry import EntityRegistry


def test_book_kind_registered_as_operational() -> None:
    r = EntityRegistry.with_core_types()
    assert r.entity_class_for("book") == EntityClass.OPERATIONAL
    assert r.model_for("book") is BookEntity
```

> `entity_class_for` / `model_for` are placeholder accessor names — before writing, grep
> `entity_registry.py` for the real public methods that return a kind's `EntityClass` and
> its registered model class, and use those. The intent (book → OPERATIONAL, model =
> BookEntity) is what matters.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/graph/test_book_kind_registered.py -v`
Expected: FAIL — book is not registered (KeyError or None).

- [ ] **Step 3: Wire the registry**

In `science/src/science_tool/graph/entity_registry.py`:

Add `BookEntity` to the `from science_model.entities import (...)` block (alphabetically, before `ChainAuditEntity`):

```python
from science_model.entities import (
    BookEntity,
    ChainAuditEntity,
    CodeFileEntity,
```

In `_CORE_KIND_CLASSES`, after the `"paper"` line:

```python
    "paper": EntityClass.OPERATIONAL,
    "book": EntityClass.OPERATIONAL,
```

In `with_core_types()`, after the `r.register_core_kind("paper", ...)` line:

```python
    r.register_core_kind("paper", PaperEntity, entity_class=_CORE_KIND_CLASSES["paper"])
    r.register_core_kind("book", BookEntity, entity_class=_CORE_KIND_CLASSES["book"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/graph/test_book_kind_registered.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/keith/d/science
git add science/src/science_tool/graph/entity_registry.py science/tests/graph/test_book_kind_registered.py
git commit -m "feat(graph): register book kind (BookEntity, OPERATIONAL)"
```

---

## Task 6: Author the `book` template in both surfaces

**Files:**
- Create: `templates/book.md` (repo-root, command-facing)
- Create: `science/model/src/science_model/templates/book.md` (packaged, byte-identical)
- Test: `science/model/tests/test_book_template_renders.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_book_template_renders.py`:

```python
from __future__ import annotations

from datetime import date

from science_model.templates import Renderer


def test_book_template_renders_from_packaged_copy() -> None:
    out = Renderer(today=date(2026, 6, 13)).render(
        "book",
        fields={
            "entity_id": "book:Kelly1982",
            "title": "A New Interpretation of Information Rate",
            "source_refs": ["cite:Kelly1982"],
            "related": [],
        },
    )
    assert out.startswith("---\n")
    for section in (
        "## Overview",
        "## Whole-Book Synthesis",
        "## Chapter Map",
        "## Key Themes",
        "## Relevance",
        "## Limitations",
        "## Follow-up",
    ):
        assert section in out
```

> The exact `fields` keys depend on the template's `_template.frontmatter` bindings. Model
> them on `science/model/src/science_model/templates/paper.md` — read its
> `_template.frontmatter` block and supply the same `from:` source keys. Adjust `fields`
> until `render` succeeds; the section assertions are the load-bearing part.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest tests/test_book_template_renders.py -v`
Expected: FAIL — `EntityTemplateError: Packaged template not found: science_model/templates/book.md`.

- [ ] **Step 3: Create the template (both copies, identical)**

Write this content to **both** `templates/book.md` and
`science/model/src/science_model/templates/book.md`. Mirror the `_template` block style of
`paper.md`; required sections must equal `_BOOK_SECTIONS` from Task 8.

```markdown
---
id: "book:{{nn}}-{{slug}}"
type: "book"
title: "{{title}}"
status: "active"
ontology_terms: []
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "book" }
    title: { from: title }
    status: { from: status }
    ontology_terms: { default: [] }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: overview, name: "Overview", required: true }
    - { key: whole-book-synthesis, name: "Whole-Book Synthesis", required: true }
    - { key: chapter-map, name: "Chapter Map", required: true }
    - { key: key-themes, name: "Key Themes", required: true }
    - { key: relevance, name: "Relevance", required: true }
    - { key: limitations, name: "Limitations", required: true }
    - { key: follow-up, name: "Follow-up", required: true }
---

# {{title}}

<!--
- **Authors:** <authors>
- **Year:** <year>
- **Publisher:** <publisher>
- **ISBN:** <isbn>
- **BibTeX key:** <bibtex-key>
- **Source:** PDF
-->

## Overview

<!-- Bibliographic block + scope / intended audience. What kind of book is this? -->

## Whole-Book Synthesis

<!-- The cross-chapter argument and through-lines. Synthesized after all chapters. -->

## Chapter Map

<!-- Table: chapter # -> link to ../../doc/books/<citekey>/chNN-*.md -> one-line gist. -->

| # | Chapter | Gist |
|---|---------|------|

## Key Themes

<!-- Recurring concepts that span chapters. -->

## Relevance

<!-- Connection to project research questions / hypotheses. Reference hypothesis/question IDs. -->

## Limitations

<!-- What the book does not cover; dated or contested positions. -->

## Follow-up

<!-- Derived questions, chapters worth re-reading, related papers to ingest. -->
```

After writing both, verify they are byte-identical:

```bash
diff templates/book.md science/model/src/science_model/templates/book.md && echo IDENTICAL
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run pytest tests/test_book_template_renders.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/keith/d/science
git add templates/book.md science/model/src/science_model/templates/book.md science/model/tests/test_book_template_renders.py
git commit -m "feat(templates): add book template (command-facing + packaged copies)"
```

---

## Task 7: Validate book-overview sections under `entities/books/`

**Files:**
- Modify: `science/src/science_tool/validate/checks/document_structure.py` (`_BOOK_SECTIONS` ~line 29; `check_document_structure` ~line 38)
- Test: `science/tests/validate/test_checks_document_structure_book.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/validate/test_checks_document_structure_book.py` (mirrors
`test_checks_document_structure_entities.py`):

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.document_structure import check_document_structure
from science_tool.validate.context import ValidateContext


def _project(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )


def _write_book(tmp_path: Path, body: str) -> Path:
    d = tmp_path / "entities" / "books"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "Kelly1982.md"
    p.write_text(
        '---\nid: "book:Kelly1982"\ntype: book\nstatus: active\n---\n# Book\n' + body,
        encoding="utf-8",
    )
    return p


def test_book_missing_section_is_flagged(tmp_path: Path) -> None:
    _project(tmp_path)
    _write_book(tmp_path, "\n## Overview\n\ntext\n")  # missing the other 6 sections
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_document_structure(ctx))
    assert any("missing section: ## Whole-Book Synthesis" in str(r.message) for r in results)


def test_book_with_all_sections_has_no_missing_warning(tmp_path: Path) -> None:
    _project(tmp_path)
    sections = (
        "## Overview",
        "## Whole-Book Synthesis",
        "## Chapter Map",
        "## Key Themes",
        "## Relevance",
        "## Limitations",
        "## Follow-up",
    )
    _write_book(tmp_path, "\n" + "\n\ntext\n".join(sections) + "\n\ntext\n")
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_document_structure(ctx))
    assert not any("missing section" in str(r.message) for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/validate/test_checks_document_structure_book.py -v`
Expected: FAIL — no book branch exists, so the missing-section warning is never emitted.

- [ ] **Step 3: Add `_BOOK_SECTIONS` and the branch**

In `science/src/science_tool/validate/checks/document_structure.py`, after the
`_PAPER_SECTIONS` line:

```python
_PAPER_SECTIONS = ("## Key Contribution", "## Methods", "## Key Findings", "## Relevance")
_BOOK_SECTIONS = (
    "## Overview",
    "## Whole-Book Synthesis",
    "## Chapter Map",
    "## Key Themes",
    "## Relevance",
    "## Limitations",
    "## Follow-up",
)
```

In `check_document_structure`, after the papers block:

```python
    papers_dir = ctx.project_root / "entities" / "papers"
    if papers_dir.is_dir():
        yield from _check_documents(ctx, papers_dir, _PAPER_SECTIONS)
    books_dir = ctx.project_root / "entities" / "books"
    if books_dir.is_dir():
        yield from _check_documents(ctx, books_dir, _BOOK_SECTIONS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_checks_document_structure_book.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
cd /home/keith/d/science
git add science/src/science_tool/validate/checks/document_structure.py science/tests/validate/test_checks_document_structure_book.py
git commit -m "feat(validate): check book-overview required sections under entities/books"
```

---

## Task 8: Confirm chapter notes under `doc/books/` are NOT validated

**Files:**
- Test only: `science/tests/validate/test_book_chapter_notes_unvalidated.py` (create)

This task is a guard test — no production code should be needed if Tasks 1–7 are correct
(chapter notes have no registered `type:` and live outside any entity home). If the test
fails, the fix is in whichever check over-reaches; do not "fix" it by registering chapters.

- [ ] **Step 1: Write the test**

Create `science/tests/validate/test_book_chapter_notes_unvalidated.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.document_structure import check_document_structure
from science_tool.validate.checks.entity_conformance import (
    check_entity_frontmatter_completeness,
    check_entity_location_coherence,
)
from science_tool.validate.context import ValidateContext


def _project_with_chapter_note(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    d = tmp_path / "doc" / "books" / "Kelly1982"
    d.mkdir(parents=True, exist_ok=True)
    # Lightweight chapter note: provenance frontmatter, but NO registered `type:`.
    (d / "ch01-intro.md").write_text(
        "---\nbook: Kelly1982\nchapter: 1\npages: '1-24'\n---\n"
        "## Summary\n\ntext\n## Key Concepts\n\ntext\n",
        encoding="utf-8",
    )


def test_chapter_note_raises_no_validation_warnings(tmp_path: Path) -> None:
    _project_with_chapter_note(tmp_path)
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = (
        list(check_document_structure(ctx))
        + list(check_entity_frontmatter_completeness(ctx))
        + list(check_entity_location_coherence(ctx))
    )
    offenders = [r for r in results if "ch01-intro" in str(r.path) and r.severity.name != "INFO"]
    assert offenders == [], f"chapter note should not be validated, got: {offenders}"
```

> Confirm the importable names `check_entity_frontmatter_completeness` and
> `check_entity_location_coherence` in `entity_conformance.py` before running; adjust to the
> actual function names if they differ.

- [ ] **Step 2: Run the test**

Run: `cd science && uv run pytest tests/validate/test_book_chapter_notes_unvalidated.py -v`
Expected: PASS (the note is invisible to all three checks). If it FAILS, a check is
over-reaching into `doc/books/`; narrow that check, then re-run.

- [ ] **Step 3: Commit**

```bash
cd /home/keith/d/science
git add science/tests/validate/test_book_chapter_notes_unvalidated.py
git commit -m "test(validate): guard that book chapter notes are not entity-validated"
```

---

## Task 9: Parse the BibTeX entry type into `BibEntry`

**Files:**
- Modify: `science/src/science_tool/bibliography.py` (`BibEntry` ~line 84; new regex ~line 14; `load_bib_entries` ~line 143)
- Test: `science/tests/test_bibliography_entries.py`

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_bibliography_entries.py` (reuses the module's `_write_bib` helper):

```python
def test_load_bib_entries_captures_entry_type(tmp_path: Path) -> None:
    _write_bib(
        tmp_path,
        "@book{Kelly1982,\n  title = {Information Rate},\n  year = {1982},\n}\n\n"
        "@article{Smith2024,\n  title = {Cells},\n  year = {2024},\n}\n",
    )
    entries = load_bib_entries(tmp_path)
    assert entries["Kelly1982"].entry_type == "book"
    assert entries["Smith2024"].entry_type == "article"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_bibliography_entries.py::test_load_bib_entries_captures_entry_type -v`
Expected: FAIL — `AttributeError: 'BibEntry' object has no attribute 'entry_type'`.

- [ ] **Step 3: Add the field, a dedicated regex, and populate it**

In `science/src/science_tool/bibliography.py`:

Add a new module-level regex below the existing `_BIBTEX_ENTRY_RE` (leave that one and its
three call sites untouched — this avoids renumbering capture groups):

```python
_BIBTEX_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")
_BIBTEX_ENTRY_TYPED_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
```

Add `entry_type` to `BibEntry`:

```python
@dataclass(frozen=True)
class BibEntry:
    """One balanced bibliography entry — the subset Phase 4b materializes."""

    key: str
    entry_type: str = "misc"
    title: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
```

In `load_bib_entries`, switch the loop to the typed regex and capture both groups:

```python
    for match in _BIBTEX_ENTRY_TYPED_RE.finditer(text):
        entry_type = match.group(1).lower()
        key = match.group(2)
        span = _entry_span(text, key)
        if span is None:
            continue  # unbalanced/truncated — cannot be "backed", excluded
        block = text[span[0] : span[1]]
        year_raw = _field_value(block, "year")
        year_int = int(year_raw) if year_raw is not None and year_raw.isdigit() else None
        year = year_int if year_int is not None and 1800 <= year_int <= 2200 else None
        entries[key] = BibEntry(
            key=key,
            entry_type=entry_type,
            title=_field_value(block, "title"),
            year=year,
            doi=_field_value(block, "doi"),
            url=_field_value(block, "url"),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_bibliography_entries.py -v`
Expected: PASS (new test + all existing bibliography tests — the default `BibEntry()`
construction stays valid because `entry_type` has a default).

- [ ] **Step 5: Commit**

```bash
cd /home/keith/d/science
git add science/src/science_tool/bibliography.py science/tests/test_bibliography_entries.py
git commit -m "feat(bib): capture BibTeX entry_type in BibEntry"
```

---

## Task 10: Materialize `@book` entries as `book:` nodes

**Files:**
- Modify: `science/src/science_tool/graph/storage_adapters/bib.py` (`load_raw`, ~line 44)
- Test: `science/tests/graph/test_bib_adapter.py`

- [ ] **Step 1: Write the failing test**

Add to `science/tests/graph/test_bib_adapter.py` (reuses the module's `_write_bib` helper):

```python
def test_bib_adapter_materializes_book_as_book_kind(tmp_path: Path) -> None:
    _write_bib(
        tmp_path,
        "@book{Kelly1982,\n  title = {Information Rate},\n  year = {1982},\n}\n"
        "@article{Smith2024,\n  title = {Cells},\n  year = {2024},\n}\n",
    )
    adapter = BibAdapter()
    refs = adapter.discover(tmp_path)
    by_key = {adapter.load_raw(r)["bibkey"]: adapter.load_raw(r) for r in refs}
    assert by_key["Kelly1982"]["kind"] == "book"
    assert by_key["Kelly1982"]["id"] == "book:Kelly1982"
    assert by_key["Smith2024"]["kind"] == "paper"
    assert by_key["Smith2024"]["id"] == "paper:Smith2024"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/graph/test_bib_adapter.py::test_bib_adapter_materializes_book_as_book_kind -v`
Expected: FAIL — Kelly1982 materializes as `paper:Kelly1982` (hard-coded).

- [ ] **Step 3: Derive kind from entry_type**

In `science/src/science_tool/graph/storage_adapters/bib.py`, in `load_raw`, replace the
hard-coded kind/id with a small explicit map:

```python
        entry = self._entries[self._keys_by_line[ref.line]]
        kind = "book" if entry.entry_type == "book" else "paper"
        raw: dict[str, Any] = {
            "kind": kind,
            "id": f"{kind}:{entry.key}",
            "title": entry.title or entry.key,
            "bibkey": entry.key,
            "file_path": _BIB_REL,
        }
```

(Leave the `year`/`doi`/`url` tail of the method unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/graph/test_bib_adapter.py -v`
Expected: PASS (new test + the existing `@article` → `paper:` test still green).

- [ ] **Step 5: Commit**

```bash
cd /home/keith/d/science
git add science/src/science_tool/graph/storage_adapters/bib.py science/tests/graph/test_bib_adapter.py
git commit -m "feat(graph): materialize @book bib entries as book: nodes"
```

---

## Task 11: Add the `pypdf` dependency and the `book_split` module

**Files:**
- Modify: `science/pyproject.toml` (dependencies)
- Create: `science/src/science_tool/book_split.py`
- Test: `science/tests/test_book_split.py` (create)

- [ ] **Step 1: Add the dependency**

Run:

```bash
cd /home/keith/d/science/science && uv add pypdf
```

Expected: `pypdf` added to `[project.dependencies]` in `science/pyproject.toml` and locked.

- [ ] **Step 2: Write the failing test**

Create `science/tests/test_book_split.py`. It builds real PDFs with `pypdf`'s writer so no
fixtures are needed:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from science_tool.book_split import BookSplitError, split_book


def _make_pdf(path: Path, n_pages: int, outline: list[tuple[str, int]]) -> None:
    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=72, height=72)
    for title, page in outline:
        writer.add_outline_item(title, page)
    with path.open("wb") as fh:
        writer.write(fh)


def _make_pdf_with_parts(path: Path, n_pages: int) -> None:
    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=72, height=72)
    p1 = writer.add_outline_item("Part I", 0)
    writer.add_outline_item("Chapter 1", 0, parent=p1)
    writer.add_outline_item("Chapter 2", 4, parent=p1)
    p2 = writer.add_outline_item("Part II", 8)
    writer.add_outline_item("Chapter 3", 8, parent=p2)
    with path.open("wb") as fh:
        writer.write(fh)


def test_split_flat_outline(tmp_path: Path) -> None:
    pdf = tmp_path / "flat.pdf"
    _make_pdf(pdf, 30, [("Introduction", 0), ("Methods", 10), ("Results", 20)])
    chapters = split_book(pdf)
    assert [c.n for c in chapters] == [1, 2, 3]
    assert chapters[0].title == "Introduction"
    assert chapters[0].start_page == 1   # 1-based
    assert chapters[0].end_page == 10    # next start (11) - 1
    assert chapters[2].end_page == 30    # last runs to final page
    assert all(c.part is None for c in chapters)


def test_split_detects_parts(tmp_path: Path) -> None:
    pdf = tmp_path / "parts.pdf"
    _make_pdf_with_parts(pdf, 12)
    chapters = split_book(pdf)
    titles = [c.title for c in chapters]
    assert titles == ["Chapter 1", "Chapter 2", "Chapter 3"]  # parts are containers, not chapters
    assert chapters[0].part == "Part I"
    assert chapters[2].part == "Part II"
    assert chapters[0].level == 1


def test_no_outline_raises(tmp_path: Path) -> None:
    pdf = tmp_path / "bare.pdf"
    _make_pdf(pdf, 5, [])  # pages, no outline
    with pytest.raises(BookSplitError, match="no outline"):
        split_book(pdf)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_book_split.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.book_split'`.

- [ ] **Step 4: Implement `book_split.py`**

Create `science/src/science_tool/book_split.py`:

```python
"""Split a book PDF into a chapter manifest from its embedded outline/bookmarks.

Used by the `science book-split` CLI and the /review-books command. Pure outline
extraction — no page rendering. Fails early (BookSplitError) when the PDF has no
outline, which is the caller's signal to fall back to reading the ToC pages.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from pypdf import PdfReader


class BookSplitError(Exception):
    """Raised when a book PDF cannot be split (e.g. no outline/bookmarks)."""


@dataclass(frozen=True)
class ChapterEntry:
    n: int
    title: str
    start_page: int  # 1-based, inclusive
    end_page: int  # 1-based, inclusive
    level: int
    part: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _collect_leaves(nodes: list, reader: PdfReader, part: str | None = None) -> list[dict]:
    """Walk the (possibly nested) outline and return leaf entries in document order.

    pypdf represents hierarchy as: a Destination followed immediately by a list of
    its children. Such a destination is a *Part* (container), not a chapter; its
    children are the chapters. A destination with no following list is a chapter leaf.
    """
    leaves: list[dict] = []
    i = 0
    while i < len(nodes):
        node = nodes[i]
        if isinstance(node, list):
            # A list with no preceding destination at this level — recurse, same part.
            leaves.extend(_collect_leaves(node, reader, part))
            i += 1
            continue
        title = str(node.title).strip()
        start = reader.get_destination_page_number(node) + 1  # 0-based -> 1-based
        has_children = i + 1 < len(nodes) and isinstance(nodes[i + 1], list)
        if has_children:
            leaves.extend(_collect_leaves(nodes[i + 1], reader, part=title))
            i += 2
        else:
            leaves.append({"title": title, "start_page": start, "part": part})
            i += 1
    return leaves


def split_book(pdf_path: str | Path) -> list[ChapterEntry]:
    reader = PdfReader(str(pdf_path))
    try:
        outline = reader.outline
    except Exception as exc:  # pypdf raises various errors on malformed outlines
        raise BookSplitError(f"could not read outline: {exc}") from exc
    if not outline:
        raise BookSplitError("no outline/bookmarks in PDF")

    leaves = _collect_leaves(outline, reader)
    if not leaves:
        raise BookSplitError("no chapters found in outline")

    total_pages = len(reader.pages)
    chapters: list[ChapterEntry] = []
    for idx, leaf in enumerate(leaves):
        start = leaf["start_page"]
        end = leaves[idx + 1]["start_page"] - 1 if idx + 1 < len(leaves) else total_pages
        if end < start:
            end = start
        chapters.append(
            ChapterEntry(
                n=idx + 1,
                title=leaf["title"],
                start_page=start,
                end_page=end,
                level=1 if leaf["part"] else 0,
                part=leaf["part"],
            )
        )
    return chapters
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_book_split.py -v`
Expected: PASS (all three).

- [ ] **Step 6: Commit**

```bash
cd /home/keith/d/science
git add science/pyproject.toml science/uv.lock science/src/science_tool/book_split.py science/tests/test_book_split.py
git commit -m "feat(cli): add pypdf dep and book_split outline-to-manifest module"
```

---

## Task 12: Expose `science book-split` on the CLI

**Files:**
- Modify: `science/src/science_tool/cli.py` (new `@main.command("book-split")`, near the `paper-fetch` command ~line 4394)
- Test: `science/tests/test_book_split_cli.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_book_split_cli.py` (uses click's `CliRunner`; rebuilds a small
PDF inline):

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from pypdf import PdfWriter

from science_tool.cli import main


def _make_pdf(path: Path, n_pages: int, outline: list[tuple[str, int]]) -> None:
    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=72, height=72)
    for title, page in outline:
        writer.add_outline_item(title, page)
    with path.open("wb") as fh:
        writer.write(fh)


def test_book_split_cli_emits_json(tmp_path: Path) -> None:
    pdf = tmp_path / "b.pdf"
    _make_pdf(pdf, 20, [("Intro", 0), ("Body", 10)])
    result = CliRunner().invoke(main, ["book-split", str(pdf), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [c["title"] for c in data] == ["Intro", "Body"]
    assert data[0]["start_page"] == 1


def test_book_split_cli_no_outline_exits_nonzero(tmp_path: Path) -> None:
    pdf = tmp_path / "bare.pdf"
    _make_pdf(pdf, 3, [])
    result = CliRunner().invoke(main, ["book-split", str(pdf), "--json"])
    assert result.exit_code != 0
    assert "no outline" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_book_split_cli.py -v`
Expected: FAIL — `No such command 'book-split'`.

- [ ] **Step 3: Add the command**

In `science/src/science_tool/cli.py`, add near the `paper-fetch` command (mirror its
structure: lazy import inside the function, JSON output via `click.echo`):

```python
@main.command("book-split")
@click.argument("pdf", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit the chapter manifest as JSON.")
def book_split_cmd(pdf: Path, as_json: bool) -> None:
    """Extract a chapter manifest from a book PDF's outline/bookmarks.

    Intended for the /review-books command: call this first; on a non-zero exit
    with 'no outline', fall back to reading the book's table-of-contents pages.
    """
    import json as _json

    from science_tool.book_split import BookSplitError, split_book

    try:
        chapters = split_book(pdf)
    except BookSplitError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = [c.to_dict() for c in chapters]
    if as_json:
        click.echo(_json.dumps(payload, indent=2))
    else:
        for c in chapters:
            part = f"  [{c.part}]" if c.part else ""
            click.echo(f"{c.n:>3}. {c.title}  (pp. {c.start_page}-{c.end_page}){part}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_book_split_cli.py -v`
Expected: PASS (both — `click.ClickException` produces a non-zero exit and an `Error: …`
message containing "no outline").

- [ ] **Step 5: Commit**

```bash
cd /home/keith/d/science
git add science/src/science_tool/cli.py science/tests/test_book_split_cli.py
git commit -m "feat(cli): add 'science book-split' command"
```

---

## Task 13: Author the `book-chapter-researcher` subagent

**Files:**
- Create: `agents/book-chapter-researcher.md`

Markdown agent definition (no automated test). Mirror `agents/paper-researcher.md`'s
frontmatter and tone, scoped to one chapter.

- [ ] **Step 1: Write the agent file**

Create `agents/book-chapter-researcher.md`:

```markdown
---
name: book-chapter-researcher
description: Summarize a single book chapter into a lightweight note under doc/books/<citekey>/. Accepts a PDF path, a page range, and chapter metadata. Returns the chapter note path. Use this to offload per-chapter reading from a more expensive orchestrator during /review-books.
model: claude-sonnet-4-6
tools: Read, Write, Edit, Glob, Grep, Bash
---

# Book Chapter Researcher

You are a dispatched subagent. Your sole job is to read ONE chapter of a book PDF and write
one lightweight chapter note, then report back.

## Inputs (from the orchestrator prompt)

- `pdf_path` — absolute path to the book PDF.
- `start_page`, `end_page` — 1-based inclusive page range for your chapter.
- `n`, `title` — chapter number and title.
- `citekey` — the book's BibTeX key (e.g. `Kelly1982`).
- `out_path` — where to write the note, e.g. `doc/books/<citekey>/chNN-<slug>.md`.

## Workflow

1. Read only your page range: `Read` the PDF with `pages="<start_page>-<end_page>"`. Do not
   read the whole book; you were dispatched to save that cost.
2. Write `out_path` with this exact lightweight structure (provenance frontmatter, then the
   four standard headings — NOT a registered entity type):

   ```markdown
   ---
   book: <citekey>
   chapter: <n>
   pages: "<start_page>-<end_page>"
   ---

   # <n>. <title>

   ## Summary
   <2-4 sentences: what this chapter establishes.>

   ## Key Concepts
   <bullet list of the chapter's load-bearing ideas/definitions.>

   ## Notable Claims
   <specific claims/results that matter, each verifiable from the pages you read.>

   ## Relevance
   <how this chapter connects to the project's questions/hypotheses, if at all.>
   ```

3. Mark anything you could not verify from your pages as `[UNVERIFIED]`; mark image-only or
   unreadable content as `[INACCESSIBLE]`. Do not invent claims — an incomplete note beats a
   fabricated one.

## Scope discipline

- Summarize ONE chapter. Do not read other chapters, edit the book overview, touch
  `references.bib`, reserve questions, or commit. Those are the orchestrator's job.

## Reporting back

Return ≤120 words: the chapter number, the written `out_path`, and any `[UNVERIFIED]` /
`[INACCESSIBLE]` flags worth the orchestrator's attention. Do not paste the note back.
```

- [ ] **Step 2: Sanity-check frontmatter**

Run: `cd /home/keith/d/science && head -8 agents/book-chapter-researcher.md`
Expected: a valid YAML frontmatter block with `name`, `model: claude-sonnet-4-6`, and a
`tools:` line (no `WebFetch`/`WebSearch` — books are local PDFs).

- [ ] **Step 3: Commit**

```bash
cd /home/keith/d/science
git add agents/book-chapter-researcher.md
git commit -m "feat(agents): add book-chapter-researcher subagent"
```

---

## Task 14: Author the `book-synthesizer` subagent

**Files:**
- Create: `agents/book-synthesizer.md`

- [ ] **Step 1: Write the agent file**

Create `agents/book-synthesizer.md`:

```markdown
---
name: book-synthesizer
description: Synthesize per-chapter notes into the book overview entity (entities/books/<citekey>.md) and, adaptively, sub-topic part rollups. Use after all book-chapter-researcher subagents return during /review-books.
model: claude-opus-4-8
tools: Read, Write, Edit, Glob, Grep, Bash
---

# Book Synthesizer

You are a dispatched subagent. Your job is the cross-chapter judgment that the chapter
subagents could not do: read every chapter note and produce the book overview entity, plus
optional Part rollups.

## Inputs (from the orchestrator prompt)

- `citekey`, `title`, bibliographic metadata (authors/year/publisher/isbn).
- `chapter_notes` — the list of `doc/books/<citekey>/chNN-*.md` paths.
- `parts` — the Part structure from the manifest (may be empty/flat).

## Workflow

1. Read all chapter notes.
2. Write the book overview entity to `entities/books/<citekey>.md` from the packaged `book`
   template's section set. Required sections (must all be present): `## Overview`,
   `## Whole-Book Synthesis`, `## Chapter Map`, `## Key Themes`, `## Relevance`,
   `## Limitations`, `## Follow-up`. Frontmatter: `id: book:<citekey>`, `type: book`,
   `title`, `status: active`, `created`, `updated`, `source_refs: [cite:<citekey>]`,
   `related: []` (the orchestrator fills hypothesis/question links afterward).
   - The Chapter Map is a table linking each chapter to
     `../../doc/books/<citekey>/chNN-*.md` with a one-line gist.
3. **Adaptive Part rollups:** if `parts` is non-empty OR there are more than ~8 chapters,
   write one `doc/books/<citekey>/part-N-<slug>.md` per Part summarizing its chapters.
   Otherwise skip Part rollups entirely.
4. Carry forward `[UNVERIFIED]`/`[INACCESSIBLE]` markers from chapter notes where the
   synthesis depends on them. Do not introduce claims absent from the chapter notes.

## Scope discipline

- Do NOT run `science bib add`, reserve questions, or commit — the orchestrator owns those
  one-per-book steps. You only write the overview entity and any Part rollups.

## Reporting back

Return ≤120 words: the overview entity path, the list of any Part rollup paths written
(or "no parts — flat book"), and any cross-chapter tensions worth the orchestrator's notice.
```

- [ ] **Step 2: Sanity-check frontmatter**

Run: `cd /home/keith/d/science && head -8 agents/book-synthesizer.md`
Expected: valid frontmatter, `model: claude-opus-4-8`.

- [ ] **Step 3: Commit**

```bash
cd /home/keith/d/science
git add agents/book-synthesizer.md
git commit -m "feat(agents): add book-synthesizer subagent"
```

---

## Task 15: Author the `/review-books` command

**Files:**
- Create: `commands/review-books.md`

- [ ] **Step 1: Write the command file**

Create `commands/review-books.md` (mirrors `commands/research-papers.md`'s orchestrator /
subagent split and the design doc's §5 flow):

```markdown
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
   `doc/books/<citekey>/` already exists. If so, ask the user to **overwrite / skip /
   supplement**, and honor that choice. Never clobber prior notes silently.
5. **Confirmation gate.** Show the user the chapter count + titles (and detected Parts).
   Proceed only on confirmation — this guards against fanning out on a bad split.
6. **Fan out.** Create `doc/books/<citekey>/`. Dispatch one `book-chapter-researcher` per
   chapter **in parallel** (multiple Agent calls in one message), each given
   `{pdf_path, start_page, end_page, n, title, citekey, out_path}` where `out_path` is
   `doc/books/<citekey>/ch<NN>-<slug>.md`.
7. **Synthesize.** When all chapter subagents return, dispatch ONE `book-synthesizer` with
   the citekey, metadata, the chapter-note paths, and the Part structure. It writes
   `entities/books/<citekey>.md` and any `doc/books/<citekey>/part-N-*.md` rollups.
8. **Integrate (orchestrator, once).**
   - Add the BibTeX entry — **never** edit `references.bib` directly:
     ```bash
     uv run science bib add --project-root . <<'EOF'
     @book{<citekey>, title={...}, author={...}, year={...}, publisher={...} }
     EOF
     ```
   - Reserve any new questions via `uv run science question reserve --slug "<slug>"
     --title "<title>" --source-refs "<citekey>" --json` (never write `doc/questions/`
     directly).
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
```

- [ ] **Step 2: Sanity-check**

Run: `cd /home/keith/d/science && head -4 commands/review-books.md`
Expected: a `---` frontmatter block with a `description:` line (matches the other
`commands/*.md`).

- [ ] **Step 3: Commit**

```bash
cd /home/keith/d/science
git add commands/review-books.md
git commit -m "feat(commands): add /review-books orchestrator command"
```

---

## Task 16: Full-suite regression + end-to-end readiness

**Files:** none (verification only)

- [ ] **Step 1: Run the model test suite**

Run: `cd science/model && uv run pytest -q`
Expected: PASS (adding `BOOK`, `BookEntity`, and the core-profile kind must not break
existing model tests — watch for any enum-exhaustiveness or profile-snapshot test that now
needs `book`; if a snapshot test fails, update the snapshot per its documented procedure).

- [ ] **Step 2: Run the tool test suite**

Run: `cd science && uv run pytest -q`
Expected: PASS (new book tests + all existing tests). If a validate snapshot test
(`-m snapshot`, normally excluded) covers document_structure, note it for a separate
snapshot-update pass; the default run excludes it.

- [ ] **Step 3: Smoke-test the CLI against a real book**

Run: `cd /home/keith/d/science && uv run science book-split ~/downloads/nature-pdfs/Kelly1982.pdf`
Expected: a printed chapter list (or a clear "no outline" error, in which case the command's
ToC fallback path applies). This is the live input for downstream `task:t688`.

- [ ] **Step 4: Final commit (if any snapshot/lock updates were needed)**

```bash
cd /home/keith/d/science
git add -A
git commit -m "chore(review-books): regression fixups (snapshots/lock)"
```

> Do NOT run the end-to-end `/review-books` here — executing it against Kelly1982 is
> `task:t688`, downstream of this build. This task only confirms the machinery is green and
> the CLI runs.

---

## Self-Review Notes (for the implementer)

- **Spec coverage:** §3a→Tasks 11–12; §3b→Tasks 1–5; §3b.6 review-state→Task 2; §3c
  section validation→Task 7; §3d bib layer→Tasks 9–10; §6 dual templates→Task 6;
  §5 flow + gates→Task 15; chapter-note exclusion→Task 8; agents→Tasks 13–14.
- **Verify-before-write callouts:** Tasks 4, 5, 6, 8 contain accessor names
  (`resolve_path_policy`, `entity_class_for`/`model_for`, template `fields` keys, conformance
  check function names) that must be confirmed against the real modules before writing the
  test — each step says so inline. These are the only non-verbatim spots; everything else is
  grounded in quoted code.
- **Type consistency:** `BookEntity` (Tasks 1, 5), `entry_type` field (Tasks 9, 10),
  `ChapterEntry`/`split_book`/`BookSplitError` (Tasks 11, 12), `_BOOK_SECTIONS` (Tasks 6, 7)
  are used with identical names across tasks.
- **Ordering:** model → tool wiring → templates/validation → bib → CLI → markdown → regression.
  Each task is independently committable and leaves the suite green.
```
