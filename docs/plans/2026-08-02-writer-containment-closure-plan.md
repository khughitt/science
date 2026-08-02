# Writer Containment Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** No writer may turn a base-shape-valid entity record into an invalid one, and a promotion batch that would do so writes nothing at all.

**Architecture:** Two sequenced slices. Slice 1 (Tasks 1–5) makes the two kind-agnostic renderers in `entities.py` text-in/text-out and makes them **refuse the one forbidden transition** (base-valid → base-invalid), then gives every workflow that reaches them a translated — and where a batch exists, aggregated — error. Slice 2 (Tasks 6–10) converts the three workflows that write as they go into plan-then-apply: a complete plan of post-images is built, every candidate-local refusal is collected, and only then is anything published.

**Design of record:** [`docs/plans/2026-08-02-writer-containment-closure-design.md`](2026-08-02-writer-containment-closure-design.md). Section references below (§2.2, §4.3, …) point into it.

**Tech Stack:** Python 3.13, Pydantic v2, PyYAML, Click + `CliRunner`, pytest. Package root is `science/` — all `uv` commands run from there.

## Global Constraints

- **All `uv` commands run from `science/`**, never the repo root. There is no root `pyproject.toml`.
- **Run scoped test selections**, not the full suite. The full CLI suite is ~12k tests / ~7 minutes and exceeds the default 120s command timeout. Each task names the exact selection to run.
- **Never run two pytest suites concurrently in the same worktree** — they race on shared test-output paths.
- **`pytest -q` is wrong here**: the package's `addopts` already carries `-q`, so adding another yields `-qq` and suppresses the summary line. Run bare `pytest`.
- Lint and types, from `science/`: `uv run ruff check` (line-length 120) and `uv run pyright`. Pyright is configured once by `pyrightconfig.json` at the repo root; test directories are **not** type-checked.
- Conventional commits. **No AI-attribution trailer or footer** on any commit, PR, or comment.
- Composition over inheritance; explicit over defensive; fail early rather than silent fallback.
- **No "legacy" or "compatibility" layers**, and no `Unified` prefix on component names.
- In documentation and code, write filepaths as `~/d/...` or repo-relative — never `/home/keith/...` or `/mnt/ssd/Dropbox/...`.
- **The forbidden transition is exactly one**: pre-image valid AND post-image invalid → refuse. `invalid → invalid` and `invalid → valid` both write. This branch performs **no intentional backfill** (§2).
- **Validate the post-image after rendering AND reparsing it** — never the in-memory mapping (§2.1). That round trip is what catches a date the YAML dumper emitted as a bare scalar.
- **Base shape only.** `EntityValidator().validate_persisted_base_shape`. No typed certification on these paths (§2, §6).
- The 183 records that already fail base shape are **not** repaired by this branch (§6).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/science_tool/annotation/planned_edits.py` (new) | The shared plan-then-apply vocabulary: `PlannedFileEdit`, its constructors, the CRLF-preserving reader, hashing, changed/no-op partitioning, `PlannedEditDriftError`, and `publish_edit` | 1, 6 |
| `src/science_tool/entities.py` | The two renderers become text-in/text-out and carry the degradation guard; `EntityDegradationError` lives here | 2, 3, 10 |
| `src/science_tool/dag/entity_frontmatter.py` | `publish_new_file` extracted from `create_entity_file` so planning and publishing can be separated | 6 |
| `src/science_tool/annotation/proposition_reconciliation_apply.py` | Loses the hoisted helpers; gains per-action refusal aggregation | 1, 4 |
| `src/science_tool/annotation/proposition_resynthesis_apply.py` | Imports the hoisted helpers from their new home | 1 |
| `src/science_tool/annotation/promote.py` | `PromotionTarget.mint` → `plan_mint`; `apply_candidates` becomes plan-then-apply with a planned sidecar | 4, 7, 8 |
| `src/science_tool/annotation/prose_decomposition.py` | `record_promotion` gains a pure planning sibling that returns index text | 9 |
| `src/science_tool/annotation/prose_promote.py`, `prose_promotion_batch.py` | Both become plan-then-apply over the shared vocabulary | 10 |
| `tests/test_planned_edits.py` (new) | The shared vocabulary's own tests, including drift and CRLF | 1, 6 |
| `tests/test_entity_writer.py` | The four-transition matrix, the round trip, the signature change | 2, 3 |
| `tests/test_hypothesis_consumers.py` | The anticipatory guard's roster and premise | 5 |

---

# Slice 1 — the guard

### Task 1: Hoist the shared edit vocabulary

`proposition_resynthesis_apply.py:13-21` already imports six private names from `proposition_reconciliation_apply.py` across a module boundary. That import list defines the hoist set by evidence rather than by taste (§3.2). This task moves exactly those six and fixes one latent defect in `_current_text`.

**Files:**
- Create: `science/src/science_tool/annotation/planned_edits.py`
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_apply.py:39-45,157-200`
- Modify: `science/src/science_tool/annotation/proposition_resynthesis_apply.py:13-21`
- Create: `science/tests/test_planned_edits.py`

**Interfaces:**
- Produces: `PlannedFileEdit` (frozen dataclass: `path: Path`, `reason: str`, `before_sha256: str`, `after_sha256: str`, `final_text: str`, `changed: bool`), `current_text(path: Path) -> str`, `sha256_text(text: str) -> str`, `path_string(path: Path) -> str`, `plan_update(path: Path, final_text: str, reason: str) -> PlannedFileEdit`, `changed_and_noop_paths(edits: Sequence[PlannedFileEdit]) -> tuple[tuple[str, ...], tuple[str, ...]]`.
- The hoisted names lose their leading underscore because they are now a public module boundary. `_changed_and_noop_paths_from_path_changes` and `_live_annotation_index` and `CanonicalizationPreflight` **stay in reconciliation** — nothing else imports them and they serve reconciliation's own per-action map.

- [ ] **Step 1: Write the failing test for CRLF preservation**

Create `science/tests/test_planned_edits.py`:

```python
from pathlib import Path

from science_tool.annotation.planned_edits import (
    PlannedFileEdit,
    changed_and_noop_paths,
    current_text,
    plan_update,
    sha256_text,
)


def test_current_text_preserves_crlf(tmp_path: Path):
    """`Path.read_text()` applies universal-newline translation, which would rewrite
    bytes the edit never intended -- and the round-trip guard would then certify the
    rewrite as correct. The preserving reader at entities.py:1920-1923 is the precedent."""
    target = tmp_path / "record.md"
    target.write_bytes(b"---\r\nid: proposition:x\r\n---\r\nbody\r\n")

    assert current_text(target) == "---\r\nid: proposition:x\r\n---\r\nbody\r\n"


def test_plan_update_reports_unchanged_when_text_matches(tmp_path: Path):
    target = tmp_path / "record.md"
    target.write_text("same\n", encoding="utf-8")

    edit = plan_update(target, "same\n", "noop")

    assert edit.changed is False
    assert edit.before_sha256 == edit.after_sha256 == sha256_text("same\n")


def test_changed_and_noop_paths_partitions(tmp_path: Path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("one\n", encoding="utf-8")
    b.write_text("two\n", encoding="utf-8")

    changed, noop = changed_and_noop_paths(
        [plan_update(a, "ONE\n", "r"), plan_update(b, "two\n", "r")]
    )

    assert changed == (a.as_posix(),)
    assert noop == (b.as_posix(),)


def test_planned_file_edit_is_frozen(tmp_path: Path):
    target = tmp_path / "a.md"
    target.write_text("x\n", encoding="utf-8")
    edit = plan_update(target, "y\n", "r")
    assert isinstance(edit, PlannedFileEdit)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py
```

Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.annotation.planned_edits'`.

- [ ] **Step 3: Create the module**

Create `science/src/science_tool/annotation/planned_edits.py`:

```python
"""The shared plan-then-apply edit vocabulary.

Reconciliation grew this vocabulary first, and resynthesis reached across a module
boundary for six of its private names. This module owns them so no generic helper
stays owned by one workflow.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class PlannedFileEdit:
    path: Path
    reason: str
    before_sha256: str
    after_sha256: str
    final_text: str
    changed: bool


def path_string(path: Path) -> str:
    return path.as_posix()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def current_text(path: Path) -> str:
    """Read a planning pre-image WITHOUT universal-newline translation.

    `Path.read_text()` normalizes CRLF to LF before planning ever runs, so a CRLF body
    would be silently rewritten by an edit that never touched it -- and the round-trip
    guard would certify that rewrite as correct. `entities.py`'s preserving parser reads
    the same way.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def plan_update(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    before = current_text(path)
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=sha256_text(before),
        after_sha256=sha256_text(final_text),
        final_text=final_text,
        changed=before != final_text,
    )


def changed_and_noop_paths(
    edits: Sequence[PlannedFileEdit],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    changed = tuple(path_string(edit.path) for edit in edits if edit.changed)
    noop = tuple(path_string(edit.path) for edit in edits if not edit.changed)
    return changed, noop
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py
```

Expected: 4 passed.

- [ ] **Step 5: Repoint reconciliation**

In `science/src/science_tool/annotation/proposition_reconciliation_apply.py`:

1. Delete the `PlannedFileEdit` dataclass (currently `:39-45`) and the four helpers `_path_string`, `_sha256_text`, `_current_text`, `_changed_and_noop_paths`, `_edit` (currently `:157-200`).
2. Add the import:

```python
from science_tool.annotation.planned_edits import (
    PlannedFileEdit,
    changed_and_noop_paths,
    current_text,
    path_string,
    plan_update,
    sha256_text,
)
```

3. Rename every in-module use: `_path_string(` → `path_string(`, `_sha256_text(` → `sha256_text(`, `_current_text(` → `current_text(`, `_changed_and_noop_paths(` → `changed_and_noop_paths(`, `_edit(` → `plan_update(`.

**Keep** `_changed_and_noop_paths_from_path_changes` in this module — nothing else imports it and it serves reconciliation's per-action map.

- [ ] **Step 6: Repoint resynthesis**

In `science/src/science_tool/annotation/proposition_resynthesis_apply.py`, replace the cross-module import block at `:13-21` so the six generic names come from `planned_edits` and only reconciliation's own names (if any remain) come from reconciliation:

```python
from science_tool.annotation.planned_edits import (
    PlannedFileEdit,
    changed_and_noop_paths,
    current_text,
    path_string,
    plan_update,
    sha256_text,
)
```

Rename the uses in this module the same way. `_new_or_existing_edit` stays here — it is resynthesis's own constructor for a path that may not exist yet.

- [ ] **Step 7: Run the affected suites**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py tests/test_proposition_reconciliation_apply.py tests/test_proposition_reconciliation_cli.py tests/test_proposition_reconciliation_plan.py
```

Expected: all pass. Then:

```bash
cd science && uv run --frozen pytest -k resynthesis
```

Expected: all pass.

- [ ] **Step 8: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/annotation/planned_edits.py \
        science/src/science_tool/annotation/proposition_reconciliation_apply.py \
        science/src/science_tool/annotation/proposition_resynthesis_apply.py \
        science/tests/test_planned_edits.py
git commit -m "refactor(annotation): hoist the shared planned-edit vocabulary"
```

---

### Task 2: Renderers become text-in / text-out

Both renderers currently take a `file_path` and read their own pre-image. Composition (§4.6) is impossible under that signature, because every edit would re-read the unmodified file. This task changes the signature only — the guard lands in Task 3.

**Files:**
- Modify: `science/src/science_tool/entities.py:477-534`
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_apply.py` (two renderer call sites)
- Modify: `science/src/science_tool/annotation/proposition_resynthesis_apply.py` (one renderer call site, in `_original_edit`)
- Test: `science/tests/test_entity_writer.py`

**Interfaces:**
- Consumes: `current_text` from `science_tool.annotation.planned_edits` (Task 1).
- Produces:

```python
def render_entity_source_refs(
    current_text: str,
    refs_to_append: Sequence[str],
    *,
    entity_path: Path,          # diagnostic only; no filesystem I/O
    as_of: date | None = None,
) -> tuple[str, bool]: ...


def render_entity_frontmatter_updates(
    current_text: str,
    updates: Mapping[str, object],
    *,
    entity_path: Path,          # diagnostic only; no filesystem I/O
    as_of: date | None = None,
) -> tuple[str, bool]: ...
```

`entity_path` is **required**, not defaulted to `None`: every refusal must be identifiable, and a planner that has text has a path, since it read the text from one. It is used only to build error messages — the renderer performs no filesystem I/O.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_entity_writer.py`:

```python
def test_render_entity_source_refs_takes_text_not_a_path(tmp_path: Path):
    text = (
        "---\n"
        "id: proposition:x\n"
        "kind: proposition\n"
        "title: a claim\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "---\n"
        "body\n"
    )

    rendered, changed = render_entity_source_refs(
        text,
        ["paper:new"],
        entity_path=tmp_path / "x.md",
        as_of=date(2026, 6, 16),
    )

    assert changed is True
    assert "paper:new" in rendered
    # No file was ever created: the renderer does no filesystem I/O.
    assert not (tmp_path / "x.md").exists()


def test_render_entity_frontmatter_updates_returns_input_text_when_unchanged(tmp_path: Path):
    text = (
        "---\n"
        "id: proposition:x\n"
        "kind: proposition\n"
        "title: a claim\n"
        "status: superseded\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "---\n"
        "body\n"
    )

    rendered, changed = render_entity_frontmatter_updates(
        text,
        {"status": "superseded"},
        entity_path=tmp_path / "x.md",
        as_of=date(2026, 6, 16),
    )

    assert changed is False
    assert rendered == text
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_entity_writer.py::test_render_entity_source_refs_takes_text_not_a_path
```

Expected: FAIL — the renderer tries to treat the string as a `Path` (`AttributeError: 'str' object has no attribute 'open'`).

- [ ] **Step 3: Change both signatures**

In `science/src/science_tool/entities.py`, replace the two renderers:

```python
def render_entity_source_refs(
    current_text: str,
    refs_to_append: Sequence[str],
    *,
    entity_path: Path,
    as_of: date | None = None,
) -> tuple[str, bool]:
    """Return rendered entity markdown after appending missing source refs.

    Text in, text out: the CALLER reads the pre-image. That is what lets a planner
    compose several edits to one path without each one re-reading the unmodified file.
    `entity_path` is diagnostic only -- this function performs no filesystem I/O.

    Existing refs keep their current order, new refs are appended in caller-provided
    order, exact strings are deduped, and updated advances only when the rendered
    content changes.
    """
    frontmatter, body = split_frontmatter(current_text)
    refs = list(frontmatter.get("source_refs") or [])
    changed = False
    for ref in refs_to_append:
        if ref in refs:
            continue
        refs.append(ref)
        changed = True
    if not changed:
        return (current_text, False)
    frontmatter["source_refs"] = refs
    frontmatter["updated"] = (as_of or date.today()).isoformat()
    return (_render_markdown(frontmatter, body), True)


def render_entity_frontmatter_updates(
    current_text: str,
    updates: Mapping[str, object],
    *,
    entity_path: Path,
    as_of: date | None = None,
) -> tuple[str, bool]:
    """Return rendered entity markdown after applying exact frontmatter updates.

    Text in, text out; `entity_path` is diagnostic only. See `render_entity_source_refs`.
    """
    frontmatter, body = split_frontmatter(current_text)
    changed = False
    for key, value in updates.items():
        if frontmatter.get(key) == value:
            continue
        frontmatter[key] = value
        changed = True
    if not changed:
        return (current_text, False)
    frontmatter["updated"] = (as_of or date.today()).isoformat()
    return (_render_markdown(frontmatter, body), True)
```

Note the unchanged branches now return `current_text` directly instead of re-reading the file, which also removes a redundant read.

- [ ] **Step 4: Update `append_entity_source_ref` to be the reading adapter**

Still in `entities.py`, immediately below:

```python
def append_entity_source_ref(file_path: Path, ref: str, *, as_of: date | None = None) -> bool:
    """Append ``ref`` to an existing entity file's ``source_refs`` frontmatter, preserving
    the body. Returns True if added, False if already present. Used by promotion LINK so a
    hand-authored proposition's prose is never clobbered. When a ref is added, `updated`
    advances to ``as_of`` (or today), matching other entity mutations.

    This is the read-render-write adapter for callers that still write as they go. It is
    deleted once the promotion and prose workflows plan their writes (slice 2).
    """
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    rendered, changed = render_entity_source_refs(
        text, [ref], entity_path=file_path, as_of=as_of
    )
    if not changed:
        return False
    _atomic_replace_text(file_path, rendered)
    return True
```

- [ ] **Step 5: Update the three production call sites**

In `proposition_reconciliation_apply.py`, the canonical-refs call (currently `:647`):

```python
        final_text, _changed = render_entity_source_refs(
            current_text(canonical_location.path),
            canonical_refs,
            entity_path=canonical_location.path,
            as_of=as_of,
        )
```

and the duplicate-supersession call (currently `:668`):

```python
            final_text, _changed = render_entity_frontmatter_updates(
                current_text(duplicate_location.path),
                {"status": "superseded", "superseded_by": canonical},
                entity_path=duplicate_location.path,
                as_of=as_of,
            )
```

In `proposition_resynthesis_apply.py`, inside `_original_edit` (currently `:493-498`):

```python
        location = find_entity(project_root, draft.original_proposition)
        final_text, _changed = render_entity_frontmatter_updates(
            current_text(location.path),
            updates,
            entity_path=location.path,
            as_of=as_of,
        )
```

- [ ] **Step 6: Update the existing test call sites**

Roughly a dozen calls across `tests/test_entity_writer.py`, `tests/test_proposition_resynthesis_apply.py` and `tests/test_hypothesis_consumers.py` pass a `Path` as the first argument. Find them:

```bash
cd science && grep -rn "render_entity_source_refs(\|render_entity_frontmatter_updates(" tests/
```

For each, read the file first and pass its text, e.g.:

```python
rendered, changed = render_entity_source_refs(
    dest.read_text(encoding="utf-8"), ["paper:x"], entity_path=dest, as_of=date(2026, 6, 16)
)
```

- [ ] **Step 7: Run the affected suites**

```bash
cd science && uv run --frozen pytest tests/test_entity_writer.py tests/test_hypothesis_consumers.py tests/test_proposition_reconciliation_apply.py tests/test_proposition_resynthesis_apply.py tests/test_annotation_promote.py tests/test_prose_promote.py tests/test_prose_promotion_batch.py
```

Expected: all pass.

- [ ] **Step 8: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/entities.py \
        science/src/science_tool/annotation/proposition_reconciliation_apply.py \
        science/src/science_tool/annotation/proposition_resynthesis_apply.py \
        science/tests/
git commit -m "refactor(entities): make the entity renderers text-in/text-out"
```

---

### Task 3: The degradation guard

Inside each renderer, validate the pre-image and the post-image with `EntityValidator.validate_persisted_base_shape`, and **refuse iff the pre-image satisfies base shape and the post-image would not**. Exactly one of the four transitions is forbidden (§2).

**Files:**
- Modify: `science/src/science_tool/entities.py` (imports, new error class, new guard, both renderers)
- Test: `science/tests/test_entity_writer.py`

**Interfaces:**
- Consumes: the text-in/text-out signatures from Task 2.
- Produces: `EntityDegradationError(EntityCommandError)` in `science_tool.entities`. Subclassing `EntityCommandError` is deliberate — the two prose workflows already catch `(DecompositionError, EntityCommandError, PromotionApplyError)`, and resynthesis's `_original_edit` already catches `EntityCommandError`, so those three keep their current shape with no change.

- [ ] **Step 1: Write the failing tests — the four-transition matrix**

Add to `science/tests/test_entity_writer.py`:

```python
import pytest

from science_tool.entities import EntityDegradationError

VALID = (
    "---\n"
    "id: proposition:x\n"
    "kind: proposition\n"
    "title: a real claim\n"
    "created: '2026-01-01'\n"
    "updated: '2026-01-01'\n"
    "---\n"
    "body\n"
)

# Empty `title` is what 769 of piece 3's 792 repaired records carried; base 2.0 requires
# a non-empty string.
INVALID = VALID.replace("title: a real claim", "title: ''")


def test_valid_to_valid_writes(tmp_path: Path):
    rendered, changed = render_entity_frontmatter_updates(
        VALID, {"status": "superseded"}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
    )
    assert changed is True
    assert "status: superseded" in rendered


def test_valid_to_invalid_refuses(tmp_path: Path):
    with pytest.raises(EntityDegradationError) as excinfo:
        render_entity_frontmatter_updates(
            VALID, {"title": ""}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
        )
    assert "x.md" in str(excinfo.value)


def test_invalid_to_invalid_writes(tmp_path: Path):
    """A record that already fails base shape stays writable. 183 records across 13 kinds
    fail it today; refusing writes to those would couple this work to migrating them."""
    rendered, changed = render_entity_frontmatter_updates(
        INVALID, {"status": "superseded"}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
    )
    assert changed is True
    assert "status: superseded" in rendered


def test_invalid_to_valid_writes(tmp_path: Path):
    """No INTENTIONAL backfill, but a write whose own content happens to satisfy base
    shape is allowed through."""
    rendered, changed = render_entity_frontmatter_updates(
        INVALID, {"title": "a real claim"}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
    )
    assert changed is True
    assert "title: a real claim" in rendered


def test_source_refs_renderer_carries_the_same_guard(tmp_path: Path):
    """Both renderers, not just one: append_entity_source_ref already reaches `hypothesis`
    through promotion LINK, and `hypothesis` is an armed kind."""
    # `source_refs` must be an array of strings; a mapping degrades an otherwise valid record.
    with pytest.raises(EntityDegradationError):
        render_entity_source_refs(
            VALID.replace("---\nbody\n", "source_refs: {a: b}\n---\nbody\n"),
            ["paper:new"],
            entity_path=tmp_path / "x.md",
            as_of=date(2026, 6, 16),
        )
```

- [ ] **Step 2: Write the failing round-trip test**

Also in `science/tests/test_entity_writer.py`:

```python
def test_guard_validates_the_reparsed_text_not_the_in_memory_mapping(tmp_path: Path):
    """23 of piece 3's 792 records differed in NO parsed value at all -- they were
    date-quoting alone. `date(...)` is an acceptable in-memory value, and the YAML dumper
    emits it as a bare scalar that reloads as `datetime.date` where base shape requires a
    string. Validating the in-memory mapping would certify something never persisted.

    This test passes only if the guard validates the REPARSED rendered text (design §2.1).
    """
    with pytest.raises(EntityDegradationError):
        render_entity_frontmatter_updates(
            VALID,
            {"created": date(2026, 3, 4)},
            entity_path=tmp_path / "x.md",
            as_of=date(2026, 6, 16),
        )
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_entity_writer.py -k "valid_to or same_guard or reparsed"
```

Expected: `test_valid_to_invalid_refuses`, `test_source_refs_renderer_carries_the_same_guard` and `test_guard_validates_the_reparsed_text_not_the_in_memory_mapping` FAIL with `Failed: DID NOT RAISE`. The other three already pass — they assert the transitions that must stay writable.

- [ ] **Step 4: Add the error class and the guard**

In `science/src/science_tool/entities.py`, extend the existing `science_model.entity_schema` import to include `EntityValidator`:

```python
from science_model.entity_schema import (
    PROJECT_MIXIN_NAMES,
    EntityValidationError,
    EntityValidator,
    check_resolution,
    has_lineage_to_resolve,
)
```

Add the error class beside `EntityCommandError` (`:47`):

```python
class EntityDegradationError(EntityCommandError):
    """A write was refused because it would turn a base-shape-valid record invalid.

    Subclasses `EntityCommandError` so the workflows that already catch that keep their
    current shape. Deliberately WEAKER than `render_update`'s `certify_persisted`, which
    rejects an already-invalid record outright: these renderers are kind-agnostic and serve
    live promotion traffic onto records this branch does not repair. The shared principle is
    only that neither writer backfills.
    """
```

Add the guard immediately above `render_entity_source_refs`:

```python
def _satisfies_base_shape(text: str) -> bool:
    frontmatter, _body = split_frontmatter(text)
    if not isinstance(frontmatter, dict):
        return False
    try:
        EntityValidator().validate_persisted_base_shape(frontmatter)
    except EntityValidationError:
        return False
    return True


def _refuse_degradation(before_text: str, after_text: str, entity_path: Path) -> None:
    """Refuse iff the pre-image satisfies base shape and the post-image would not.

    Exactly one transition is forbidden. `invalid -> invalid` and `invalid -> valid` both
    write: 183 records across 13 kinds fail base shape today, 41 of them `question` -- a
    live promotion LINK target -- and refusing writes to those would couple containment to
    migrating them.

    `after_text` is REPARSED here rather than validated as the mapping that was dumped, for
    the reason `certify_persisted` documents: the round trip is what catches an unquoted
    date the dumper emitted as a bare scalar, which reloads as `datetime.date` where the
    schema requires a string.
    """
    if not _satisfies_base_shape(before_text):
        return
    frontmatter, _body = split_frontmatter(after_text)
    try:
        EntityValidator().validate_persisted_base_shape(frontmatter)
    except EntityValidationError as exc:
        raise EntityDegradationError(
            f"{entity_path} satisfies the durable base shape and this write would not; "
            f"nothing was written\n  {exc}"
        ) from exc
```

- [ ] **Step 5: Call the guard from both renderers**

In `render_entity_source_refs`, replace the final return:

```python
    frontmatter["source_refs"] = refs
    frontmatter["updated"] = (as_of or date.today()).isoformat()
    rendered = _render_markdown(frontmatter, body)
    _refuse_degradation(current_text, rendered, entity_path)
    return (rendered, True)
```

In `render_entity_frontmatter_updates`, the same:

```python
    frontmatter["updated"] = (as_of or date.today()).isoformat()
    rendered = _render_markdown(frontmatter, body)
    _refuse_degradation(current_text, rendered, entity_path)
    return (rendered, True)
```

The unchanged branches return `current_text` before reaching the guard, which is correct: a no-op write cannot degrade anything.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_entity_writer.py
```

Expected: all pass, including the four matrix cases and the round trip.

- [ ] **Step 7: Certify the guard by mutation**

Temporarily change `_refuse_degradation` to validate the in-memory mapping instead of the reparsed text — i.e. replace the `split_frontmatter(after_text)` line with the mapping the caller dumped — and re-run:

```bash
cd science && uv run --frozen pytest tests/test_entity_writer.py::test_guard_validates_the_reparsed_text_not_the_in_memory_mapping
```

Expected: FAIL. Then revert the mutation and confirm it passes again. A guard that cannot be made to fail is not certified.

- [ ] **Step 8: Run the downstream suites**

```bash
cd science && uv run --frozen pytest tests/test_entity_writer.py tests/test_hypothesis_consumers.py tests/test_proposition_reconciliation_apply.py tests/test_proposition_resynthesis_apply.py tests/test_annotation_promote.py tests/test_promote_numeric_mint.py tests/test_prose_promote.py tests/test_prose_promotion_batch.py
```

Expected: all pass.

- [ ] **Step 9: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

- [ ] **Step 10: Commit**

```bash
git add science/src/science_tool/entities.py science/tests/test_entity_writer.py
git commit -m "feat(entities): refuse writes that degrade a base-shape-valid record"
```

---

### Task 4: Translation and aggregation

A renderer refusal must never reach a CLI as `EntityDegradationError`. Two workflows need work (§2.3): `apply_candidates` lets `EntityCommandError` escape and the promotion CLI wraps it in `except PromotionApplyError` alone (`annotation/cli.py:2640-2642`); `plan_canonicalization_apply`'s two renderer calls sit in no `try` at all. Canonicalization is additionally a **batch** — it loops `for action in actions` with both renderer calls inside the loop — so it must aggregate, not abort on the first refusal (§2.2).

Resynthesis needs no change: `_original_edit` already catches `EntityCommandError` and raises `ResynthesisApplyError`, so `EntityDegradationError` is caught by inheritance. The two prose workflows are covered the same way by their existing `except (DecompositionError, EntityCommandError, PromotionApplyError)`.

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_apply.py` (the `for action in actions` loop in `plan_canonicalization_apply`)
- Modify: `science/src/science_tool/annotation/promote.py` (`apply_candidates`)
- Test: `science/tests/test_proposition_reconciliation_apply.py`, `science/tests/test_annotation_promote.py`

**Interfaces:**
- Consumes: `EntityDegradationError` from `science_tool.entities` (Task 3).
- Produces: no new public names. `plan_canonicalization_apply` raises `ReconciliationApplyError` naming **every** refused record; `apply_candidates` raises `PromotionApplyError`.
- The `apply_candidates` translation is **temporary by design** — slice 2 (Task 8) replaces it with the aggregated report. It exists so slice 1 can land alone without introducing a raw traceback in the promotion CLI for exactly the case the guard exists to report.

- [ ] **Step 1: Write the failing aggregation test**

Add to `science/tests/test_proposition_reconciliation_apply.py`. Build a plan with **two** actions, each whose duplicate would degrade, and assert both are named:

```python
def test_canonicalization_aggregates_every_degradation_refusal(tmp_path: Path):
    """plan_canonicalization_apply loops over the selected action set with both renderer
    calls inside the loop, so an N-action set can refuse N times. Aborting on the first
    would make an operator re-run the command once per bad record."""
    project_root = _reconciliation_project(tmp_path)  # existing helper in this module

    # Two duplicates whose supersession update would degrade an otherwise valid record:
    # `superseded_by` must be a string, and each already carries a non-string that base
    # shape rejects once the write lands.
    _write_degrading_duplicate(project_root, "dup-a")
    _write_degrading_duplicate(project_root, "dup-b")

    plan = _two_action_plan(canonical_a="canon-a", duplicate_a="dup-a",
                            canonical_b="canon-b", duplicate_b="dup-b")

    with pytest.raises(ReconciliationApplyError) as excinfo:
        plan_canonicalization_apply(project_root, plan)

    message = str(excinfo.value)
    assert "dup-a" in message
    assert "dup-b" in message
    # Nothing was written: this is a PLANNING failure.
    assert "superseded" not in (project_root / "entities/propositions/canon-a.md").read_text()
```

Write `_write_degrading_duplicate` and `_two_action_plan` against the fixtures this module already uses — read the existing helpers at the top of the file first and follow their shape. A degrading duplicate is one whose record is base-shape-valid but whose planned post-image is not; the simplest reachable form is a record whose `source_refs` is a mapping rather than a list, since the supersession write re-dumps the whole mapping.

- [ ] **Step 2: Run it to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_proposition_reconciliation_apply.py::test_canonicalization_aggregates_every_degradation_refusal
```

Expected: FAIL — only the first duplicate is named, because `EntityDegradationError` escapes the loop on the first refusal (it will surface as `EntityDegradationError`, not `ReconciliationApplyError`, which is the second half of the defect).

- [ ] **Step 3: Aggregate inside the action loop**

In `plan_canonicalization_apply`, add a refusal accumulator before the loop and collect per renderer call:

```python
    degradations: list[str] = []

    for action in actions:
        ...
        try:
            final_text, _changed = render_entity_source_refs(
                current_text(canonical_location.path),
                canonical_refs,
                entity_path=canonical_location.path,
                as_of=as_of,
            )
        except EntityCommandError as exc:
            degradations.append(f"{canonical}: {exc}")
            continue
        ...
        for duplicate in action.members:
            ...
            try:
                final_text, _changed = render_entity_frontmatter_updates(
                    current_text(duplicate_location.path),
                    {"status": "superseded", "superseded_by": canonical},
                    entity_path=duplicate_location.path,
                    as_of=as_of,
                )
            except EntityCommandError as exc:
                degradations.append(f"{duplicate}: {exc}")
                continue
```

and raise once, after the loop, before the sidecar pass:

```python
    if degradations:
        joined = "\n  ".join(degradations)
        raise ReconciliationApplyError(
            f"{len(degradations)} record(s) would be degraded by this canonicalization and "
            f"nothing was written:\n  {joined}"
        )
```

Import `EntityCommandError` from `science_tool.entities` if it is not already imported in this module. Catching the base class rather than `EntityDegradationError` is deliberate: `find_entity` and the renderers can both raise `EntityCommandError`, and both are candidate-local planning failures the operator wants reported together.

- [ ] **Step 4: Run it to verify it passes**

```bash
cd science && uv run --frozen pytest tests/test_proposition_reconciliation_apply.py::test_canonicalization_aggregates_every_degradation_refusal
```

Expected: PASS.

- [ ] **Step 5: Write the failing promotion translation test**

Add to `science/tests/test_annotation_promote.py`:

```python
def test_apply_candidates_translates_a_degradation_refusal(tmp_path: Path):
    """The promotion CLI wraps apply_candidates in `except PromotionApplyError` alone
    (annotation/cli.py:2640-2642), so an EntityDegradationError would surface as a raw
    traceback for exactly the case the guard exists to report."""
    project_root, sidecar_path = _promotion_project(tmp_path)  # existing helper
    dest = project_root / "entities/propositions/existing.md"
    # Base-shape valid today, but its `source_refs` is a mapping, so the LINK append
    # re-dumps a frontmatter that base shape rejects.
    dest.write_text(_degrading_record(), encoding="utf-8")

    candidate = _link_candidate(slug="proposition:existing")

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [candidate],
            sidecar_path=sidecar_path,
            project_root=project_root,
            paper_ref="paper:p",
        )

    assert "existing" in str(excinfo.value)
```

- [ ] **Step 6: Run it to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_annotation_promote.py::test_apply_candidates_translates_a_degradation_refusal
```

Expected: FAIL — `EntityDegradationError` is raised instead of `PromotionApplyError`.

- [ ] **Step 7: Translate in `apply_candidates`**

In `science/src/science_tool/annotation/promote.py`, wrap the body of the candidate loop:

```python
    for c in candidates:
        try:
            if c.decision == "MINT":
                ...
            elif c.decision == "LINK":
                ...
            else:  # COLLISION / SKIP — not applied
                report.skipped[c.reason] += 1
        except EntityDegradationError as exc:
            raise PromotionApplyError(str(exc)) from exc
```

Import `EntityDegradationError` from `science_tool.entities`. Add a comment recording that this is the slice-1 half-step:

```python
        # Slice 1 translation: apply_candidates still writes as it goes, so a refusal must
        # not reach the CLI as EntityDegradationError. Slice 2 replaces this with the
        # aggregated preflight report.
```

- [ ] **Step 8: Pin the two workflows that are already covered**

Resynthesis and the prose paths are covered by *inheritance* — `EntityDegradationError` subclasses `EntityCommandError`, which they already catch. Inheritance coverage is real but invisible, so pin it. Add to `science/tests/test_proposition_resynthesis_apply.py`:

```python
def test_resynthesis_surfaces_a_degradation_refusal_as_its_own_error(tmp_path: Path):
    """`_original_edit` already catches EntityCommandError, so EntityDegradationError is
    covered by inheritance and needs no code change. This test is what would notice if that
    catch were ever narrowed to a sibling type."""
    project_root = _resynthesis_project(tmp_path)  # existing helper
    original = project_root / "entities/propositions/original.md"
    original.write_text(_degrading_record(title="original"), encoding="utf-8")
    draft = _draft_superseding("proposition:original", replacements=["proposition:new"])

    with pytest.raises(ResynthesisApplyError):
        plan_resynthesis_apply(project_root, draft)
```

- [ ] **Step 9: Run the affected suites**

```bash
cd science && uv run --frozen pytest tests/test_annotation_promote.py tests/test_annotate_promote_cli.py tests/test_proposition_reconciliation_apply.py tests/test_proposition_reconciliation_cli.py tests/test_promote_qh_integration.py tests/test_proposition_resynthesis_apply.py
```

Expected: all pass.

- [ ] **Step 10: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

- [ ] **Step 11: Commit**

```bash
git add science/src/science_tool/annotation/proposition_reconciliation_apply.py \
        science/src/science_tool/annotation/promote.py \
        science/tests/test_proposition_reconciliation_apply.py \
        science/tests/test_annotation_promote.py \
        science/tests/test_proposition_resynthesis_apply.py
git commit -m "feat(annotation): translate and aggregate renderer refusals per workflow"
```

---

### Task 5: Update the anticipatory guard

`tests/test_hypothesis_consumers.py:263-276` (`test_the_OTHER_entity_writer_still_cannot_reach_a_hypothesis`) pins the call-site set of `render_entity_frontmatter_updates` and says in its own comment that the writer "runs NO schema or resolution check". Both halves need updating: the premise stops being true, and the roster was one writer short — `append_entity_source_ref` already reaches `hypothesis` through promotion LINK, and `hypothesis` is an armed kind (§1.1).

**Files:**
- Modify: `science/tests/test_hypothesis_consumers.py:263-276`

**Interfaces:**
- Consumes: `EntityDegradationError` and the guard from Task 3.
- Produces: nothing importable. This task replaces a roster-based guard with a behavioral one.

- [ ] **Step 1: Read the existing guard**

```bash
cd science && sed -n '250,290p' tests/test_hypothesis_consumers.py
```

Read the whole test and its comment before changing anything — the comment states the reasoning this task is preserving, not discarding.

- [ ] **Step 2: Replace it with a behavioral guard**

The roster enumerated callers, which is why it had a hole. Replace it with a test that exercises the property directly, for **both** renderers, on a `hypothesis`:

```python
def test_neither_entity_writer_can_degrade_a_hypothesis():
    """Supersedes the roster-based guard.

    The old test pinned the CALL SITES of `render_entity_frontmatter_updates` and reasoned
    that the writer was safe because both its callers operated on propositions. The
    reasoning was sound and the roster was real, but it ranged over one writer and not its
    sibling: `append_entity_source_ref` already reached `hypothesis` through promotion LINK,
    and `hypothesis` is an armed kind. A guard that LISTS its scope has a hole by
    construction.

    The renderers now certify base shape themselves, so containment no longer depends on a
    roster staying complete -- and this test ranges over behavior instead of callers.
    """
    valid_hypothesis = (
        "---\n"
        "id: hypothesis:h0001\n"
        "kind: hypothesis\n"
        "title: a hypothesis\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "---\n"
        "body\n"
    )
    path = Path("entities/hypotheses/h0001.md")

    with pytest.raises(EntityDegradationError):
        render_entity_frontmatter_updates(
            valid_hypothesis, {"title": ""}, entity_path=path, as_of=date(2026, 6, 16)
        )

    with pytest.raises(EntityDegradationError):
        render_entity_source_refs(
            valid_hypothesis.replace("---\nbody\n", "source_refs: {a: b}\n---\nbody\n"),
            ["paper:new"],
            entity_path=path,
            as_of=date(2026, 6, 16),
        )
```

Delete the old `test_the_OTHER_entity_writer_still_cannot_reach_a_hypothesis` and its now-false comment. Add imports for `pytest`, `date`, `Path`, `EntityDegradationError`, `render_entity_frontmatter_updates` and `render_entity_source_refs` if the module lacks them.

- [ ] **Step 3: Run it**

```bash
cd science && uv run --frozen pytest tests/test_hypothesis_consumers.py
```

Expected: all pass.

- [ ] **Step 4: Certify by mutation**

Temporarily make `_refuse_degradation` in `entities.py` return unconditionally, and re-run:

```bash
cd science && uv run --frozen pytest tests/test_hypothesis_consumers.py::test_neither_entity_writer_can_degrade_a_hypothesis
```

Expected: FAIL with `DID NOT RAISE`. Revert and confirm it passes.

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_hypothesis_consumers.py
git commit -m "test(hypothesis): replace the roster guard with a behavioral one"
```

**Slice 1 is complete at this commit.** The two staged workflows are contained; the three immediate-write workflows translate their refusals but still write as they go.

---

# Slice 2 — preflight the three immediate-write workflows

### Task 6: Creates, drift, and the publish primitive

`PlannedFileEdit` models an update: `plan_update` calls `current_text(path)` unconditionally, so it cannot represent an absent pre-image, and the apply loop publishes with `atomic_write_text` — a temp file plus `os.replace`, which overwrites whatever is there. Planned creates and planned numeric mints need different publishes, and planned updates need an optimistic precondition (§4.3).

**Files:**
- Modify: `science/src/science_tool/annotation/planned_edits.py`
- Modify: `science/src/science_tool/dag/entity_frontmatter.py:352-388` (extract `publish_new_file`)
- Test: `science/tests/test_planned_edits.py`

**Interfaces:**
- Consumes: `PlannedFileEdit`, `current_text`, `sha256_text` (Task 1).
- Produces:

```python
class PlannedEditDriftError(EntityCommandError):
    """A planned update's target changed on disk after planning; the batch refused."""


@dataclass(frozen=True)
class PlannedFileEdit:
    path: Path
    reason: str
    before_sha256: str | None        # None for a create -- there is no pre-image
    after_sha256: str
    final_text: str
    changed: bool
    operation: Literal["create", "update"] = "update"
    claim_number: int | None = None  # numeric create only
    kind: str | None = None          # numeric create only, for claim_number_in_dir
    local_part: str | None = None    # numeric create only, for claim_number_in_dir


def plan_update(path: Path, final_text: str, reason: str) -> PlannedFileEdit: ...
def plan_create(path: Path, final_text: str, reason: str) -> PlannedFileEdit: ...
def plan_numeric_create(
    path: Path, final_text: str, reason: str, *, kind: str, local_part: str, number: int
) -> PlannedFileEdit: ...
def publish_edit(edit: PlannedFileEdit, *, project_root: Path) -> None: ...
def edits_for_planned_texts(
    planned_text_by_path: Mapping[Path, str],
    creates: Mapping[Path, tuple[str, str, int] | None],   # path -> (kind, local_part, number) | None
    *,
    reason_create: str,
    reason_update: str,
) -> dict[Path, PlannedFileEdit]: ...
```

`edits_for_planned_texts` is the "one `PlannedFileEdit` per path, **after** composition" rule, defined once here because Tasks 8 and 10 both need it. A path present in `creates` becomes `plan_numeric_create` when its value is a `(kind, local_part, number)` triple and `plan_create` when its value is `None`; every other path becomes `plan_update`.

- Also produces `publish_new_file(dest: Path, text: str) -> None` in `science_tool.dag.entity_frontmatter`, extracted from `create_entity_file` so the exclusive-create publish can be used without re-rendering.

- [ ] **Step 1: Write the failing drift tests**

Add to `science/tests/test_planned_edits.py`:

```python
import pytest

from science_tool.annotation.planned_edits import (
    PlannedEditDriftError,
    plan_create,
    publish_edit,
)
from science_tool.dag.entity_frontmatter import EntityWriteError


def test_update_refuses_when_the_target_drifted(tmp_path: Path):
    """os.replace overwrites unconditionally, so an update planned against bytes that have
    since changed would silently discard the other writer's work -- and preflight is what
    makes that race worth caring about, since the window is now the whole planning phase."""
    target = tmp_path / "record.md"
    target.write_text("planned against this\n", encoding="utf-8")
    edit = plan_update(target, "my new content\n", "r")

    target.write_text("someone else got here first\n", encoding="utf-8")

    with pytest.raises(PlannedEditDriftError) as excinfo:
        publish_edit(edit, project_root=tmp_path)

    assert target.name in str(excinfo.value)
    # The assertion that matters: the other writer's bytes survive.
    assert target.read_text(encoding="utf-8") == "someone else got here first\n"


def test_update_publishes_when_the_target_is_unchanged(tmp_path: Path):
    target = tmp_path / "record.md"
    target.write_text("before\n", encoding="utf-8")
    edit = plan_update(target, "after\n", "r")

    publish_edit(edit, project_root=tmp_path)

    assert target.read_text(encoding="utf-8") == "after\n"


def test_create_refuses_an_intervening_file_without_clobbering_it(tmp_path: Path):
    """Asserting only that an error was raised is not enough -- an atomic_write_text publish
    would overwrite the file and could still raise later in the batch. The assertion that
    fails under os.replace is the untouched pre-existing content."""
    dest = tmp_path / "new.md"
    edit = plan_create(dest, "my planned content\n", "r")

    dest.write_text("another writer created this\n", encoding="utf-8")

    with pytest.raises(EntityWriteError):
        publish_edit(edit, project_root=tmp_path)

    assert dest.read_text(encoding="utf-8") == "another writer created this\n"


def test_plan_create_needs_no_pre_image(tmp_path: Path):
    """Fails if plan_create calls current_text on a path that does not exist."""
    edit = plan_create(tmp_path / "absent.md", "content\n", "r")

    assert edit.before_sha256 is None
    assert edit.changed is True
    assert edit.operation == "create"
```

- [ ] **Step 2: Run them to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py
```

Expected: FAIL — `ImportError: cannot import name 'PlannedEditDriftError'`.

- [ ] **Step 3: Extract `publish_new_file`**

In `science/src/science_tool/dag/entity_frontmatter.py`, split the staging block out of `create_entity_file`:

```python
def publish_new_file(dest: Path, text: str) -> None:
    """Publish `text` to `dest`, refusing to clobber an existing file.

    Stages to a random temp name opened "x" and publishes with `os.link`, so a file that
    appears BETWEEN a caller's existence check and this publish still raises. Under
    plan-then-apply that window is no longer microseconds -- it spans the whole planning
    phase -- so this is the mechanism that makes preflight safe, not belt-and-braces.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            staged = dest.with_name(f".{dest.name}.{secrets.token_hex(8)}.tmp")
            try:
                handle = staged.open("x", encoding="utf-8", newline="")
                break
            except FileExistsError:
                continue
        try:
            with handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(staged, dest)
        finally:
            staged.unlink(missing_ok=True)
    except FileExistsError as exc:
        raise EntityWriteError(f"refusing to create {dest}: it already exists") from exc
    except OSError as exc:
        raise EntityWriteError(f"could not create {dest}: {exc}") from exc
```

Then `create_entity_file`'s body becomes:

```python
    dest = _entity_dest(entity, project_root)
    if dest.exists():
        raise EntityWriteError(f"refusing to create {dest}: it already exists")
    today = (as_of or date.today()).isoformat()
    text = render_create(
        entity, ownership=ownership, body=create_body, created=today, updated=today
    )
    publish_new_file(dest, text)
    return dest
```

- [ ] **Step 4: Extend `planned_edits.py`**

Add to `science/src/science_tool/annotation/planned_edits.py`:

```python
from typing import Literal

from science_model.frontmatter import atomic_write_text

from science_tool.dag.entity_frontmatter import publish_new_file
from science_tool.entities import EntityCommandError
from science_tool.entity_reservation import claim_number_in_dir


class PlannedEditDriftError(EntityCommandError):
    """A planned update's target changed on disk after planning; the batch refused.

    Subclasses `EntityCommandError` so a workflow's existing wrap set covers it, but it is
    named in each publish table so the inventory of what the write stage can raise stays
    complete rather than relying on inheritance to be noticed.
    """
```

Extend the dataclass with the four new fields shown in **Interfaces** above, then add the two constructors and the publisher:

```python
def plan_create(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    """A planned create asserts the destination is absent rather than reading it."""
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=None,
        after_sha256=sha256_text(final_text),
        final_text=final_text,
        changed=True,
        operation="create",
    )


def plan_numeric_create(
    path: Path, final_text: str, reason: str, *, kind: str, local_part: str, number: int
) -> PlannedFileEdit:
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=None,
        after_sha256=sha256_text(final_text),
        final_text=final_text,
        changed=True,
        operation="create",
        claim_number=number,
        kind=kind,
        local_part=local_part,
    )


def publish_edit(edit: PlannedFileEdit, *, project_root: Path) -> None:
    """Publish one planned edit. The write stage's WHOLE vocabulary.

    Three publishes, three failure modes:

    | publish        | raises                                        |
    |----------------|-----------------------------------------------|
    | update         | PlannedEditDriftError, OSError                 |
    | create         | EntityWriteError, OSError                      |
    | numeric create | EntityCommandError (drift), OSError            |

    The create guarantee is stronger than the update guarantee, and the difference is real:
    the exclusive open("x") + os.link publish is atomic against a concurrent creator, so it
    can never clobber. The update refuses drift OBSERVED by the check immediately below --
    compare-then-os.replace leaves a narrow TOCTOU window. The check shortens the exposure
    from the whole planning phase to a few syscalls; it does not eliminate it.
    """
    if edit.operation == "create":
        if edit.claim_number is not None:
            assert edit.kind is not None and edit.local_part is not None
            claim_number_in_dir(
                project_root, edit.kind, edit.claim_number, edit.local_part, edit.final_text
            )
            return
        publish_new_file(edit.path, edit.final_text)
        return

    assert edit.before_sha256 is not None
    if sha256_text(current_text(edit.path)) != edit.before_sha256:
        raise PlannedEditDriftError(
            f"refusing to publish {path_string(edit.path)}: it changed on disk after this "
            f"batch was planned; re-run the preview"
        )
    atomic_write_text(edit.path, edit.final_text)
```

`plan_update` keeps its existing body — it already sets `before_sha256` and defaults `operation` to `"update"`.

Finally, the shared edit-construction rule both slice-2 planners need:

```python
def edits_for_planned_texts(
    planned_text_by_path: Mapping[Path, str],
    creates: Mapping[Path, tuple[str, str, int] | None],
    *,
    reason_create: str,
    reason_update: str,
) -> dict[Path, PlannedFileEdit]:
    """One PlannedFileEdit per path, AFTER composition.

    Constructing an edit mid-composition would capture an intermediate post-image as
    `after_sha256` and re-read disk for `before_sha256` on the next edit to the same path,
    losing the earlier change. Building them all here, once, is what makes `before_sha256`
    the on-disk pre-image and `after_sha256` the composed result.

    `creates` maps a path to `(kind, local_part, number)` for a numeric create, or to `None`
    for a slug-addressed create. Paths absent from it are updates.
    """
    edits: dict[Path, PlannedFileEdit] = {}
    for path, post_image in planned_text_by_path.items():
        if path in creates:
            numeric = creates[path]
            edits[path] = (
                plan_numeric_create(
                    path, post_image, reason_create,
                    kind=numeric[0], local_part=numeric[1], number=numeric[2],
                )
                if numeric is not None
                else plan_create(path, post_image, reason_create)
            )
        else:
            edits[path] = plan_update(path, post_image, reason_update)
    return edits
```

Import `Mapping` from `collections.abc`.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py
```

Expected: all pass.

- [ ] **Step 6: Certify the drift guard by mutation**

Temporarily delete the hash comparison from `publish_edit` and re-run:

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py::test_update_refuses_when_the_target_drifted
```

Expected: FAIL — the other writer's bytes are gone. Revert. Then swap `publish_new_file` for `atomic_write_text` in the create branch and re-run:

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py::test_create_refuses_an_intervening_file_without_clobbering_it
```

Expected: FAIL on the surviving-content assertion. Revert.

- [ ] **Step 7: Run the entity-writer suites**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py tests/test_entity_writer.py tests/test_proposition_reconciliation_apply.py tests/test_proposition_resynthesis_apply.py -k "not slow"
```

Expected: all pass. `create_entity_file`'s extraction is behavior-preserving, so nothing that exercises it should change.

- [ ] **Step 8: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/annotation/planned_edits.py \
        science/src/science_tool/dag/entity_frontmatter.py \
        science/tests/test_planned_edits.py
git commit -m "feat(annotation): add create, numeric-create and drift-refusing publishes"
```

---

### Task 7: `PromotionTarget.plan_mint`

`PromotionTarget.mint` is a **writing** function today. Adding a preflight *around* that contract would leave the writes inside `mint` and produce a design that looks preflighted and is not (§4.4). This task replaces it with a pure planning function that performs no filesystem writes and reserves no number.

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py:258-390`
- Test: `science/tests/test_annotation_promote.py`, `science/tests/test_promote_numeric_mint.py`

**Interfaces:**
- Consumes: `plan_create`, `plan_numeric_create`, `plan_update` (Task 6); `render_entity_source_refs` (Task 2); `propose_number` from `science_tool.entity_reservation`.
- Produces:

```python
@dataclass(frozen=True)
class PlannedMint:
    entity_id: str                          # "<kind>:<local_part>", the id apply must land
    operation: Literal["create", "accrue"]  # what MintOutcome.created encoded
    path: Path
    post_image: str                         # the exact text to publish
    claim_number: int | None                # set for numeric kinds; None for slug-addressed


# (candidate, source_refs, project_root, as_of, assigned_number, current_text) -> PlannedMint
PlanMintFn = Callable[
    ["PromotionCandidate", list[str], Path, "date | None", int | None, str | None],
    PlannedMint,
]


@dataclass(frozen=True)
class PromotionTarget:
    kind: str
    slug_addressed: bool
    plan_mint: PlanMintFn
```

- `MintOutcome` and `MintFn` are **deleted**. A writing `mint` no longer exists on the target, so an implementation cannot retain writes inside it — there is nothing left to hide them in.
- The two added inputs are what keep the target pure. `assigned_number` is the number the *outer* planner allocated in memory — a target that called `propose_number` itself would hand every candidate in the batch the same number, since `propose_number` is read-only and nothing has been written yet. `current_text` is the destination's **composed** post-image so far, or `None` when the destination does not exist; accrual is an update, so it must render from what previous edits in this batch already planned for that path.

- [ ] **Step 1: Write the failing purity test**

Add to `science/tests/test_annotation_promote.py`:

```python
def test_planning_a_mint_writes_nothing_and_consumes_no_number(tmp_path: Path):
    """This is what fails if an implementation keeps writes inside mint."""
    project_root = _promotion_project_root(tmp_path)  # existing helper
    targets = build_targets()

    before_files = sorted(p.name for p in (project_root / "entities/propositions").glob("*.md"))
    before_number = propose_number(project_root, "question")

    prop = targets["proposition"].plan_mint(
        _mint_candidate(kind="proposition", slug="a-claim"), ["paper:p"], project_root, None,
        None, None,
    )
    question = targets["question"].plan_mint(
        _mint_candidate(kind="question", slug="a-question"), ["paper:p"], project_root, None,
        before_number, None,
    )

    assert prop.operation == "create"
    assert prop.claim_number is None
    assert question.operation == "create"
    assert question.claim_number == before_number

    assert sorted(p.name for p in (project_root / "entities/propositions").glob("*.md")) == before_files
    assert propose_number(project_root, "question") == before_number


def test_plan_mint_accrual_renders_from_the_composed_text(tmp_path: Path):
    """Accrual is an UPDATE, so it must render from what previous edits in this batch already
    planned for that path. Re-reading disk would discard them."""
    project_root = _promotion_project_root(tmp_path)
    dest = project_root / "entities/propositions/a-claim.md"
    dest.write_text(_valid_proposition(title="a claim"), encoding="utf-8")
    targets = build_targets()

    composed, _ = render_entity_source_refs(
        dest.read_text(encoding="utf-8"), ["paper:earlier"], entity_path=dest
    )

    planned = targets["proposition"].plan_mint(
        _mint_candidate(kind="proposition", slug="a-claim", claim="a claim"),
        ["paper:later"], project_root, None, None, composed,
    )

    assert planned.operation == "accrue"
    assert "paper:earlier" in planned.post_image  # the earlier edit is NOT lost
    assert "paper:later" in planned.post_image
```

- [ ] **Step 2: Run them to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_annotation_promote.py -k "plan_mint or planning_a_mint"
```

Expected: FAIL — `AttributeError: 'PromotionTarget' object has no attribute 'plan_mint'`.

- [ ] **Step 3: Replace `MintOutcome`/`MintFn` with `PlannedMint`/`PlanMintFn`**

In `science/src/science_tool/annotation/promote.py`, delete `MintOutcome` and `MintFn` and add:

```python
@dataclass(frozen=True)
class PlannedMint:
    """What a mint WOULD do. Nothing here has touched the filesystem."""

    entity_id: str
    operation: Literal["create", "accrue"]
    path: Path
    post_image: str
    claim_number: int | None


# (candidate, source_refs, project_root, as_of, assigned_number, current_text) -> PlannedMint
PlanMintFn = Callable[
    ["PromotionCandidate", list[str], Path, "date | None", int | None, str | None],
    PlannedMint,
]


@dataclass(frozen=True)
class PromotionTarget:
    kind: str
    slug_addressed: bool   # proposition True (content-addressed slug); numeric kinds False
    plan_mint: PlanMintFn
```

`operation` is typed `Literal["create", "accrue"]` rather than `str`, so a third value is a type error rather than a silently unhandled apply branch. Import `Literal` from `typing`.

- [ ] **Step 4: Convert `_mint_proposition` to a planner**

```python
def _plan_proposition_mint(
    c: PromotionCandidate,
    source_refs: list[str],
    project_root: Path,
    as_of: date | None,
    assigned_number: int | None,
    current_text: str | None,
) -> PlannedMint:
    """4a proposition mint planning: create-only, with provenance accrual on an identical
    claim (design §4.3) -- provenance accrual, not a rewrite. Writes nothing."""
    assert c.slug is not None
    assert assigned_number is None, "proposition is slug-addressed; it consumes no number"
    prop_ref = f"proposition:{c.slug}"
    dest = entity_dest(prop_ref, project_root)

    if current_text is not None:
        # Never-overwrite guard: a MINT slug colliding with a DIFFERENT-claim proposition
        # (only reachable via an explicit-id override; auto mints are pre-screened) fails loud.
        existing_fm, _ = split_frontmatter(current_text)
        if normalize_claim(str(existing_fm.get("title") or "")) != normalize_claim(c.claim):
            raise PromotionApplyError(
                f"refusing to overwrite {dest.name}: it holds a different proposition"
            )
        # Same claim from a second source: ACCRUE, exactly as the LINK path does. Rendering
        # it as an update would replace source_refs with only this paper's refs and overwrite
        # the subject/object refinements synthesize owns.
        post_image, _changed = render_entity_source_refs(
            current_text, source_refs, entity_path=dest, as_of=as_of
        )
        return PlannedMint(
            entity_id=prop_ref, operation="accrue", path=dest,
            post_image=post_image, claim_number=None,
        )

    prop = PropositionEntity(
        id=prop_ref, title=c.claim, subject=c.subject, object=c.object,
        source_refs=list(source_refs),
    )
    today = (as_of or date.today()).isoformat()
    post_image = render_create(
        prop,
        ownership=PROMOTE_PROPOSITION,
        body=_proposition_body(c.claim),
        created=today,
        updated=today,
    )
    return PlannedMint(
        entity_id=prop_ref, operation="create", path=dest,
        post_image=post_image, claim_number=None,
    )


def proposition_target() -> PromotionTarget:
    return PromotionTarget(kind="proposition", slug_addressed=True, plan_mint=_plan_proposition_mint)
```

Import `render_create` from `science_tool.dag.entity_frontmatter` and `split_frontmatter` from `science_model.frontmatter`. `render_create` calls `certify_persisted` itself, so the create's certification now runs at **plan** time — which is the point.

- [ ] **Step 5: Convert `_mint_numeric` to a planner**

```python
def _plan_numeric_mint(kind: str) -> PlanMintFn:
    lead = _LEAD_SECTION[kind]

    def plan(
        c: PromotionCandidate,
        source_refs: list[str],
        project_root: Path,
        as_of: date | None,
        assigned_number: int | None,
        current_text: str | None,
    ) -> PlannedMint:
        assert c.slug is not None
        assert assigned_number is not None, f"{kind} is numeric; the planner must assign a number"
        assert current_text is None, f"{kind} mints are create-only; accrual is not reachable"
        today = (as_of or date.today()).isoformat()
        # Preflight the template (pure read, no number consumed). Raises if the packaged
        # template is missing/malformed -- an environment/target-kind PRECONDITION, so the
        # caller aborts rather than aggregating (design §4.1).
        renderer = Renderer()
        renderer.sections(kind)
        local_part = f"{assigned_number:0{LOCAL_PART_WIDTH}d}-{c.slug}"
        entity_id = f"{kind}:{local_part}"
        fields: dict[str, object] = {
            "entity_id": entity_id,
            "title": c.claim,
            "status": default_status(kind),
            "source_refs": list(source_refs),
            "related": [],
            "created": today,
            "updated": today,
        }
        if kind == "hypothesis":
            # A promoted claim is a TRIAL FRAMING, not a committed one -- which is what
            # `phase: candidate` said. `draft` is the lifecycle word it folded into.
            fields["status"] = "draft"
        rendered = renderer.render(kind, fields=fields)
        rendered = _insert_claim_into_lead(rendered, lead, c.claim)
        return PlannedMint(
            entity_id=entity_id,
            operation="create",
            path=entity_dest(entity_id, project_root),
            post_image=rendered,
            claim_number=assigned_number,
        )

    return plan


def numeric_target(kind: str) -> PromotionTarget:
    if kind not in ("question", "hypothesis"):
        raise ValueError(f"numeric_target supports question/hypothesis, got {kind!r}")
    return PromotionTarget(kind=kind, slug_addressed=False, plan_mint=_plan_numeric_mint(kind))
```

Import `LOCAL_PART_WIDTH` from `science_tool.entity_reservation`. The `reserve_entity` call, the placeholder `.md`, and the explicit post-reservation rollback are all **gone** — there is no reservation to roll back, because planning consumes nothing. Verify the local-part format matches what `reserve_number_in_dir` produces:

```bash
cd science && grep -n "local_part\|LOCAL_PART_WIDTH" src/science_tool/entity_reservation.py | head -20
```

Match it exactly — apply passes `local_part` to `claim_number_in_dir`, and a mismatch would land the entity at a path the plan did not name.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_annotation_promote.py -k "plan_mint or planning_a_mint"
```

Expected: PASS. The rest of `test_annotation_promote.py` and `test_promote_numeric_mint.py` will FAIL at this point — their callers still use `target.mint(...)`. Task 8 fixes them.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/annotation/promote.py science/tests/test_annotation_promote.py
git commit -m "feat(promote): replace the writing mint with pure mint planning"
```

Note: `apply_candidates` and both prose workflows are broken at this commit — they call `targets[...].mint`. Tasks 8 and 10 repair them. Do not run the broader promote/prose suites until Task 10 is done.

---

### Task 8: `apply_candidates` becomes plan-then-apply

Build a complete plan, aggregate every candidate-local refusal, then write. This is the pattern reconciliation already implements and that `resolve_entity_slug`'s docstring already states as doctrine (§4).

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py:398-450` (`apply_candidates`)
- Test: `science/tests/test_annotation_promote.py`, `science/tests/test_promote_numeric_mint.py`

**Interfaces:**
- Consumes: `PlannedMint`/`PlanMintFn` (Task 7); `plan_create`, `plan_numeric_create`, `plan_update`, `publish_edit`, `current_text`, `path_string`, `PlannedEditDriftError` (Tasks 1, 6); `propose_number` from `science_tool.entity_reservation`; `serialize_sidecar` from `science_tool.annotation.io`.
- Produces: `apply_candidates` with its existing signature and `ApplyReport` return type, now all-or-nothing against deterministic preflight failures.

**Which failures aggregate, and which may abort (§4.1):**
- **Collected**, then reported together: `EntityDegradationError`, slug-naming failures from `resolve_entity_slug`, LINK target-resolution failures, and the never-overwrite guard. Planning continues past each one so the report is complete.
- **Aborted immediately**: a missing or malformed packaged template (`Renderer().sections(kind)`), an unreadable sidecar, an unresolvable project root. These are properties of the environment or of a target *kind*, not of a candidate. This is a **precondition**, not "every later candidate would fail" — a malformed `question` template does not affect the `proposition` candidates in a mixed-kind batch. They still abort before any write.

- [ ] **Step 1: Write the failing aggregation test**

Add to `science/tests/test_annotation_promote.py`:

```python
def test_apply_candidates_aggregates_every_candidate_local_refusal(tmp_path: Path):
    """One refusal does not prove aggregation; it is equally consistent with
    abort-on-first. Two unsupported records plus one valid edit is the shape that does."""
    project_root, sidecar_path = _promotion_project(tmp_path)
    bad_a = project_root / "entities/propositions/bad-a.md"
    bad_b = project_root / "entities/propositions/bad-b.md"
    good = project_root / "entities/propositions/good.md"
    bad_a.write_text(_degrading_record(title="bad a"), encoding="utf-8")
    bad_b.write_text(_degrading_record(title="bad b"), encoding="utf-8")
    good.write_text(_valid_proposition(title="good"), encoding="utf-8")
    good_before = good.read_text(encoding="utf-8")

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [
                _link_candidate(slug="proposition:bad-a", frag="a-1"),
                _link_candidate(slug="proposition:bad-b", frag="a-2"),
                _link_candidate(slug="proposition:good", frag="a-3"),
            ],
            sidecar_path=sidecar_path,
            project_root=project_root,
            paper_ref="paper:p",
        )

    message = str(excinfo.value)
    assert "bad-a" in message
    assert "bad-b" in message
    # Nothing was written -- not even the valid edit.
    assert good.read_text(encoding="utf-8") == good_before


def test_apply_candidates_aggregates_across_kinds_of_failure(tmp_path: Path):
    """The report spans the whole candidate-local set, not degradation alone."""
    project_root, sidecar_path = _promotion_project(tmp_path)
    bad = project_root / "entities/propositions/bad.md"
    bad.write_text(_degrading_record(title="bad"), encoding="utf-8")

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [
                _link_candidate(slug="proposition:bad", frag="a-1"),
                _link_candidate(slug="proposition:does-not-exist", frag="a-2"),
            ],
            sidecar_path=sidecar_path,
            project_root=project_root,
            paper_ref="paper:p",
        )

    message = str(excinfo.value)
    assert "bad" in message
    assert "does-not-exist" in message


def test_two_links_to_one_record_compose(tmp_path: Path):
    """Two annotations can LINK to the same existing record. Independent edits from the same
    disk pre-image would lose the first."""
    project_root, sidecar_path = _promotion_project(tmp_path)
    dest = project_root / "entities/propositions/shared.md"
    dest.write_text(_valid_proposition(title="shared"), encoding="utf-8")

    apply_candidates(
        [
            _link_candidate(slug="proposition:shared", frag="a-1", ref="annotation:p#a-1"),
            _link_candidate(slug="proposition:shared", frag="a-2", ref="annotation:p#a-2"),
        ],
        sidecar_path=sidecar_path,
        project_root=project_root,
        paper_ref="paper:p",
    )

    written = dest.read_text(encoding="utf-8")
    assert "annotation:p#a-1" in written
    assert "annotation:p#a-2" in written


def test_a_refused_batch_leaves_the_sidecar_unchanged(tmp_path: Path):
    project_root, sidecar_path = _promotion_project(tmp_path)
    bad = project_root / "entities/propositions/bad.md"
    bad.write_text(_degrading_record(title="bad"), encoding="utf-8")
    sidecar_before = sidecar_path.read_text(encoding="utf-8")

    with pytest.raises(PromotionApplyError):
        apply_candidates(
            [_link_candidate(slug="proposition:bad", frag="a-1")],
            sidecar_path=sidecar_path,
            project_root=project_root,
            paper_ref="paper:p",
        )

    assert sidecar_path.read_text(encoding="utf-8") == sidecar_before


def test_sidecar_drift_between_planning_and_apply_refuses(tmp_path: Path, monkeypatch):
    """The drift precondition applies to EVERY planned update, not only entity records. A
    sidecar clobbered by a concurrent writer loses exactly as much as a record does, and it
    is the one planned update that does not look like one."""
    project_root, sidecar_path = _promotion_project(tmp_path)
    dest = project_root / "entities/propositions/existing.md"
    dest.write_text(_valid_proposition(title="existing"), encoding="utf-8")

    real_publish = planned_edits.publish_edit

    def drift_the_sidecar_first(edit, *, project_root):
        if edit.path == sidecar_path:
            sidecar_path.write_text("{}\n", encoding="utf-8")
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(planned_edits, "publish_edit", drift_the_sidecar_first)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [_link_candidate(slug="proposition:existing", frag="a-1")],
            sidecar_path=sidecar_path,
            project_root=project_root,
            paper_ref="paper:p",
        )

    assert "stage=write" in str(excinfo.value)
    # The other writer's bytes survive.
    assert sidecar_path.read_text(encoding="utf-8") == "{}\n"
```

Add to `science/tests/test_promote_numeric_mint.py`:

```python
def test_a_refused_batch_consumes_no_number(tmp_path: Path):
    project_root, sidecar_path = _numeric_promotion_project(tmp_path)  # existing helper
    bad = project_root / "entities/propositions/bad.md"
    bad.write_text(_degrading_record(title="bad"), encoding="utf-8")
    before = propose_number(project_root, "question")

    with pytest.raises(PromotionApplyError):
        apply_candidates(
            [
                _mint_candidate(kind="question", slug="a-question", frag="a-1"),
                _link_candidate(slug="proposition:bad", frag="a-2"),
            ],
            sidecar_path=sidecar_path,
            project_root=project_root,
            paper_ref="paper:p",
        )

    assert propose_number(project_root, "question") == before
    assert not any((project_root / "entities/questions").glob("*.md"))


def test_a_number_claimed_between_plan_and_apply_refuses(tmp_path: Path, monkeypatch):
    """claim_number_in_dir claims a NAMED number, which is what a report-then-apply flow
    needs: the preview showed a number, and apply must land THAT number or refuse."""
    project_root, sidecar_path = _numeric_promotion_project(tmp_path)
    number = propose_number(project_root, "question")

    real_publish = planned_edits.publish_edit
    claimed: list[int] = []

    def publish_after_stealing_the_number(edit, *, project_root):
        if edit.claim_number is not None and not claimed:
            claimed.append(edit.claim_number)
            # Another writer lands the same number first.
            claim_number_in_dir(
                project_root, "question", edit.claim_number, f"{edit.claim_number:04d}-other",
                "---\nid: question:x\n---\n",
            )
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(planned_edits, "publish_edit", publish_after_stealing_the_number)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [_mint_candidate(kind="question", slug="a-question", frag="a-1")],
            sidecar_path=sidecar_path,
            project_root=project_root,
            paper_ref="paper:p",
        )

    assert "re-run the preview" in str(excinfo.value)


def test_a_write_stage_failure_reports_what_was_already_written(tmp_path: Path, monkeypatch):
    """A claim_number_in_dir drift failure raised AFTER an earlier file has been written must
    carry files_written and written_paths. An OSError-only wrapper passes the plain
    atomic_write_text test and fails this one, which is the point: EntityCommandError,
    EntityWriteError and DecompositionError are SIBLING ValueError subclasses, so catching
    one catches neither of the others."""
    project_root, sidecar_path = _numeric_promotion_project(tmp_path)
    existing = project_root / "entities/propositions/existing.md"
    existing.write_text(_valid_proposition(title="existing"), encoding="utf-8")

    real_publish = planned_edits.publish_edit

    def steal_the_number_after_the_first_write(edit, *, project_root):
        if edit.claim_number is not None:
            claim_number_in_dir(
                project_root, "question", edit.claim_number,
                f"{edit.claim_number:0{LOCAL_PART_WIDTH}d}-other", "---\nid: question:x\n---\n",
            )
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(planned_edits, "publish_edit", steal_the_number_after_the_first_write)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [
                # Sorted by path, so the proposition LINK publishes BEFORE the question mint.
                _link_candidate(slug="proposition:existing", frag="a-1"),
                _mint_candidate(kind="question", slug="a-question", frag="a-2"),
            ],
            sidecar_path=sidecar_path,
            project_root=project_root,
            paper_ref="paper:p",
        )

    message = str(excinfo.value)
    assert "stage=write" in message
    assert "files_written=1" in message
    assert "existing.md" in message


def test_a_malformed_kind_template_aborts_before_any_write(tmp_path: Path, monkeypatch):
    """The §4.1 boundary's other half. A missing or malformed packaged template is a property
    of the ENVIRONMENT or of a target KIND, not of a candidate, and no candidate-level fix
    exists -- so it aborts rather than aggregating. This is a PRECONDITION, not a claim that
    every later candidate would fail: a malformed `question` template does not affect the
    `proposition` candidates in a mixed-kind batch.

    Without this test, "may abort immediately" is untested and an implementer could
    legitimately aggregate everything."""
    project_root, sidecar_path = _numeric_promotion_project(tmp_path)
    existing = project_root / "entities/propositions/existing.md"
    existing.write_text(_valid_proposition(title="existing"), encoding="utf-8")
    existing_before = existing.read_text(encoding="utf-8")

    def malformed_sections(self, kind):
        raise RendererError(f"packaged template for {kind} is malformed")

    monkeypatch.setattr(Renderer, "sections", malformed_sections)

    with pytest.raises(RendererError):
        apply_candidates(
            [
                _link_candidate(slug="proposition:existing", frag="a-1"),
                _mint_candidate(kind="question", slug="a-question", frag="a-2"),
            ],
            sidecar_path=sidecar_path,
            project_root=project_root,
            paper_ref="paper:p",
        )

    # ONE error, not an aggregated report -- and nothing was written, including the
    # proposition LINK that would have succeeded.
    assert existing.read_text(encoding="utf-8") == existing_before
```

`RendererError` is whatever `Renderer().sections` raises for a malformed template — check it before writing the test:

```bash
cd science && grep -rn "class .*Error" src/science_tool/renderer.py src/science_tool/templates/*.py 2>/dev/null | head
```

If the real exception type is not among the candidate-local set caught by `apply_candidates`, the abort is already correct by construction and the test documents it. If it **is** — e.g. it subclasses `EntityCommandError` — then `_plan_numeric_mint` must let it out around the collection, and the test is what proves that.

Adjust the numeric local-part format string in both numeric tests to whatever Step 5 of Task 7 confirmed (`LOCAL_PART_WIDTH`).

- [ ] **Step 2: Run them to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_annotation_promote.py tests/test_promote_numeric_mint.py
```

Expected: many failures, including `AttributeError: 'PromotionTarget' object has no attribute 'mint'` from the existing tests. That is the Task 7 breakage this task repairs.

- [ ] **Step 3: Rewrite `apply_candidates`**

```python
def apply_candidates(
    candidates: list[PromotionCandidate],
    *,
    sidecar_path: Path,
    project_root: Path,
    paper_ref: str,
    as_of: date | None = None,
    targets: dict[str, PromotionTarget] | None = None,
) -> ApplyReport:
    """Plan every MINT/LINK candidate, aggregate every refusal, then write.

    All-or-nothing against DETERMINISTIC preflight failures only. The write stage can still
    fail partway on I/O or concurrent drift, and says so in its error (design §4.2). No
    transactional rollback is claimed anywhere.
    """
    targets = targets if targets is not None else build_targets()
    report = ApplyReport()
    backlinks: dict[str, str] = {}
    refusals: list[str] = []

    # Environment precondition, aborts immediately: an unreadable sidecar is not a property
    # of any candidate and no candidate-level fix exists.
    sidecar = read_sidecar_strict(sidecar_path)

    planned_text_by_path: dict[Path, str] = {}
    # path -> (kind, local_part, number) for a numeric create, None for a slug-addressed
    # create. A path absent from this map is an update. One map, not two structures that
    # can disagree about what a path is.
    creates: dict[Path, tuple[str, str, int] | None] = {}
    # One propose_number per KIND, then allocate in memory: propose_number is read-only, so
    # repeated calls before writing return the same number and every candidate in the batch
    # would be handed the same one.
    next_number: dict[str, int] = {}

    def composed(path: Path) -> str | None:
        if path in planned_text_by_path:
            return planned_text_by_path[path]
        if not path.exists():
            return None
        planned_text_by_path[path] = current_text(path)
        return planned_text_by_path[path]

    for c in candidates:
        if c.decision not in ("MINT", "LINK"):  # COLLISION / SKIP — not applied
            report.skipped[c.reason] += 1
            continue
        try:
            if c.decision == "MINT":
                target = targets[c.kind]
                assigned: int | None = None
                if not target.slug_addressed:
                    if c.kind not in next_number:
                        next_number[c.kind] = propose_number(project_root, c.kind)
                    assigned = next_number[c.kind]
                    next_number[c.kind] += 1
                dest = entity_dest(f"{c.kind}:{c.slug}", project_root) if target.slug_addressed else None
                planned = target.plan_mint(
                    c, [paper_ref, c.ref], project_root, as_of, assigned,
                    composed(dest) if dest is not None else None,
                )
                planned_text_by_path[planned.path] = planned.post_image
                if planned.operation == "create":
                    kind, local_part = planned.entity_id.split(":", 1)
                    creates[planned.path] = (
                        (kind, local_part, planned.claim_number)
                        if planned.claim_number is not None
                        else None
                    )
                    report.minted += 1
                else:
                    report.linked += 1
                backlinks[c.frag] = planned.entity_id
            else:  # LINK
                assert c.slug is not None  # "<kind>:<local_part>"
                dest = entity_dest(c.slug, project_root)
                before = composed(dest)
                if before is None:
                    raise PromotionApplyError(f"LINK target {c.slug} does not exist at {dest}")
                # Accrue BOTH provenance refs; render_entity_source_refs dedups, preserves the
                # (possibly hand-authored) prose body, and advances `updated` when it appends.
                post_image, _changed = render_entity_source_refs(
                    before, [paper_ref, c.ref], entity_path=dest, as_of=as_of
                )
                planned_text_by_path[dest] = post_image
                report.linked += 1
                backlinks[c.frag] = c.slug
        except (EntityCommandError, PromotionApplyError) as exc:
            # Candidate-local and deterministic: collect and keep planning, so an operator
            # who fixes one refusal is not ambushed by the next.
            refusals.append(f"{c.ref}: {exc}")

    if refusals:
        joined = "\n  ".join(refusals)
        raise PromotionApplyError(
            f"{len(refusals)} candidate(s) were refused and nothing was written:\n  {joined}"
        )

    edits = edits_for_planned_texts(
        planned_text_by_path, creates,
        reason_create="promotion_mint", reason_update="promotion_accrual",
    )

    if backlinks:
        new_anns = tuple(
            dataclasses.replace(a, promoted_to=backlinks[a.id]) if a.id in backlinks else a
            for a in sidecar.annotations
        )
        sidecar_text = serialize_sidecar(dataclasses.replace(sidecar, annotations=new_anns))
        edits[sidecar_path] = plan_update(sidecar_path, sidecar_text, "promotion_sidecar")

    written: list[str] = []
    for edit in sorted(edits.values(), key=lambda e: e.path.as_posix()):
        if not edit.changed:
            continue
        try:
            publish_edit(edit, project_root=project_root)
        except (OSError, EntityCommandError, EntityWriteError) as exc:
            raise PromotionApplyError(
                f"[stage=write, files_written={len(written)}, written_paths={tuple(written)}] "
                f"failed to write {path_string(edit.path)}: {exc}"
            ) from exc
        written.append(path_string(edit.path))
        if edit.operation == "create":
            report.written_paths.append(str(edit.path))

    return report
```

The wrap set is `(OSError, EntityCommandError, EntityWriteError)`. These are **sibling** `ValueError` subclasses — `EntityCommandError` (`entities.py:47`), `EntityWriteError` (`dag/entity_frontmatter.py:314`) — so catching one catches neither of the others. An `EntityCommandError`-only wrapper would let the create publish's own refusal escape naked, which is the one failure preflight was added to make legible. `PlannedEditDriftError` is covered by inheritance from `EntityCommandError`.

- [ ] **Step 4: Add the imports**

At the top of `promote.py`:

```python
from science_model.frontmatter import split_frontmatter

from science_tool.annotation.io import serialize_sidecar
from science_tool.annotation.planned_edits import (
    current_text,
    edits_for_planned_texts,
    path_string,
    plan_update,
    publish_edit,
)
from science_tool.dag.entity_frontmatter import EntityWriteError, render_create
from science_tool.entities import EntityCommandError, EntityDegradationError, render_entity_source_refs
from science_tool.entity_reservation import LOCAL_PART_WIDTH, propose_number
```

Remove the now-unused `append_entity_source_ref`, `create_entity_file`, `reserve_entity`, `_atomic_replace_text` and `anno_io` imports if nothing else in the module uses them. The slice-1 `except EntityDegradationError` translation added in Task 4 is **replaced** by the aggregation above — delete it.

- [ ] **Step 5: Run the tests**

```bash
cd science && uv run --frozen pytest tests/test_annotation_promote.py tests/test_promote_numeric_mint.py tests/test_annotate_promote_cli.py tests/test_promote_qh_integration.py tests/test_promote_render_frontmatter_golden.py
```

Expected: all pass. Existing tests that asserted immediate-write behavior may need updating — where one does, check whether it was asserting *the behavior this design removes* (fine to update) or *a property that must survive* (fix the code instead).

- [ ] **Step 6: Certify the aggregation by mutation**

Change `refusals.append(...)` to `raise PromotionApplyError(...)` and re-run:

```bash
cd science && uv run --frozen pytest tests/test_annotation_promote.py::test_apply_candidates_aggregates_every_candidate_local_refusal
```

Expected: FAIL — only `bad-a` is named. Revert.

- [ ] **Step 7: Certify the wrap set by mutation**

Narrow the write-stage `except` tuple to `(OSError,)` and re-run:

```bash
cd science && uv run --frozen pytest tests/test_promote_numeric_mint.py::test_a_write_stage_failure_reports_what_was_already_written
```

Expected: FAIL — the `EntityCommandError` from `claim_number_in_dir` escapes naked and the partial-state diagnostic is lost. Revert.

- [ ] **Step 8: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/annotation/promote.py science/tests/
git commit -m "feat(promote): preflight the promotion batch before writing anything"
```

---

### Task 9: Plan the prose decomposition index

`ProseDecompositionStore.record_promotion` is a read-modify-write of one JSON file per source slug, called four times across the two prose workflows. **Multiple rows in a batch share one index**, so its post-images must compose exactly as entity files do (§4.5). This task adds the pure planning sibling; Task 10 uses it.

**Files:**
- Modify: `science/src/science_tool/annotation/prose_decomposition.py:211-217`
- Test: `science/tests/test_prose_decomposition.py`

**Interfaces:**
- Produces:

```python
class ProseDecompositionStore:
    def plan_promotion(
        self, source_slug: str, fingerprint: str, promoted_to: str, *, state: dict | None = None
    ) -> dict:
        """Return the index state after recording this promotion. Writes nothing.

        `state` is the COMPOSED index so far; pass the previous call's return value so two
        rows sharing one source slug produce one index carrying both promotions, rather than
        two writes where the second drops the first. `None` loads from disk.
        """
```

- `record_promotion` keeps its current signature and behavior — resynthesis and other callers still use it. It is reimplemented in terms of `plan_promotion` so there is one place that knows the index's shape.
- Also produces `serialize_index_state(state: dict) -> str` at module level, so a planner can turn the composed state into the exact text apply will publish. It must produce byte-identical output to `_atomic_write_json`; read that function and match its `json.dumps` arguments exactly.

- [ ] **Step 1: Write the failing composition test**

Add to `science/tests/test_prose_decomposition.py`:

```python
def test_plan_promotion_composes_across_rows_and_writes_nothing(tmp_path: Path):
    """Two prose rows sharing one source slug must produce ONE index carrying both
    promotions, not two writes where the second drops the first."""
    store, slug, fingerprints = _store_with_two_units(tmp_path)  # existing-style helper
    before = store.index_path(slug).read_text(encoding="utf-8")

    state = store.plan_promotion(slug, fingerprints[0], "proposition:a")
    state = store.plan_promotion(slug, fingerprints[1], "proposition:b", state=state)

    assert state["units"][fingerprints[0]]["promoted_to"] == "proposition:a"
    assert state["units"][fingerprints[1]]["promoted_to"] == "proposition:b"
    # Planning wrote nothing.
    assert store.index_path(slug).read_text(encoding="utf-8") == before


def test_plan_promotion_rejects_an_unknown_fingerprint(tmp_path: Path):
    store, slug, _ = _store_with_two_units(tmp_path)

    with pytest.raises(DecompositionError):
        store.plan_promotion(slug, "sha256:nope", "proposition:a")


def test_serialize_index_state_matches_what_record_promotion_writes(tmp_path: Path):
    """The planner's text must be byte-identical to the writer's, or a planned index write
    would produce a spurious diff."""
    store, slug, fingerprints = _store_with_two_units(tmp_path)

    planned = serialize_index_state(store.plan_promotion(slug, fingerprints[0], "proposition:a"))
    store.record_promotion(source_slug=slug, fingerprint=fingerprints[0], promoted_to="proposition:a")

    assert store.index_path(slug).read_text(encoding="utf-8") == planned
```

- [ ] **Step 2: Run them to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_prose_decomposition.py -k plan_promotion
```

Expected: FAIL — `AttributeError: 'ProseDecompositionStore' object has no attribute 'plan_promotion'`.

- [ ] **Step 3: Add `plan_promotion` and `serialize_index_state`**

Read `_atomic_write_json` first so the serializer matches it exactly:

```bash
cd science && grep -n "_atomic_write_json" -A 8 src/science_tool/annotation/prose_decomposition.py | head -20
```

Then, in `science/src/science_tool/annotation/prose_decomposition.py`:

```python
def serialize_index_state(state: dict) -> str:
    """The exact text `_atomic_write_json` would write for `state`."""
    return json.dumps(state, indent=2, sort_keys=True) + "\n"   # MATCH _atomic_write_json
```

and on the store:

```python
    def plan_promotion(
        self, source_slug: str, fingerprint: str, promoted_to: str, *, state: dict | None = None
    ) -> dict:
        """Return the index state after recording this promotion. Writes nothing.

        `state` is the COMPOSED index so far -- pass the previous call's return value so two
        rows sharing one source slug produce one index carrying both promotions, rather than
        two writes where the second drops the first. `None` loads from disk.
        """
        source_slug = _validate_store_slug(source_slug)
        state = copy.deepcopy(self.load_index(source_slug)) if state is None else copy.deepcopy(state)
        if fingerprint not in state["units"]:
            raise DecompositionError(f"unknown decomposition unit fingerprint: {fingerprint}")
        state["units"][fingerprint]["promoted_to"] = promoted_to
        return state

    def record_promotion(self, source_slug: str, fingerprint: str, promoted_to: str) -> None:
        state = self.plan_promotion(source_slug, fingerprint, promoted_to)
        _atomic_write_json(self.index_path(_validate_store_slug(source_slug)), state)
```

Import `copy`. The deep copy is what makes `plan_promotion` pure — mutating the caller's dict would make composition depend on aliasing.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_prose_decomposition.py
```

Expected: all pass. If `test_serialize_index_state_matches_what_record_promotion_writes` fails, the `json.dumps` arguments do not match `_atomic_write_json` — fix `serialize_index_state`, not the test.

- [ ] **Step 5: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/prose_decomposition.py science/tests/test_prose_decomposition.py
git commit -m "feat(prose): plan decomposition-index promotions without writing"
```

---

### Task 10: Both prose workflows become plan-then-apply

The last two immediate-write workflows. `promote_prose_unit` handles one unit; `apply_prose_promotion_plan` loops over rows and is the one where composition across a shared index matters. When both are converted, `append_entity_source_ref` has no production callers left and is deleted (§3.3).

**Files:**
- Modify: `science/src/science_tool/annotation/prose_promote.py:148-260`
- Modify: `science/src/science_tool/annotation/prose_promotion_batch.py:77-152`
- Modify: `science/src/science_tool/entities.py` (delete `append_entity_source_ref`)
- Test: `science/tests/test_prose_promote.py`, `science/tests/test_prose_promotion_batch.py`, `science/tests/test_entity_writer.py`

**Interfaces:**
- Consumes: everything from Tasks 6–9. `plan_mint` is now `PlanMintFn`, so both call sites pass six arguments.
- Produces: no new public names. Both functions keep their signatures and `ApplyReport` return type.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_prose_promotion_batch.py`:

```python
def test_two_rows_sharing_a_source_slug_produce_one_index_write(tmp_path: Path):
    """The index is a read-modify-write of ONE file per source slug. Two independent writes
    from the same pre-image would drop the first row's promotion."""
    project_root, plan = _two_row_plan(tmp_path)  # both rows share one source slug

    apply_prose_promotion_plan(project_root, plan)

    index = ProseDecompositionStore(project_root).load_index(plan.source_slug)
    promoted = {row.get("promoted_to") for row in index["units"].values()}
    assert None not in promoted
    assert len(promoted) == 2


def test_a_refused_row_leaves_the_index_and_every_entity_unchanged(tmp_path: Path):
    project_root, plan = _two_row_plan_with_one_degrading_link(tmp_path)
    store = ProseDecompositionStore(project_root)
    index_before = store.index_path(plan.source_slug).read_text(encoding="utf-8")
    entities_before = {
        p: p.read_text(encoding="utf-8")
        for p in (project_root / "entities").rglob("*.md")
    }

    with pytest.raises(ProsePromotionError):
        apply_prose_promotion_plan(project_root, plan)

    assert store.index_path(plan.source_slug).read_text(encoding="utf-8") == index_before
    for path, text in entities_before.items():
        assert path.read_text(encoding="utf-8") == text


def test_index_drift_between_planning_and_apply_refuses(tmp_path: Path, monkeypatch):
    """The third planned update. All three -- entity record, sidecar, decomposition index --
    go through the same precondition; only the first is obviously an update."""
    project_root, plan = _two_row_plan(tmp_path)
    store = ProseDecompositionStore(project_root)
    index_path = store.index_path(plan.source_slug)

    real_publish = planned_edits.publish_edit

    def drift_the_index_first(edit, *, project_root):
        if edit.path == index_path:
            index_path.write_text('{"units": {}}\n', encoding="utf-8")
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(planned_edits, "publish_edit", drift_the_index_first)

    with pytest.raises(ProsePromotionError) as excinfo:
        apply_prose_promotion_plan(project_root, plan)

    assert "stage=write" in str(excinfo.value)
    assert index_path.read_text(encoding="utf-8") == '{"units": {}}\n'
```

Add to `science/tests/test_entity_writer.py`:

```python
def test_append_entity_source_ref_is_gone():
    """Its production callers are gone; the adapter goes with them rather than becoming a
    compatibility layer."""
    import science_tool.entities as entities

    assert not hasattr(entities, "append_entity_source_ref")
```

- [ ] **Step 2: Run them to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_prose_promotion_batch.py tests/test_entity_writer.py::test_append_entity_source_ref_is_gone
```

Expected: FAIL — the batch tests fail on `AttributeError: 'PromotionTarget' object has no attribute 'mint'` (the Task 7 breakage), and the adapter test fails because the function still exists.

- [ ] **Step 3: Convert `apply_prose_promotion_plan`**

Split `_apply_validated_row` into a planner and let the caller publish. In `science/src/science_tool/annotation/prose_promotion_batch.py`:

```python
def apply_prose_promotion_plan(project_root: Path, plan: ProsePromotionPlan) -> ApplyReport:
    """Plan every row, aggregate every refusal, then write.

    Recovered units can inherit promote_prose_unit's empty ApplyReport because the entity
    already has the artifact unit ref and apply only records decomposition index recovery.
    """
    project_root = project_root.resolve()
    targets = build_targets()
    current_rows = [_validate_current_row(project_root, row) for row in _plan_rows(plan)]
    _reject_duplicate_mint_targets(current_rows, targets)

    store = ProseDecompositionStore(project_root)
    report = ApplyReport()
    refusals: list[str] = []
    planned_text_by_path: dict[Path, str] = {}
    creates: dict[Path, tuple[str, str, int] | None] = {}
    index_state_by_slug: dict[str, dict] = {}
    next_number: dict[str, int] = {}

    def composed(path: Path) -> str | None:
        if path in planned_text_by_path:
            return planned_text_by_path[path]
        if not path.exists():
            return None
        planned_text_by_path[path] = current_text(path)
        return planned_text_by_path[path]

    for current in current_rows:
        row = current.row
        candidate = current.candidate
        try:
            promoted_to = _plan_row(
                project_root, current, targets,
                composed=composed,
                planned_text_by_path=planned_text_by_path,
                creates=creates,
                next_number=next_number,
                report=report,
            )
            if promoted_to is not None:
                index_state_by_slug[row.source_slug] = store.plan_promotion(
                    row.source_slug, row.fingerprint, promoted_to,
                    state=index_state_by_slug.get(row.source_slug),
                )
        except (DecompositionError, EntityCommandError, PromotionApplyError) as exc:
            refusals.append(f"{row.unit_id}: {exc}")

    if refusals:
        joined = "\n  ".join(refusals)
        raise ProsePromotionError(
            f"{len(refusals)} row(s) were refused and nothing was written:\n  {joined}"
        )

    edits = edits_for_planned_texts(
        planned_text_by_path, creates,
        reason_create="prose_promotion_mint", reason_update="prose_promotion_accrual",
    )
    for slug, state in index_state_by_slug.items():
        index_path = store.index_path(slug)
        edits[index_path] = plan_update(
            index_path, serialize_index_state(state), "prose_decomposition_index"
        )

    written: list[str] = []
    for edit in sorted(edits.values(), key=lambda e: e.path.as_posix()):
        if not edit.changed:
            continue
        try:
            publish_edit(edit, project_root=project_root)
        except (OSError, EntityCommandError, EntityWriteError) as exc:
            raise ProsePromotionError(
                f"[stage=write, files_written={len(written)}, written_paths={tuple(written)}] "
                f"failed to write {path_string(edit.path)}: {exc}"
            ) from exc
        written.append(path_string(edit.path))
        if edit.operation == "create":
            report.written_paths.append(str(edit.path))

    return report
```

`_plan_row` is the per-row planner extracted from the current `_apply_validated_row` body: it handles the `recovered_link` early return (which produces only an index update, no entity edit), the MINT branch (`targets[candidate.kind].plan_mint(candidate, [row.source_ref, row.artifact_unit_ref], project_root, None, assigned, composed(dest))`, with the same one-`propose_number`-per-kind rule as Task 8), and the LINK branch (`render_entity_source_refs` twice into `planned_text_by_path`, composing). It returns the `promoted_to` string or `None` for SKIP.

`edits_for_planned_texts` is the shared "one `PlannedFileEdit` per path, after composition" helper defined in Task 6 — `apply_candidates` uses the same one. Populate `creates[planned.path]` in `_plan_row`'s MINT branch exactly as Task 8 does: `(kind, local_part, planned.claim_number)` when `claim_number is not None`, else `None`.

`DecompositionError` is **not** in the write-stage wrap set, and does not need to be: no `record_promotion` call survives into the write stage. If an implementation leaves one there, the wrap set is wrong — but the correct fix is to plan it, not to widen the tuple.

Both prose modules need these imports, replacing `append_entity_source_ref`:

```python
from science_tool.annotation.planned_edits import (
    current_text,
    edits_for_planned_texts,
    path_string,
    plan_update,
    publish_edit,
)
from science_tool.annotation.prose_decomposition import serialize_index_state
from science_tool.dag.entity_frontmatter import EntityWriteError
from science_tool.entities import EntityCommandError, find_entity, render_entity_source_refs
from science_tool.entity_reservation import propose_number
```

- [ ] **Step 4: Convert `promote_prose_unit`**

`promote_prose_unit` handles one unit, so it needs no aggregation — but it must still plan then write, so a refusal leaves nothing half-written. Replace the write section of `science/src/science_tool/annotation/prose_promote.py:220-260` with the same shape: plan the entity edit and the index state, then publish both through `publish_edit`, wrapping with the same `(OSError, EntityCommandError, EntityWriteError)` tuple and raising `ProsePromotionError`. The existing `except (DecompositionError, EntityCommandError, PromotionApplyError)` around the planning section stays — it is the translation, and it now covers a planning failure rather than a partial write.

The recovery path at `:185-195` (`store.record_promotion` after finding the entity already carries the ref) also becomes a planned write: `store.plan_promotion(...)` → `plan_update(store.index_path(source_slug), serialize_index_state(state), ...)` → `publish_edit`.

- [ ] **Step 5: Delete `append_entity_source_ref`**

Confirm it has no production callers left:

```bash
cd science && grep -rn "append_entity_source_ref" src/
```

Expected: no results. Then delete the function from `science/src/science_tool/entities.py` and remove it from `tests/test_entity_writer.py`'s import list. Delete the two tests that exercised it directly (`test_append_entity_source_ref_preserves_body_and_updates_timestamp`, `test_append_entity_source_ref_noops_when_ref_exists`) — the behavior they covered is now covered by `render_entity_source_refs`'s own tests plus the publish tests in `test_planned_edits.py`. Do not leave it as a compatibility shim.

- [ ] **Step 6: Run the prose suites**

```bash
cd science && uv run --frozen pytest tests/test_prose_promote.py tests/test_prose_promotion_batch.py tests/test_prose_decomposition.py tests/test_annotate_prose_decomposition_cli.py tests/test_entity_writer.py
```

Expected: all pass.

- [ ] **Step 7: Run the whole affected surface**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py tests/test_entity_writer.py \
  tests/test_hypothesis_consumers.py tests/test_annotation_promote.py \
  tests/test_promote_numeric_mint.py tests/test_annotate_promote_cli.py \
  tests/test_promote_qh_integration.py tests/test_promote_render_frontmatter_golden.py \
  tests/test_prose_promote.py tests/test_prose_promotion_batch.py \
  tests/test_prose_decomposition.py tests/test_annotate_prose_decomposition_cli.py \
  tests/test_proposition_reconciliation_apply.py tests/test_proposition_reconciliation_cli.py \
  tests/test_proposition_reconciliation_plan.py tests/test_proposition_resynthesis_apply.py
```

Expected: all pass.

- [ ] **Step 8: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/annotation/prose_promote.py \
        science/src/science_tool/annotation/prose_promotion_batch.py \
        science/src/science_tool/annotation/planned_edits.py \
        science/src/science_tool/entities.py \
        science/tests/
git commit -m "feat(prose): preflight both prose promotion workflows"
```

- [ ] **Step 10: Run the full CLI suite**

This change crosses subsystem boundaries — serialization, entity writers, and three workflow surfaces — which is a full-suite trigger. The top-level agent owns this run and must pass an explicit long timeout; it takes ~7 minutes.

```bash
cd science && uv run --frozen pytest
```

Expected: green. Report the actual summary line — do not read a dots-only tail as green.

---

## Notes for the implementer

**Scope-out.** These are deliberate, not oversights (§6):
- No repair of the 183 pre-existing base-shape-invalid records. That is a separate slice.
- No typed-shape certification on these paths — base shape only.
- No transactional rollback. The write stage reports partial state; it does not undo it.
- No arming of `proposition` or `evidence-line`; neither mixin exists yet.
- `render_update`'s stale-owned-key hole (`dag/entity_frontmatter.py:298-300`) stays open.
- `entities.py:317-318`'s stale docstring stays as it is.

**If a test in an existing suite fails after a conversion**, decide which of two things it was asserting before changing anything: the immediate-write behavior this design deliberately removes (update the test), or a property that must survive the conversion (fix the code). Do not update a test to match new behavior without answering that question in the commit message.

**Certify every guard by mutation.** Each task with a guard names the mutation that must make a specific test fail. A guard that cannot be made to fail is not certified, and this plan treats an uncertified guard as unfinished work.
