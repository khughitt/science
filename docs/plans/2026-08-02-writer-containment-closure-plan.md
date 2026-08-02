# Writer Containment Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** No writer may turn a base-shape-valid entity record into an invalid one, and a promotion batch that would do so writes nothing at all.

**Architecture:** Two sequenced slices, eight tasks. Slice 1 (Tasks 1–5) makes the two kind-agnostic renderers in `entities.py` text-in/text-out and makes them **refuse the one forbidden transition** (base-valid → base-invalid), then gives every workflow that reaches them a translated — and where a batch exists, aggregated — error. Slice 2 (Tasks 6–8) converts every planned write onto one drift-refusing publish primitive and turns the three write-as-you-go workflows into plan-then-apply.

**Design of record:** [`docs/plans/2026-08-02-writer-containment-closure-design.md`](2026-08-02-writer-containment-closure-design.md). Section references below (§2.2, §4.3, …) point into it.

**Tech Stack:** Python 3.13, Pydantic v2, PyYAML, Click + `CliRunner`, pytest. Package root is `science/` — all `uv` commands run from there.

## Global Constraints

- **All `uv` commands run from `science/`**, never the repo root. There is no root `pyproject.toml`.
- **Run scoped test selections**, not the full suite. The full CLI suite is ~12k tests and takes many minutes — far longer than the default 120s command timeout. Each task names the exact selection to run; only Task 8's last step runs the whole thing, with an explicit timeout.
- **Never run two pytest suites concurrently in the same worktree** — they race on shared test-output paths.
- **`pytest -q` is wrong here**: the package's `addopts` already carries `-q`, so adding another yields `-qq` and suppresses the summary line. Run bare `pytest`.
- Lint and types, from `science/`: `uv run ruff check` (line-length 120) and `uv run pyright`. Pyright is configured once by `pyrightconfig.json` at the repo root; test directories are **not** type-checked.
- Conventional commits. **No AI-attribution trailer or footer** on any commit, PR, or comment.
- Composition over inheritance; explicit over defensive; fail early rather than silent fallback.
- **No "legacy" or "compatibility" layers**, and no `Unified` prefix on component names.
- In documentation and code, write filepaths as `~/d/...` or repo-relative — never `/home/keith/...` or `/mnt/ssd/Dropbox/...`.
- **The forbidden transition is exactly one**: pre-image valid AND post-image invalid → refuse. `invalid → invalid` and `invalid → valid` both write. This branch performs **no intentional backfill** (§2).
- **Validate the post-image after rendering AND reparsing it** — never the in-memory mapping (§2.1). The rendered text is what becomes authored source; the mapping is not the artifact, and any difference introduced between building the mapping and emitting the text is invisible to a mapping-reading guard. (The unquoted-date example the design originally gave does **not** discriminate — measured 2026-08-02; see §2.1's correction and Task 3.)
- **Base shape only.** `EntityValidator().validate_persisted_base_shape`. No typed certification on these paths (§2, §6).
- The 183 records that already fail base shape are **not** repaired by this branch (§6).
- **Every commit leaves the tree green.** No task commits a deliberately broken intermediate API.

## What base 2.0 actually constrains

Read this before writing any degradation fixture. `science/model/src/science_model/schemas/science-entity-base-2.0.json` requires exactly `["id", "kind", "title", "created", "updated"]`, and constrains only:

| field | constraint |
|---|---|
| `id` | string matching `^[a-z][a-z0-9-]*:[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` |
| `kind` | string matching `^[a-z][a-z0-9-]*$` |
| `title` | string, `minLength: 1` |
| `created`, `updated` | string, `format: date` |
| `status` | string (when present) |

**`source_refs`, `related` and `superseded_by` have no schema at all.** Two consequences the fixtures in this plan depend on:

1. A `source_refs` mapping is **base-valid**, not invalid. It cannot be used to construct any transition.
2. `render_entity_source_refs` **cannot degrade a base-valid record through its own logic**: it touches only `source_refs` (unconstrained) and `updated` (which it always sets to a valid ISO date). Its guard is protection against future change, and the only honest way to test it is to inject a corrupting renderer.

So guard tests use `render_entity_frontmatter_updates` with genuinely degrading updates (`{"title": ""}`, `{"created": date(...)}`) and, for the source-refs renderer, a monkeypatched `entities._render_markdown`. Translation and aggregation tests monkeypatch the **workflow-local** renderer name to raise `EntityDegradationError` directly — those tests are about error routing, not about the guard's own logic, and constructing a real degradation through five layers of fixture would test the fixture instead.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/science_tool/annotation/planned_edits.py` (new) | The shared plan-then-apply vocabulary: `PlannedFileEdit`, its constructors, the CRLF-preserving reader, hashing, changed/no-op partitioning, `PlannedEditDriftError`, `publish_edit`, `edits_for_planned_texts` | 1, 6 |
| `src/science_tool/entities.py` | The two renderers become text-in/text-out and carry the degradation guard; `EntityDegradationError` lives here | 2, 3, 8 |
| `src/science_tool/dag/entity_frontmatter.py` | `publish_new_file` extracted from `create_entity_file` so planning and publishing can be separated | 6 |
| `src/science_tool/annotation/proposition_reconciliation_apply.py` | Loses the hoisted helpers; gains per-action refusal aggregation; publishes through `publish_edit` | 1, 4, 6 |
| `src/science_tool/annotation/proposition_resynthesis_apply.py` | Imports the hoisted helpers; publishes through `publish_edit`; its create-or-update constructor splits | 1, 6 |
| `src/science_tool/annotation/prose_decomposition.py` | `record_promotion` gains a pure planning sibling; `_canonical_json_text` becomes public | 7 |
| `src/science_tool/annotation/promote.py` | `PromotionTarget.mint` → `plan_mint`; `apply_candidates` becomes plan-then-apply with a planned sidecar | 4, 8 |
| `src/science_tool/annotation/prose_promote.py`, `prose_promotion_batch.py` | Both become plan-then-apply over the shared vocabulary | 8 |
| `tests/test_planned_edits.py` (new) | The shared vocabulary's own tests, including drift and CRLF | 1, 6 |
| `tests/test_entity_writer.py` | The four-transition matrix, the round trip, the signature change | 2, 3, 8 |
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
- The hoisted names lose their leading underscore because they are now a public module boundary. `_changed_and_noop_paths_from_path_changes`, `_live_annotation_index` and `CanonicalizationPreflight` **stay in reconciliation** — nothing else imports them and they serve reconciliation's own per-action map.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_planned_edits.py`:

```python
import dataclasses
from pathlib import Path

import pytest

from science_tool.annotation.planned_edits import (
    PlannedFileEdit,
    changed_and_noop_paths,
    current_text,
    plan_update,
    sha256_text,
)


def test_current_text_preserves_crlf(tmp_path: Path):
    """`Path.read_text()` applies universal-newline translation, which would rewrite bytes
    the edit never intended -- and the round-trip guard would then certify the rewrite as
    correct. The preserving reader at entities.py:1920-1923 is the precedent."""
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
    """A planner that could mutate an edit after constructing it could desynchronize
    final_text from after_sha256, and the drift check added in Task 6 reads both."""
    target = tmp_path / "a.md"
    target.write_text("x\n", encoding="utf-8")
    edit = plan_update(target, "y\n", "r")

    with pytest.raises(dataclasses.FrozenInstanceError):
        edit.final_text = "z\n"  # type: ignore[misc]
```

- [ ] **Step 2: Run the tests to verify they fail**

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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


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

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py
```

Expected: 4 passed.

- [ ] **Step 5: Repoint reconciliation**

In `science/src/science_tool/annotation/proposition_reconciliation_apply.py`:

1. Delete the `PlannedFileEdit` dataclass (currently `:39-45`) and the five helpers `_path_string`, `_sha256_text`, `_current_text`, `_changed_and_noop_paths`, `_edit` (currently `:157-200`).
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

In `science/src/science_tool/annotation/proposition_resynthesis_apply.py`, replace the cross-module import block at `:13-21` so the six generic names come from `planned_edits`:

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

Rename the uses in this module the same way. `_new_or_existing_edit` (`:501`) stays here for now — it is resynthesis's own constructor for a path that may not exist yet, and Task 6 splits it.

- [ ] **Step 7: Run the affected suites**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py tests/test_proposition_reconciliation_apply.py tests/test_proposition_reconciliation_cli.py tests/test_proposition_reconciliation_plan.py tests/test_proposition_resynthesis_apply.py
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

Expected: FAIL — the renderer treats the string as a `Path` (`AttributeError: 'str' object has no attribute 'open'`).

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

The unchanged branches now return `current_text` directly instead of re-reading the file, which also removes a redundant read.

- [ ] **Step 4: Update `append_entity_source_ref` to be the reading adapter**

Still in `entities.py`, immediately below:

```python
def append_entity_source_ref(file_path: Path, ref: str, *, as_of: date | None = None) -> bool:
    """Append ``ref`` to an existing entity file's ``source_refs`` frontmatter, preserving
    the body. Returns True if added, False if already present. Used by promotion LINK so a
    hand-authored proposition's prose is never clobbered. When a ref is added, `updated`
    advances to ``as_of`` (or today), matching other entity mutations.

    This is the read-render-write adapter for callers that still write as they go. It is
    deleted in Task 8, once the promotion and prose workflows plan their writes.
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

For each, read the file first and pass its text:

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

Read **"What base 2.0 actually constrains"** at the top of this plan before writing the fixtures. In particular, `render_entity_source_refs` cannot reach the guard through its own logic, so its test injects a corrupting renderer.

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

import science_tool.entities as entities
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

# Empty `title` is the base-2.0 violation 769 of piece 3's 792 repaired records carried:
# `title` is required with minLength 1.
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
    """No INTENTIONAL backfill, but a write whose own content happens to satisfy base shape
    is allowed through."""
    rendered, changed = render_entity_frontmatter_updates(
        INVALID, {"title": "a real claim"}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
    )
    assert changed is True
    assert "title: a real claim" in rendered


def test_source_refs_renderer_carries_the_same_guard(tmp_path: Path, monkeypatch):
    """Both renderers, not just one: append_entity_source_ref already reaches `hypothesis`
    through promotion LINK, and `hypothesis` is an armed kind.

    This renderer cannot degrade a base-valid record through its own logic -- base 2.0 does
    not constrain `source_refs` at all, and `updated` is always stamped as a valid ISO date.
    Its guard is protection against FUTURE change, so the corruption is injected at the one
    seam both renderers share.
    """
    real_render_markdown = entities._render_markdown

    def corrupt_the_title(frontmatter, body):
        return real_render_markdown({**frontmatter, "title": ""}, body)

    monkeypatch.setattr(entities, "_render_markdown", corrupt_the_title)

    with pytest.raises(EntityDegradationError):
        render_entity_source_refs(
            VALID, ["paper:new"], entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
        )
```

- [ ] **Step 2: Write the failing rendered-text test**

Also in `science/tests/test_entity_writer.py`:

```python
def test_guard_validates_the_rendered_text_not_the_in_memory_mapping(tmp_path: Path, monkeypatch):
    """§2.1 requires the guard to validate what will be PERSISTED, not the mapping that was
    dumped. The corruption is injected at `_render_markdown` -- after the mapping is built --
    so a guard reading the mapping sees a perfectly good `title` and lets the write through,
    while a guard reading the rendered text refuses.

    A `date(...)` value does NOT discriminate, though the design's §5 suggested it would:
    measured 2026-08-02, `validate_persisted_base_shape` refuses `datetime.date` identically
    whether it reads the in-memory mapping or the reparsed text, because `type: string`
    rejects the date object in both. A test built on it would pass under the mutation and
    certify nothing.
    """
    real_render_markdown = entities._render_markdown

    def corrupt_the_title(frontmatter, body):
        return real_render_markdown({**frontmatter, "title": ""}, body)

    monkeypatch.setattr(entities, "_render_markdown", corrupt_the_title)

    with pytest.raises(EntityDegradationError):
        render_entity_frontmatter_updates(
            VALID, {"status": "superseded"}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
        )


def test_a_date_object_is_refused_on_an_otherwise_valid_record(tmp_path: Path):
    """Base 2.0 requires `created` to be a string with format: date, and 23 of piece 3's 792
    records were date-quoting alone. This asserts the transition is refused; it does NOT
    certify the round trip -- see the test above for why."""
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
cd science && uv run --frozen pytest tests/test_entity_writer.py -k "valid_to or same_guard or rendered_text or date_object"
```

Expected: every one of them errors on `ImportError: cannot import name 'EntityDegradationError'` until Step 4 lands. After Step 4, the three refusal cases would fail with `DID NOT RAISE` without Step 5; the other three transitions pass either way, because they assert what must stay writable.

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

    `after_text` is REPARSED here rather than validated as the mapping that was dumped,
    because the rendered text is what becomes authored source and the mapping is not the
    artifact: anything introduced between building the mapping and emitting the text is
    invisible to a mapping-reading guard. (`certify_persisted` gives the unquoted-date
    scalar as its example; measured 2026-08-02, that case does not actually distinguish the
    two -- `type: string` rejects a `datetime.date` either way. The rule is structural.)
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

- [ ] **Step 7: Certify the rendered-text guard by mutation**

Apply exactly this mutation — make the guard read the in-memory mapping instead of the rendered text. In `_refuse_degradation`, change the signature and delete the reparse:

```python
def _refuse_degradation(before_text: str, after_frontmatter: dict, entity_path: Path) -> None:
    if not _satisfies_base_shape(before_text):
        return
    try:
        EntityValidator().validate_persisted_base_shape(after_frontmatter)   # MUTATION
    except EntityValidationError as exc:
        raise EntityDegradationError(...) from exc
```

and in both renderers pass the mapping they just built instead of the rendered text:

```python
    rendered = _render_markdown(frontmatter, body)
    _refuse_degradation(current_text, frontmatter, entity_path)   # MUTATION
    return (rendered, True)
```

Then run:

```bash
cd science && uv run --frozen pytest tests/test_entity_writer.py -k "rendered_text or same_guard"
```

Expected: **both FAIL with `DID NOT RAISE`** — the corruption lives only in `_render_markdown`'s output, so a mapping-reading guard sees an intact `title` and lets the write through. Revert with `git checkout -- science/src/science_tool/entities.py` and confirm both pass. A guard that cannot be made to fail is not certified.

Note `test_a_date_object_is_refused_on_an_otherwise_valid_record` **still passes** under this mutation. That is expected and is why it is not the certification test.

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

Resynthesis needs no code change: `_original_edit` already catches `EntityCommandError` and raises `ResynthesisApplyError`, so `EntityDegradationError` is caught by inheritance. The two prose workflows are covered the same way. Inheritance coverage is real but invisible, so this task pins it with tests.

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_apply.py` (the `for action in actions` loop in `plan_canonicalization_apply`)
- Modify: `science/src/science_tool/annotation/promote.py` (`apply_candidates`)
- Test: `science/tests/test_proposition_reconciliation_apply.py`, `science/tests/test_annotation_promote.py`

**Interfaces:**
- Consumes: `EntityDegradationError` from `science_tool.entities` (Task 3).
- Produces: no new public names. `plan_canonicalization_apply` raises `ReconciliationApplyError` naming **every** refused record; `apply_candidates` raises `PromotionApplyError`.
- The `apply_candidates` translation is **temporary by design** — Task 8 replaces it with the aggregated report. It exists so slice 1 can land alone without introducing a raw traceback in the promotion CLI for exactly the case the guard exists to report.

- [ ] **Step 1: Write the failing aggregation test**

Add to `science/tests/test_proposition_reconciliation_apply.py`. This module's existing helpers are `_action(...)`, `_manual_ready_plan(actions=...)`, `_manifest(root)` and `_proposition(root, slug, title, ...)` — read them at `:39-200` before writing.

The test monkeypatches the **workflow-local** renderer name to raise. That is deliberate: this test is about error routing, and a real degradation would have to be smuggled through five layers of fixture, testing the fixture instead of the routing.

```python
def test_canonicalization_aggregates_every_degradation_refusal(tmp_path: Path, monkeypatch) -> None:
    """plan_canonicalization_apply loops over the selected action set with both renderer
    calls inside the loop, so an N-action set can refuse N times. Aborting on the first
    would make an operator re-run the command once per bad record."""
    import science_tool.annotation.proposition_reconciliation_apply as recon

    _manifest(tmp_path)
    for slug in ("a", "b", "c", "d"):
        _proposition(tmp_path, slug, f"Claim {slug}")

    def refuse(current_text, updates, *, entity_path, as_of=None):
        raise EntityDegradationError(f"{entity_path} would be degraded")

    monkeypatch.setattr(recon, "render_entity_frontmatter_updates", refuse)

    plan = _manual_ready_plan(
        actions=(
            _action(action_id="act-1", canonical="proposition:a",
                    members=("proposition:a", "proposition:b")),
            _action(action_id="act-2", canonical="proposition:c",
                    members=("proposition:c", "proposition:d")),
        )
    )

    with pytest.raises(ReconciliationApplyError) as excinfo:
        recon.plan_canonicalization_apply(tmp_path, plan)

    message = str(excinfo.value)
    assert "b.md" in message
    assert "d.md" in message
    # Planning refused, so nothing was written.
    assert "superseded" not in (tmp_path / "entities" / "propositions" / "b.md").read_text(
        encoding="utf-8"
    )
```

Import `EntityDegradationError` from `science_tool.entities` at the top of the test module.

- [ ] **Step 2: Run it to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_proposition_reconciliation_apply.py::test_canonicalization_aggregates_every_degradation_refusal
```

Expected: FAIL — `EntityDegradationError` escapes the loop on the first refusal, so the raised type is wrong and only one record is named.

- [ ] **Step 3: Aggregate inside the action loop**

In `plan_canonicalization_apply`, add a refusal accumulator before the `for action in actions:` loop:

```python
    degradations: list[str] = []
```

Wrap the canonical-refs renderer call:

```python
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
```

and the duplicate-supersession call:

```python
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

Import `EntityCommandError` from `science_tool.entities` if this module does not already. Catching the base class rather than `EntityDegradationError` is deliberate: `find_entity` and the renderers can both raise `EntityCommandError`, and both are candidate-local planning failures the operator wants reported together.

- [ ] **Step 4: Run it to verify it passes**

```bash
cd science && uv run --frozen pytest tests/test_proposition_reconciliation_apply.py::test_canonicalization_aggregates_every_degradation_refusal
```

Expected: PASS.

- [ ] **Step 5: Write the failing promotion translation test**

Add to `science/tests/test_annotation_promote.py`. This module builds its projects inline — model the setup on `test_apply_links_to_existing_appends_both_refs_preserves_prose` (`:252`), which is the LINK path this test exercises.

```python
def test_apply_candidates_translates_a_degradation_refusal(tmp_path, monkeypatch):
    """The promotion CLI wraps apply_candidates in `except PromotionApplyError` alone
    (annotation/cli.py:2640-2642), so an EntityDegradationError would surface as a raw
    traceback for exactly the case the guard exists to report."""
    from datetime import date

    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import (
        PromotionApplyError,
        apply_candidates,
        collect_promotable,
        decide_candidates,
        load_corpora,
    )
    from science_tool.annotation.query import read_sidecar_strict
    from science_tool.entities import EntityDegradationError

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    existing = tmp_path / "entities" / "propositions" / "known-claim.md"
    existing.write_text(
        '---\nid: proposition:known-claim\nkind: proposition\ntitle: Known claim\n'
        'status: draft\nsource_refs:\n  - "paper:other"\n'
        'created: "2026-06-01"\nupdated: "2026-06-01"\n---\n'
        "# Known claim\n\n## Claim\n\nHand-authored prose.\n",
        encoding="utf-8",
    )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Known claim.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(
        _statement_ann("a-1", "Known claim", status=Status.OPEN),
    )))

    def refuse(current_text, refs_to_append, *, entity_path, as_of=None):
        raise EntityDegradationError(f"{entity_path} would be degraded")

    monkeypatch.setattr(promote_mod, "render_entity_source_refs", refuse)

    corpora, derived = load_corpora(tmp_path)
    promotable, _ = collect_promotable(read_sidecar_strict(sp), sp, tmp_path, derived_refs=derived)
    candidates = decide_candidates(promotable, corpora["proposition"])
    assert candidates[0].decision == "LINK"

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(candidates, sidecar_path=sp, project_root=tmp_path,
                         paper_ref="paper:p", as_of=date(2026, 6, 16))

    assert "known-claim" in str(excinfo.value)
```

Note this test monkeypatches `promote_mod.render_entity_source_refs`, which requires the LINK path to call the renderer directly rather than through `append_entity_source_ref`. Change the LINK branch of `apply_candidates` in Step 6 accordingly.

- [ ] **Step 6: Translate in `apply_candidates`**

In `science/src/science_tool/annotation/promote.py`, change the LINK branch to call the renderer directly and write, so the workflow owns the renderer call it must translate:

```python
        elif c.decision == "LINK":
            assert c.slug is not None  # "<kind>:<local_part>"
            dest = entity_dest(c.slug, project_root)
            # Accrue BOTH provenance refs onto the existing entity; the renderer dedups,
            # preserves the (possibly hand-authored) prose body, and advances `updated`
            # whenever it actually appends a ref.
            post_image, changed = render_entity_source_refs(
                current_text(dest), [paper_ref, c.ref], entity_path=dest, as_of=as_of
            )
            if changed:
                _atomic_replace_text(dest, post_image)
            report.linked += 1
            backlinks[c.frag] = c.slug
```

and make the same change in the MINT-accrual branch of `_mint_proposition` (`:304`):

```python
        post_image, changed = render_entity_source_refs(
            current_text(dest), source_refs, entity_path=dest, as_of=as_of
        )
        if changed:
            _atomic_replace_text(dest, post_image)
        return MintOutcome(entity_id=prop_ref, created=False)
```

Then wrap the candidate loop:

```python
    for c in candidates:
        # Slice 1 translation: apply_candidates still writes as it goes, so a refusal must
        # not reach the CLI as EntityDegradationError. Task 8 replaces this with the
        # aggregated preflight report.
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

Add imports: `EntityDegradationError` and `render_entity_source_refs` from `science_tool.entities`, and `current_text` from `science_tool.annotation.planned_edits`. `append_entity_source_ref` is no longer used by this module — drop its import.

- [ ] **Step 7: Pin the two workflows covered by inheritance**

Resynthesis and `promote_prose_unit` need no code change — `EntityDegradationError` subclasses `EntityCommandError`, which both already catch. Inheritance coverage is real but invisible, so pin it in both.

Add to `science/tests/test_proposition_resynthesis_apply.py`. The construction is the one this module already uses at `:50-51`, via helpers it imports from `test_proposition_resynthesis` at `:17`:

```python
def test_resynthesis_surfaces_a_degradation_refusal_as_its_own_error(tmp_path: Path, monkeypatch):
    """`_original_edit` already catches EntityCommandError, so EntityDegradationError is
    covered by inheritance. This test is what would notice if that catch were ever narrowed
    to a sibling type -- EntityCommandError, EntityWriteError and DecompositionError are
    SIBLINGS, not a hierarchy, so `except EntityCommandError` catches neither of the others.
    """
    import science_tool.annotation.proposition_resynthesis_apply as resynth
    from science_tool.entities import EntityDegradationError

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    def refuse(current_text, updates, *, entity_path, as_of=None):
        raise EntityDegradationError(f"{entity_path} would be degraded")

    monkeypatch.setattr(resynth, "render_entity_frontmatter_updates", refuse)

    with pytest.raises(ResynthesisApplyError):
        resynth.plan_resynthesis_apply(tmp_path, draft)
```

`_draft_payload(ctx)` produces a supersession draft, not a `split_partial` — which matters, because `_original_updates` returns `{}` for `split_partial` and `_original_edit` then returns `None` without ever calling the renderer.

Add to `science/tests/test_prose_promote.py`. This is the **fifth** workflow, and Task 8 covers only the batch prose path — the single-unit one needs its own case. In slice 1 the LINK write still goes through `append_entity_source_ref`, so that is the local name to patch; Task 8 Step 10 updates this test to patch `render_entity_source_refs` once the workflow calls the renderer directly.

```python
def test_promote_prose_unit_surfaces_a_degradation_refusal_as_its_own_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fifth workflow. `promote_prose_unit` already catches
    (DecompositionError, EntityCommandError, PromotionApplyError), so EntityDegradationError
    is covered by inheritance -- and this is what would notice if that tuple were narrowed.
    """
    import science_tool.annotation.prose_promote as prose_promote_mod
    from science_tool.entities import EntityDegradationError

    _persist_artifact(tmp_path)
    _write_existing_proposition(tmp_path)   # makes the decision a LINK

    def refuse(file_path, ref, *, as_of=None):
        raise EntityDegradationError(f"{file_path} would be degraded")

    monkeypatch.setattr(prose_promote_mod, "append_entity_source_ref", refuse)

    with pytest.raises(ProsePromotionError):
        promote_prose_unit(
            project_root=tmp_path, source_ref="prose-source:example", unit_id="u001", apply=True
        )
```

`_write_existing_proposition` lives in `tests/test_prose_promotion_batch.py:152`; if `test_prose_promote.py` has no equivalent, copy that eight-line writer into this module rather than importing across test modules.

- [ ] **Step 8: Run the affected suites**

```bash
cd science && uv run --frozen pytest tests/test_annotation_promote.py tests/test_annotate_promote_cli.py tests/test_proposition_reconciliation_apply.py tests/test_proposition_reconciliation_cli.py tests/test_promote_qh_integration.py tests/test_proposition_resynthesis_apply.py tests/test_promote_numeric_mint.py tests/test_prose_promote.py
```

Expected: all pass.

- [ ] **Step 9: Certify the aggregation by mutation**

Change `degradations.append(...)` in the duplicate-supersession branch to `raise ReconciliationApplyError(f"{duplicate}: {exc}") from exc` and re-run:

```bash
cd science && uv run --frozen pytest tests/test_proposition_reconciliation_apply.py::test_canonicalization_aggregates_every_degradation_refusal
```

Expected: FAIL — only `b.md` is named. Revert.

- [ ] **Step 10: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

- [ ] **Step 11: Commit**

```bash
git add science/src/science_tool/annotation/proposition_reconciliation_apply.py \
        science/src/science_tool/annotation/promote.py \
        science/tests/
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

Read the whole test and its comment before changing anything — the comment states the reasoning this task preserves, not discards.

- [ ] **Step 2: Replace it with a behavioral guard**

```python
def test_neither_entity_writer_can_degrade_a_hypothesis(tmp_path: Path, monkeypatch):
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
    import science_tool.entities as entities
    from science_tool.entities import (
        EntityDegradationError,
        render_entity_frontmatter_updates,
        render_entity_source_refs,
    )

    valid_hypothesis = (
        "---\n"
        "id: hypothesis:0001-a-hypothesis\n"
        "kind: hypothesis\n"
        "title: a hypothesis\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "---\n"
        "body\n"
    )
    path = tmp_path / "entities" / "hypotheses" / "0001-a-hypothesis.md"

    # `title` is required with minLength 1, so emptying it is a genuine valid -> invalid.
    with pytest.raises(EntityDegradationError):
        render_entity_frontmatter_updates(
            valid_hypothesis, {"title": ""}, entity_path=path, as_of=date(2026, 6, 16)
        )

    # The source-refs renderer touches only unconstrained fields, so its guard is reached by
    # injecting corruption at the seam both renderers share.
    real_render_markdown = entities._render_markdown
    monkeypatch.setattr(
        entities,
        "_render_markdown",
        lambda frontmatter, body: real_render_markdown({**frontmatter, "title": ""}, body),
    )
    with pytest.raises(EntityDegradationError):
        render_entity_source_refs(
            valid_hypothesis, ["paper:new"], entity_path=path, as_of=date(2026, 6, 16)
        )
```

Delete the old `test_the_OTHER_entity_writer_still_cannot_reach_a_hypothesis` and its now-false comment. Add module-level imports for `pytest`, `date` and `Path` if the module lacks them.

- [ ] **Step 3: Run it**

```bash
cd science && uv run --frozen pytest tests/test_hypothesis_consumers.py
```

Expected: all pass.

- [ ] **Step 4: Certify by mutation**

Add `return` as the first statement of `_refuse_degradation` in `entities.py`, then run:

```bash
cd science && uv run --frozen pytest tests/test_hypothesis_consumers.py::test_neither_entity_writer_can_degrade_a_hypothesis
```

Expected: FAIL with `DID NOT RAISE`, twice over. Revert with `git checkout -- science/src/science_tool/entities.py` and confirm it passes.

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_hypothesis_consumers.py
git commit -m "test(hypothesis): replace the roster guard with a behavioral one"
```

**Slice 1 is complete at this commit.** Both staged workflows are contained and aggregate; the three immediate-write workflows translate their refusals but still write as they go.

---

# Slice 2 — preflight

### Task 6: Creates, drift, and one publish primitive

`PlannedFileEdit` models an update: `plan_update` calls `current_text(path)` unconditionally, so it cannot represent an absent pre-image, and both existing apply loops publish with bare `atomic_write_text` — a temp file plus `os.replace`, which overwrites whatever is there. `before_sha256` is stored and, today, **never read anywhere**.

This task builds the publish primitive **and immediately routes both existing staged workflows through it**. Adding the primitive without repointing them would leave `before_sha256` unread and the drift protection inert for the two workflows that already plan (§4.3: "This applies to **every** planned update — entity files, the promotion sidecar, and each decomposition index").

**Files:**
- Modify: `science/src/science_tool/annotation/planned_edits.py`
- Modify: `science/src/science_tool/dag/entity_frontmatter.py:352-388` (extract `publish_new_file`)
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_apply.py:804-816`
- Modify: `science/src/science_tool/annotation/proposition_resynthesis_apply.py:501-511,675-688`
- Test: `science/tests/test_planned_edits.py`, `science/tests/test_proposition_reconciliation_apply.py`

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
def plan_create_or_update(path: Path, final_text: str, reason: str) -> PlannedFileEdit: ...
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

- Also produces `publish_new_file(dest: Path, text: str) -> None` in `science_tool.dag.entity_frontmatter`, extracted from `create_entity_file` so the exclusive-create publish can be used without re-rendering.
- And `publish_order(edits: Iterable[PlannedFileEdit]) -> list[PlannedFileEdit]`, which sorts **entity edits before side-store edits** (sidecar, decomposition index), each group by path. Ordering is not cosmetic: prose promotion's recovery contract depends on the entity landing before the index, so a write-stage failure strands a recoverable entity rather than an index pointing at nothing. Resynthesis already encodes the same idea in `_ordered_file_edits`'s `phase_by_reason` map. A path-sorted publish would make that contract depend on where the store happens to put `index.json`.

```python
_SIDE_STORE_REASONS = frozenset({"promotion_sidecar", "prose_decomposition_index"})


def publish_order(edits: Iterable[PlannedFileEdit]) -> list[PlannedFileEdit]:
    """Entity edits first, side stores last; within each group, by path.

    A write-stage failure can strand a partially applied batch (§4.2 claims no rollback), so
    WHICH half lands first is a real contract. Entity first means the next run sees the
    entity and can recover the index from it; index first means an index row pointing at a
    record that was never written.
    """
    return sorted(
        edits, key=lambda e: (e.reason in _SIDE_STORE_REASONS, e.path.as_posix())
    )
```
- `plan_create_or_update` replaces resynthesis's `_new_or_existing_edit`: it dispatches on `path.exists()` at plan time, so a resume snapshot or replacement proposition that does not yet exist becomes a create and one that does becomes a drift-checked update.

- [ ] **Step 1: Write the failing drift tests**

Add to `science/tests/test_planned_edits.py`:

```python
from science_tool.annotation.planned_edits import (
    PlannedEditDriftError,
    plan_create,
    plan_create_or_update,
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


def test_plan_create_or_update_dispatches_on_existence(tmp_path: Path):
    absent = tmp_path / "absent.md"
    present = tmp_path / "present.md"
    present.write_text("before\n", encoding="utf-8")

    assert plan_create_or_update(absent, "x\n", "r").operation == "create"
    assert plan_create_or_update(present, "x\n", "r").operation == "update"
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

`create_entity_file`'s body becomes:

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

Add the imports:

```python
from collections.abc import Mapping, Sequence
from typing import Literal

from science_model.frontmatter import atomic_write_text

from science_tool.dag.entity_frontmatter import publish_new_file
from science_tool.entities import EntityCommandError
from science_tool.entity_reservation import claim_number_in_dir
```

(No cycle: `entities.py` imports nothing from `annotation/`, and `entity_frontmatter.py` imports only `render_entity_text` from `entities`.)

Add the error class:

```python
class PlannedEditDriftError(EntityCommandError):
    """A planned update's target changed on disk after planning; the batch refused.

    Subclasses `EntityCommandError` so a workflow's existing wrap set covers it, but it is
    named in each publish table so the inventory of what the write stage can raise stays
    complete rather than relying on inheritance to be noticed.
    """
```

Extend the dataclass with the four new fields from **Interfaces** above, then add the constructors, the publisher, and the shared edit-construction rule:

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


def plan_create_or_update(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    """Dispatch on existence at PLAN time.

    Resynthesis plans resume snapshots and replacement propositions that may or may not
    exist yet. Under one publish primitive that distinction has to be decided somewhere,
    and plan time is where the pre-image is read anyway.
    """
    return (
        plan_update(path, final_text, reason)
        if path.exists()
        else plan_create(path, final_text, reason)
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

    | publish        | raises                              |
    |----------------|-------------------------------------|
    | update         | PlannedEditDriftError, OSError      |
    | create         | EntityWriteError, OSError           |
    | numeric create | EntityCommandError (drift), OSError |

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

`plan_update` keeps its existing body — it already sets `before_sha256` and defaults `operation` to `"update"`.

- [ ] **Step 5: Run the primitive's tests**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py
```

Expected: all pass.

- [ ] **Step 6: Write the failing staged-workflow drift test**

Add to `science/tests/test_proposition_reconciliation_apply.py`. Model the setup on the module's existing apply tests (`_manifest`, `_proposition`, `_manual_ready_plan`).

```python
def test_canonicalization_refuses_a_drifted_entity_without_clobbering_it(tmp_path: Path, monkeypatch) -> None:
    """The drift precondition applies to EVERY planned update, including the two workflows
    that already planned before this branch existed. Before this task, before_sha256 was
    stored and read by nothing."""
    import science_tool.annotation.proposition_reconciliation_apply as recon

    _manifest(tmp_path)
    _proposition(tmp_path, "a", "Claim a")
    _proposition(tmp_path, "b", "Claim b")
    plan = _manual_ready_plan(
        actions=(_action(canonical="proposition:a", members=("proposition:a", "proposition:b")),)
    )
    duplicate = tmp_path / "entities" / "propositions" / "b.md"

    real_publish = recon.publish_edit
    drifted = {"done": False}

    def drift_then_publish(edit, *, project_root):
        if not drifted["done"]:
            drifted["done"] = True
            duplicate.write_text("someone else got here first\n", encoding="utf-8")
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(recon, "publish_edit", drift_then_publish)

    with pytest.raises(ReconciliationApplyError) as excinfo:
        recon.apply_canonicalization_plan(tmp_path, plan)

    assert "stage=write" in str(excinfo.value)
    assert duplicate.read_text(encoding="utf-8") == "someone else got here first\n"
```

- [ ] **Step 7: Route both staged workflows through `publish_edit`**

In `proposition_reconciliation_apply.py`, `apply_canonicalization_plan` (`:804-816`):

```python
        try:
            publish_edit(edit, project_root=project_root)
        except (OSError, EntityCommandError, EntityWriteError) as exc:
            written_paths = tuple(written)
            raise ReconciliationApplyError(
                "[stage=write, "
                f"files_written={len(written_paths)}, "
                f"written_paths={written_paths}] "
                f"failed to write {path_string(edit.path)}: {exc}"
            ) from exc
```

In `proposition_resynthesis_apply.py`, `apply_resynthesis_draft` (`:675-688`), the same substitution — and drop the now-redundant `edit.path.parent.mkdir(...)`, since `publish_new_file` creates the parent for a create and an update's parent necessarily exists:

```python
        try:
            publish_edit(edit, project_root=root)
        except (OSError, EntityCommandError, EntityWriteError) as exc:
            written_paths = tuple(written)
            raise ResynthesisApplyError(
                "[stage=write, "
                f"files_written={len(written_paths)}, "
                f"written_paths={written_paths}] "
                f"failed to write {path_string(edit.path)}: {exc}"
            ) from exc
```

Delete resynthesis's `_new_or_existing_edit` (`:501-511`) and replace its two call sites (`:539`, `:547`) with `plan_create_or_update`. Add to both modules:

```python
from science_tool.annotation.planned_edits import publish_edit  # plus plan_create_or_update in resynthesis
from science_tool.dag.entity_frontmatter import EntityWriteError
from science_tool.entities import EntityCommandError
```

The wrap set is `(OSError, EntityCommandError, EntityWriteError)`. These are **sibling** `ValueError` subclasses — `EntityCommandError` (`entities.py:47`), `EntityWriteError` (`dag/entity_frontmatter.py:314`) — so catching one catches neither of the others, and `PlannedEditDriftError` is covered by inheriting from the first.

- [ ] **Step 8: Run the tests**

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py tests/test_entity_writer.py tests/test_proposition_reconciliation_apply.py tests/test_proposition_reconciliation_cli.py tests/test_proposition_reconciliation_plan.py tests/test_proposition_resynthesis_apply.py
```

Expected: all pass. `create_entity_file`'s extraction is behavior-preserving, so nothing that exercises it should change.

- [ ] **Step 9: Certify the drift guards by mutation**

Delete the hash comparison from `publish_edit` and re-run:

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py::test_update_refuses_when_the_target_drifted tests/test_proposition_reconciliation_apply.py::test_canonicalization_refuses_a_drifted_entity_without_clobbering_it
```

Expected: both FAIL — the other writer's bytes are gone. Revert. Then swap `publish_new_file` for `atomic_write_text` in the create branch and re-run:

```bash
cd science && uv run --frozen pytest tests/test_planned_edits.py::test_create_refuses_an_intervening_file_without_clobbering_it
```

Expected: FAIL on the surviving-content assertion. Revert.

- [ ] **Step 10: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

- [ ] **Step 11: Commit**

```bash
git add science/src/science_tool/annotation/planned_edits.py \
        science/src/science_tool/dag/entity_frontmatter.py \
        science/src/science_tool/annotation/proposition_reconciliation_apply.py \
        science/src/science_tool/annotation/proposition_resynthesis_apply.py \
        science/tests/
git commit -m "feat(annotation): publish every planned edit through one drift-refusing primitive"
```

---

### Task 7: Plan the prose decomposition index

`ProseDecompositionStore.record_promotion` is a read-modify-write of one JSON file per source slug, called four times across the two prose workflows. **Multiple rows in a batch share one index**, so its post-images must compose exactly as entity files do (§4.5). This task is purely additive — no caller changes — so it lands before the cutover and leaves the tree green.

**Files:**
- Modify: `science/src/science_tool/annotation/prose_decomposition.py:211-217,543-544`
- Test: `science/tests/test_prose_decomposition.py`

**Interfaces:**
- Produces:

```python
def canonical_json_text(payload: dict[str, Any]) -> str: ...   # renamed from _canonical_json_text


class ProseDecompositionStore:
    def plan_promotion(
        self, source_slug: str, fingerprint: str, promoted_to: str, *, state: dict | None = None
    ) -> dict: ...
```

- `_canonical_json_text` is **renamed**, not duplicated. It is already the byte-format authority that `_atomic_write_json` uses; a second `json.dumps` would be a second authority that can silently drift out of agreement, producing a spurious diff on every planned index write. Rename only the one in `prose_decomposition.py` — `prose_grounding.py` and `prose_health.py` have their own, unrelated.
- `record_promotion` keeps its signature and behavior, reimplemented on top of `plan_promotion` so one place knows the index's shape.

- [ ] **Step 1: Write the failing composition test**

Add to `science/tests/test_prose_decomposition.py`. This module's `_artifact(tmp_path)` helper (`:15`) already builds a **two-unit** payload under one source slug `example` — `u001` (candidate) and `s001` (skip) — and both get index rows, which is exactly the shared-index case. The module's idiom is `parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)` (`:65`), then `ProseDecompositionStore(tmp_path).persist(artifact)`.

```python
def _persisted(tmp_path: Path):
    """The module's own two-unit artifact, persisted, plus its store and fingerprints."""
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(artifact)
    return artifact, store, [unit.fingerprint for unit in artifact.units]


def test_plan_promotion_composes_across_rows_and_writes_nothing(tmp_path: Path):
    """Two prose rows sharing one source slug must produce ONE index carrying both
    promotions, not two writes where the second drops the first."""
    _artifact_obj, store, fingerprints = _persisted(tmp_path)
    first, second = fingerprints[0], fingerprints[1]
    before = store.index_path("example").read_text(encoding="utf-8")

    state = store.plan_promotion("example", first, "proposition:a")
    state = store.plan_promotion("example", second, "proposition:b", state=state)

    assert state["units"][first]["promoted_to"] == "proposition:a"
    assert state["units"][second]["promoted_to"] == "proposition:b"
    # Planning wrote nothing.
    assert store.index_path("example").read_text(encoding="utf-8") == before


def test_plan_promotion_rejects_an_unknown_fingerprint(tmp_path: Path):
    _artifact_obj, store, _fingerprints = _persisted(tmp_path)

    with pytest.raises(DecompositionError):
        store.plan_promotion("example", "sha256:nope", "proposition:a")


def test_canonical_json_text_is_what_record_promotion_writes(tmp_path: Path):
    """The planner's text must be byte-identical to the writer's, or a planned index write
    would produce a spurious diff. One authority, not two."""
    _artifact_obj, store, fingerprints = _persisted(tmp_path)

    planned = canonical_json_text(store.plan_promotion("example", fingerprints[0], "proposition:a"))
    store.record_promotion(
        source_slug="example", fingerprint=fingerprints[0], promoted_to="proposition:a"
    )

    assert store.index_path("example").read_text(encoding="utf-8") == planned
```

- [ ] **Step 2: Run them to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_prose_decomposition.py -k "plan_promotion or canonical_json_text"
```

Expected: FAIL — `AttributeError: 'ProseDecompositionStore' object has no attribute 'plan_promotion'`.

- [ ] **Step 3: Rename the serializer and add `plan_promotion`**

In `science/src/science_tool/annotation/prose_decomposition.py`, rename `_canonical_json_text` (`:543`) to `canonical_json_text` and update its two in-module uses (`:526`, `:531`). Then:

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
cd science && uv run --frozen pytest tests/test_prose_decomposition.py tests/test_annotate_prose_decomposition_cli.py tests/test_prose_promote.py tests/test_prose_promotion_batch.py
```

Expected: all pass.

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

### Task 8: The cutover — all three write-as-you-go workflows

This is one task because it must be one commit. `PromotionTarget.mint` has three callers — `apply_candidates`, `promote_prose_unit` and `apply_prose_promotion_plan` — and replacing it with `plan_mint` breaks all three at once. Converting one and committing would leave `MintFn` deleted while two callers still call `.mint`, i.e. a deliberately broken intermediate API in the history. All three convert together.

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py:258-460`
- Modify: `science/src/science_tool/annotation/prose_promote.py:148-260`
- Modify: `science/src/science_tool/annotation/prose_promotion_batch.py:77-152`
- Modify: `science/src/science_tool/entities.py` (delete `append_entity_source_ref`)
- Test: `science/tests/test_annotation_promote.py`, `test_promote_numeric_mint.py`, `test_prose_promote.py`, `test_prose_promotion_batch.py`, `test_entity_writer.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7.
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

- `MintOutcome` and `MintFn` are **deleted**. A writing `mint` no longer exists on the target, so an implementation cannot retain writes inside it.
- The two added inputs keep the target pure. `assigned_number` is the number the *outer* planner allocated in memory — a target calling `propose_number` itself would hand every candidate in the batch the same number, since `propose_number` is read-only and nothing has been written yet. `current_text` is the destination's **composed** post-image so far, or `None` when the destination does not exist; accrual is an update, so it must render from what previous edits in this batch already planned for that path.

**Which failures aggregate, and which may abort (§4.1):**
- **Collected**, then reported together: `EntityDegradationError`, slug-naming failures from `validate_slug`, LINK target-resolution failures, and the never-overwrite guard. Planning continues past each so the report is complete.
- **Aborted immediately**: a missing or malformed packaged template (`Renderer().sections(kind)` raises `EntityTemplateError` from `science_model.templates`), an unreadable sidecar, an unresolvable project root. These are properties of the environment or of a target *kind*, not of a candidate. This is a **precondition**, not "every later candidate would fail" — a malformed `question` template does not affect the `proposition` candidates in a mixed-kind batch. `EntityTemplateError` is deliberately **not** in the collected set.

- [ ] **Step 1: Write the failing promotion tests**

Add to `science/tests/test_annotation_promote.py`. Model the project setup on `test_apply_mints_proposition_and_backlinks` (`:209`) and `test_apply_links_to_existing_appends_both_refs_preserves_prose` (`:252`); the module has no shared project fixture, and building inline is its idiom.

```python
def _promotion_project(tmp_path, *, existing: dict[str, str] | None = None):
    """Entities dir, a paper with a sidecar, and any pre-existing propositions.

    `existing` maps slug -> title. Returns (project_root, sidecar_path).
    """
    from science_tool.annotation import io as anno_io

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    for slug, title in (existing or {}).items():
        (tmp_path / "entities" / "propositions" / f"{slug}.md").write_text(
            f'---\nid: proposition:{slug}\nkind: proposition\ntitle: {title}\n'
            f'status: draft\nsource_refs:\n  - "paper:other"\n'
            f'created: "2026-06-01"\nupdated: "2026-06-01"\n---\n'
            f"# {title}\n\n## Claim\n\nHand-authored prose.\n",
            encoding="utf-8",
        )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Body.\n", encoding="utf-8")
    return tmp_path, anno_io.sidecar_for_markdown(md)


def _link_candidate(slug, frag, ref=None):
    from science_tool.annotation.promote import PromotionCandidate

    return PromotionCandidate(
        ref=ref or f"annotation:papers/p.source#{frag}", frag=frag, claim="Some claim",
        subject="s", object="o", decision="LINK", slug=slug, reason="existing entity",
        kind=slug.split(":", 1)[0],
    )


def _mint_candidate(kind, slug, frag, claim="Some claim"):
    from science_tool.annotation.promote import PromotionCandidate

    return PromotionCandidate(
        ref=f"annotation:papers/p.source#{frag}", frag=frag, claim=claim,
        subject="s", object="o", decision="MINT", slug=slug, reason="new entity", kind=kind,
    )


def _refusing_source_refs_renderer(*_a, entity_path, **_k):
    from science_tool.entities import EntityDegradationError

    raise EntityDegradationError(f"{entity_path} would be degraded")


def test_apply_candidates_aggregates_every_candidate_local_refusal(tmp_path, monkeypatch):
    """One refusal does not prove aggregation; it is equally consistent with abort-on-first.
    Two refused records plus one that would have succeeded is the shape that does."""
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import PromotionApplyError, apply_candidates

    root, sp = _promotion_project(
        tmp_path, existing={"bad-a": "Bad a", "bad-b": "Bad b", "good": "Good"}
    )
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))
    good = root / "entities" / "propositions" / "good.md"
    good_before = good.read_text(encoding="utf-8")

    # Refuse ONLY the two bad records. A blanket refusal would make the "good" candidate a
    # third refusal rather than the edit that would have succeeded, and the final assertion
    # would then prove nothing about all-or-nothing.
    real_renderer = promote_mod.render_entity_source_refs

    def refuse_the_bad_ones(current_text, refs, *, entity_path, as_of=None):
        if entity_path.name in ("bad-a.md", "bad-b.md"):
            return _refusing_source_refs_renderer(entity_path=entity_path)
        return real_renderer(current_text, refs, entity_path=entity_path, as_of=as_of)

    monkeypatch.setattr(promote_mod, "render_entity_source_refs", refuse_the_bad_ones)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [
                _link_candidate("proposition:bad-a", "a-1"),
                _link_candidate("proposition:bad-b", "a-2"),
                _link_candidate("proposition:good", "a-3"),
            ],
            sidecar_path=sp, project_root=root, paper_ref="paper:p",
        )

    message = str(excinfo.value)
    assert "bad-a" in message
    assert "bad-b" in message
    # Nothing was written -- not even the edit that would have succeeded.
    assert good.read_text(encoding="utf-8") == good_before


def test_apply_candidates_aggregates_across_kinds_of_failure(tmp_path, monkeypatch):
    """The report spans the whole candidate-local set, not degradation alone: a degradation,
    a slug-naming failure, and an unresolvable LINK target in one batch."""
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import PromotionApplyError, apply_candidates

    root, sp = _promotion_project(tmp_path, existing={"bad": "Bad"})
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))

    real_renderer = promote_mod.render_entity_source_refs

    def refuse_only_bad(current_text, refs, *, entity_path, as_of=None):
        if entity_path.name == "bad.md":
            return _refusing_source_refs_renderer(entity_path=entity_path)
        return real_renderer(current_text, refs, entity_path=entity_path, as_of=as_of)

    monkeypatch.setattr(promote_mod, "render_entity_source_refs", refuse_only_bad)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [
                _link_candidate("proposition:bad", "a-1"),
                # `reserve_entity` called validate_slug; the planner must keep doing so.
                _mint_candidate("question", "Not A Slug!", "a-2"),
                _link_candidate("proposition:missing", "a-3"),
            ],
            sidecar_path=sp, project_root=root, paper_ref="paper:p",
        )

    message = str(excinfo.value)
    assert "bad" in message
    assert "Not A Slug!" in message
    assert "missing" in message


def test_two_links_to_one_record_compose(tmp_path):
    """Two annotations can LINK to the same existing record. Independent edits from the same
    disk pre-image would lose the first."""
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import apply_candidates

    root, sp = _promotion_project(tmp_path, existing={"shared": "Shared"})
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))
    dest = root / "entities" / "propositions" / "shared.md"

    apply_candidates(
        [
            _link_candidate("proposition:shared", "a-1", ref="annotation:papers/p.source#a-1"),
            _link_candidate("proposition:shared", "a-2", ref="annotation:papers/p.source#a-2"),
        ],
        sidecar_path=sp, project_root=root, paper_ref="paper:p",
    )

    written = dest.read_text(encoding="utf-8")
    assert "annotation:papers/p.source#a-1" in written
    assert "annotation:papers/p.source#a-2" in written


def test_a_refused_batch_leaves_the_sidecar_unchanged(tmp_path, monkeypatch):
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import PromotionApplyError, apply_candidates

    root, sp = _promotion_project(tmp_path, existing={"bad": "Bad"})
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))
    sidecar_before = sp.read_text(encoding="utf-8")

    monkeypatch.setattr(promote_mod, "render_entity_source_refs", _refusing_source_refs_renderer)

    with pytest.raises(PromotionApplyError):
        apply_candidates([_link_candidate("proposition:bad", "a-1")],
                         sidecar_path=sp, project_root=root, paper_ref="paper:p")

    assert sp.read_text(encoding="utf-8") == sidecar_before


def test_sidecar_drift_between_planning_and_apply_refuses(tmp_path, monkeypatch):
    """The drift precondition applies to EVERY planned update, not only entity records. A
    sidecar clobbered by a concurrent writer loses exactly as much as a record does, and it
    is the one planned update that does not look like one."""
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import PromotionApplyError, apply_candidates

    root, sp = _promotion_project(tmp_path, existing={"known-claim": "Known claim"})
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(
        _statement_ann("a-1", "Known claim", status=Status.OPEN),
    )))

    real_publish = promote_mod.publish_edit

    def drift_the_sidecar_first(edit, *, project_root):
        if edit.path == sp:
            sp.write_text("{}\n", encoding="utf-8")
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(promote_mod, "publish_edit", drift_the_sidecar_first)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates([_link_candidate("proposition:known-claim", "a-1")],
                         sidecar_path=sp, project_root=root, paper_ref="paper:p")

    assert "stage=write" in str(excinfo.value)
    assert sp.read_text(encoding="utf-8") == "{}\n"   # the other writer's bytes survive
```

- [ ] **Step 2: Write the failing numeric-mint tests**

In `science/tests/test_promote_numeric_mint.py`, the module-level `_mint` helper (`:13`) calls `target.mint(...)` and asserts `outcome.created`. Replace it with a plan-then-publish helper, and delete `test_mint_rollback_unlinks_placeholder_on_write_failure` (`:63`) — planning reserves nothing, so there is no placeholder to roll back and nothing that test asserts still exists. The property it protected (a failed write leaves no orphan) is now covered by `test_a_refused_batch_consumes_no_number`.

```python
def _mint(kind, claim, project_root, slug="claim-slug"):
    """Plan one numeric mint and publish it, so the existing template-faithfulness tests
    keep asserting the same thing about the same rendered text."""
    from science_tool.annotation.planned_edits import plan_numeric_create, publish_edit
    from science_tool.entity_reservation import propose_number

    c = PromotionCandidate(
        ref="annotation:papers/p#f1", frag="f1", claim=claim, subject="s", object="o",
        decision="MINT", slug=slug, reason="new entity", kind=kind,
    )
    number = propose_number(project_root, kind)
    planned = numeric_target(kind).plan_mint(
        c, ["paper:p", c.ref], project_root, date(2026, 6, 16), number, None
    )
    assert planned.operation == "create"   # numeric kinds claim a number; they never accrue
    kind_prefix, local_part = planned.entity_id.split(":", 1)
    publish_edit(
        plan_numeric_create(
            planned.path, planned.post_image, "test",
            kind=kind_prefix, local_part=local_part, number=planned.claim_number,
        ),
        project_root=project_root,
    )
    return planned.entity_id


def test_planning_a_mint_writes_nothing_and_consumes_no_number(tmp_path):
    """This is what fails if an implementation keeps writes inside mint."""
    from science_tool.annotation.promote import PromotionCandidate, build_targets
    from science_tool.entity_reservation import propose_number

    (tmp_path / "entities" / "questions").mkdir(parents=True)
    before_number = propose_number(tmp_path, "question")

    c = PromotionCandidate(
        ref="annotation:papers/p#f1", frag="f1", claim="What drives growth?", subject="s",
        object="o", decision="MINT", slug="what-drives-growth", reason="new entity",
        kind="question",
    )
    planned = build_targets()["question"].plan_mint(
        c, ["paper:p", c.ref], tmp_path, date(2026, 6, 16), before_number, None
    )

    assert planned.claim_number == before_number
    assert not any((tmp_path / "entities" / "questions").glob("*.md"))
    assert propose_number(tmp_path, "question") == before_number


def test_plan_mint_rejects_a_malformed_slug(tmp_path):
    """`reserve_entity` called `validate_slug`; the pure planner must keep doing so, or the
    batch would aggregate a naming failure it never detects."""
    from science_tool.annotation.promote import PromotionCandidate, numeric_target
    from science_tool.entities import EntityCommandError

    c = PromotionCandidate(
        ref="annotation:papers/p#f1", frag="f1", claim="Q?", subject="s", object="o",
        decision="MINT", slug="Not A Slug!", reason="new entity", kind="question",
    )

    with pytest.raises(EntityCommandError):
        numeric_target("question").plan_mint(c, ["paper:p"], tmp_path, None, 1, None)


def test_a_refused_batch_consumes_no_number(tmp_path, monkeypatch):
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import apply_candidates
    from science_tool.entities import EntityDegradationError
    from science_tool.entity_reservation import propose_number

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "propositions" / "bad.md").write_text(
        '---\nid: proposition:bad\nkind: proposition\ntitle: Bad\nstatus: draft\n'
        'source_refs: []\ncreated: "2026-06-01"\nupdated: "2026-06-01"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Body.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))
    before = propose_number(tmp_path, "question")

    def refuse(*_a, entity_path, **_k):
        raise EntityDegradationError(f"{entity_path} would be degraded")

    monkeypatch.setattr(promote_mod, "render_entity_source_refs", refuse)

    with pytest.raises(PromotionApplyError):
        apply_candidates(
            [
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-1", frag="a-1", claim="Q?", subject="s",
                    object="o", decision="MINT", slug="a-question", reason="new", kind="question",
                ),
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-2", frag="a-2", claim="Bad", subject="s",
                    object="o", decision="LINK", slug="proposition:bad", reason="existing",
                    kind="proposition",
                ),
            ],
            sidecar_path=sp, project_root=tmp_path, paper_ref="paper:p",
        )

    assert propose_number(tmp_path, "question") == before
    assert not any((tmp_path / "entities" / "questions").glob("*.md"))


def test_a_write_stage_failure_reports_what_was_already_written(tmp_path, monkeypatch):
    """A claim_number_in_dir drift failure raised AFTER an earlier file has been written must
    carry files_written and written_paths. An OSError-only wrapper passes the plain
    atomic_write_text test and fails this one, which is the point: EntityCommandError,
    EntityWriteError and DecompositionError are SIBLING ValueError subclasses, so catching
    one catches neither of the others."""
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import PromotionApplyError, PromotionCandidate, apply_candidates
    from science_tool.entity_reservation import LOCAL_PART_WIDTH, claim_number_in_dir

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "propositions" / "existing.md").write_text(
        '---\nid: proposition:existing\nkind: proposition\ntitle: Existing\nstatus: draft\n'
        'source_refs: []\ncreated: "2026-06-01"\nupdated: "2026-06-01"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Body.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))

    real_publish = promote_mod.publish_edit

    def steal_the_number(edit, *, project_root):
        if edit.claim_number is not None:
            claim_number_in_dir(
                project_root, "question", edit.claim_number,
                f"{edit.claim_number:0{LOCAL_PART_WIDTH}d}-other", "---\nid: question:x\n---\n",
            )
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(promote_mod, "publish_edit", steal_the_number)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-1", frag="a-1", claim="Existing",
                    subject="s", object="o", decision="LINK", slug="proposition:existing",
                    reason="existing", kind="proposition",
                ),
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-2", frag="a-2", claim="Q?", subject="s",
                    object="o", decision="MINT", slug="a-question", reason="new", kind="question",
                ),
            ],
            sidecar_path=sp, project_root=tmp_path, paper_ref="paper:p",
        )

    message = str(excinfo.value)
    assert "stage=write" in message
    assert "files_written=1" in message
    assert "existing.md" in message


def test_a_malformed_kind_template_aborts_before_any_write(tmp_path, monkeypatch):
    """The §4.1 boundary's other half. A missing or malformed packaged template is a property
    of the ENVIRONMENT or of a target KIND, not of a candidate, and no candidate-level fix
    exists -- so it aborts rather than aggregating. This is a PRECONDITION, not a claim that
    every later candidate would fail: a malformed `question` template does not affect the
    `proposition` candidates in a mixed-kind batch.

    Without this test, "may abort immediately" is untested and an implementer could
    legitimately aggregate everything."""
    from science_model.templates import EntityTemplateError, Renderer

    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import PromotionCandidate, apply_candidates

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    existing = tmp_path / "entities" / "propositions" / "existing.md"
    existing.write_text(
        '---\nid: proposition:existing\nkind: proposition\ntitle: Existing\nstatus: draft\n'
        'source_refs: []\ncreated: "2026-06-01"\nupdated: "2026-06-01"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    existing_before = existing.read_text(encoding="utf-8")
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Body.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))

    def malformed_sections(self, kind):
        raise EntityTemplateError(f"packaged template for {kind} is malformed")

    monkeypatch.setattr(Renderer, "sections", malformed_sections)

    with pytest.raises(EntityTemplateError):
        apply_candidates(
            [
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-1", frag="a-1", claim="Existing",
                    subject="s", object="o", decision="LINK", slug="proposition:existing",
                    reason="existing", kind="proposition",
                ),
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-2", frag="a-2", claim="Q?", subject="s",
                    object="o", decision="MINT", slug="a-question", reason="new", kind="question",
                ),
            ],
            sidecar_path=sp, project_root=tmp_path, paper_ref="paper:p",
        )

    # ONE error, not an aggregated report -- and nothing was written, including the
    # proposition LINK that would have succeeded.
    assert existing.read_text(encoding="utf-8") == existing_before
```

- [ ] **Step 3: Write the failing prose tests**

Add to `science/tests/test_prose_promotion_batch.py`. This module already has `_persist_duplicate_question_artifact(tmp_path)` (`:148`), which persists two candidate units (`u001`, `u002`) under the one source slug `example` — exactly the shared-index case, and `question` because `test_plan_allows_duplicate_numeric_mint_titles` (`:364`) establishes duplicate numeric titles are allowed.

```python
def test_two_rows_sharing_a_source_slug_produce_one_index_write(tmp_path: Path) -> None:
    """The index is a read-modify-write of ONE file per source slug. Two independent writes
    from the same pre-image would drop the first row's promotion."""
    artifact = _persist_duplicate_question_artifact(tmp_path)
    plan = plan_prose_promotions(tmp_path, "example", ["u001", "u002"])

    report = apply_prose_promotion_plan(tmp_path, plan)

    assert report.minted == 2
    index = ProseDecompositionStore(tmp_path).load_index("example")
    promoted = {index["units"][unit.fingerprint].get("promoted_to") for unit in artifact.units}
    assert None not in promoted
    assert len(promoted) == 2


def test_a_refused_row_leaves_the_index_and_every_entity_unchanged(tmp_path: Path, monkeypatch) -> None:
    import science_tool.annotation.prose_promotion_batch as batch
    from science_tool.entities import EntityDegradationError

    _persist_duplicate_claim_artifact(tmp_path)
    _write_existing_proposition(tmp_path)
    plan = plan_prose_promotions(tmp_path, "example", ["u001"])
    store = ProseDecompositionStore(tmp_path)
    index_before = store.index_path("example").read_text(encoding="utf-8")
    entities_before = {
        path: path.read_text(encoding="utf-8")
        for path in (tmp_path / "entities").rglob("*.md")
    }

    def refuse(*_a, entity_path, **_k):
        raise EntityDegradationError(f"{entity_path} would be degraded")

    monkeypatch.setattr(batch, "render_entity_source_refs", refuse)

    with pytest.raises(ProsePromotionError):
        apply_prose_promotion_plan(tmp_path, plan)

    assert store.index_path("example").read_text(encoding="utf-8") == index_before
    for path, text in entities_before.items():
        assert path.read_text(encoding="utf-8") == text


def test_index_drift_between_planning_and_apply_refuses(tmp_path: Path, monkeypatch) -> None:
    """The third planned update. All three -- entity record, sidecar, decomposition index --
    go through the same precondition; only the first is obviously an update."""
    import science_tool.annotation.prose_promotion_batch as batch

    _persist_duplicate_question_artifact(tmp_path)
    plan = plan_prose_promotions(tmp_path, "example", ["u001", "u002"])
    index_path = ProseDecompositionStore(tmp_path).index_path("example")

    real_publish = batch.publish_edit

    def drift_the_index_first(edit, *, project_root):
        if edit.path == index_path:
            index_path.write_text('{"units": {}}\n', encoding="utf-8")
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(batch, "publish_edit", drift_the_index_first)

    with pytest.raises(ProsePromotionError) as excinfo:
        apply_prose_promotion_plan(tmp_path, plan)

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

- [ ] **Step 4: Run everything to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_annotation_promote.py tests/test_promote_numeric_mint.py tests/test_prose_promotion_batch.py tests/test_entity_writer.py
```

Expected: many failures — `AttributeError: 'PromotionTarget' object has no attribute 'plan_mint'` and `publish_edit` not present on the workflow modules.

- [ ] **Step 5: Replace `MintOutcome`/`MintFn` with `PlannedMint`/`PlanMintFn`**

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

- [ ] **Step 6: Convert `_mint_proposition` to a planner**

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
    prop_ref = f"proposition:{validate_slug(c.slug)}"
    dest = entity_dest(prop_ref, project_root)

    if current_text is not None:
        # Never-overwrite guard: a MINT slug colliding with a DIFFERENT-claim proposition
        # (only reachable via an explicit-id override; auto mints are pre-screened) fails loud.
        existing_fm, _body = split_frontmatter(current_text)
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
        prop, ownership=PROMOTE_PROPOSITION, body=_proposition_body(c.claim),
        created=today, updated=today,
    )
    return PlannedMint(
        entity_id=prop_ref, operation="create", path=dest,
        post_image=post_image, claim_number=None,
    )


def proposition_target() -> PromotionTarget:
    return PromotionTarget(kind="proposition", slug_addressed=True, plan_mint=_plan_proposition_mint)
```

Import `render_create` from `science_tool.dag.entity_frontmatter`, `split_frontmatter` from `science_model.frontmatter`, and `validate_slug` from `science_tool.entities`. `render_create` calls `certify_persisted` itself, so the create's certification now runs at **plan** time — which is the point.

- [ ] **Step 7: Convert `_mint_numeric` to a planner**

First confirm the local-part format `reserve_number_in_dir` produces, so `claim_number_in_dir` lands the entity at the path the plan named:

```bash
cd science && grep -n "LOCAL_PART_WIDTH\|local_part" src/science_tool/entity_reservation.py | head -20
```

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
        # `reserve_entity` validated the slug before claiming a number; the pure planner keeps
        # doing so, or the batch would aggregate a naming failure it never detects.
        slug = validate_slug(c.slug)
        today = (as_of or date.today()).isoformat()
        # Preflight the template (pure read, no number consumed). Raises EntityTemplateError
        # if the packaged template is missing/malformed -- an environment/target-kind
        # PRECONDITION, so the caller aborts rather than aggregating (design §4.1).
        renderer = Renderer()
        renderer.sections(kind)
        local_part = f"{assigned_number:0{LOCAL_PART_WIDTH}d}-{slug}"
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
            entity_id=entity_id, operation="create",
            path=entity_dest(entity_id, project_root),
            post_image=rendered, claim_number=assigned_number,
        )

    return plan


def numeric_target(kind: str) -> PromotionTarget:
    if kind not in ("question", "hypothesis"):
        raise ValueError(f"numeric_target supports question/hypothesis, got {kind!r}")
    return PromotionTarget(kind=kind, slug_addressed=False, plan_mint=_plan_numeric_mint(kind))
```

Import `LOCAL_PART_WIDTH` from `science_tool.entity_reservation`. The `reserve_entity` call, the placeholder `.md`, and the explicit post-reservation rollback are all **gone** — there is no reservation to roll back, because planning consumes nothing.

- [ ] **Step 8: Rewrite `apply_candidates`**

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
    # create. A path absent from this map is an update.
    creates: dict[Path, tuple[str, str, int] | None] = {}
    # One propose_number per KIND, then allocate in memory: propose_number is read-only, so
    # repeated calls before writing return the same number and every candidate in the batch
    # would otherwise be handed the same one.
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
                dest: Path | None = None
                if target.slug_addressed:
                    dest = entity_dest(f"{c.kind}:{c.slug}", project_root)
                else:
                    if c.kind not in next_number:
                        next_number[c.kind] = propose_number(project_root, c.kind)
                    assigned = next_number[c.kind]
                    next_number[c.kind] += 1
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
                # Accrue BOTH provenance refs; the renderer dedups, preserves the (possibly
                # hand-authored) prose body, and advances `updated` when it appends.
                post_image, _changed = render_entity_source_refs(
                    before, [paper_ref, c.ref], entity_path=dest, as_of=as_of
                )
                planned_text_by_path[dest] = post_image
                report.linked += 1
                backlinks[c.frag] = c.slug
        except (EntityCommandError, PromotionApplyError) as exc:
            # Candidate-local and deterministic: collect and keep planning, so an operator
            # who fixes one refusal is not ambushed by the next. EntityTemplateError is NOT
            # caught here -- it is a target-kind precondition and aborts (design §4.1).
            refusals.append(f"{c.ref} ({c.slug}): {exc}")

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
        edits[sidecar_path] = plan_update(
            sidecar_path,
            serialize_sidecar(dataclasses.replace(sidecar, annotations=new_anns)),
            "promotion_sidecar",
        )

    written: list[str] = []
    for edit in publish_order(edits.values()):
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

The wrap set is `(OSError, EntityCommandError, EntityWriteError)` — sibling `ValueError` subclasses, so catching one catches neither of the others. An `EntityCommandError`-only wrapper would let the create publish's own refusal escape naked, which is the one failure preflight was added to make legible. `PlannedEditDriftError` is covered by inheritance.

Add these imports and drop `append_entity_source_ref`, `create_entity_file`, `reserve_entity`, `_atomic_replace_text` and `anno_io` if nothing else in the module uses them:

```python
from science_tool.annotation.io import serialize_sidecar
from science_tool.annotation.planned_edits import (
    current_text,
    edits_for_planned_texts,
    path_string,
    plan_update,
    publish_edit,
    publish_order,
)
from science_tool.dag.entity_frontmatter import EntityWriteError, render_create
from science_tool.entities import EntityCommandError, render_entity_source_refs, validate_slug
from science_tool.entity_reservation import LOCAL_PART_WIDTH, propose_number
```

The Task 4 `except EntityDegradationError` translation is **replaced** by the aggregation above — delete it and its import.

- [ ] **Step 9: Convert `apply_prose_promotion_plan`**

In `science/src/science_tool/annotation/prose_promotion_batch.py`, replace `apply_prose_promotion_plan` and `_apply_validated_row`:

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
        try:
            promoted_to = _plan_row(
                project_root, current, targets, composed,
                planned_text_by_path, creates, next_number, report,
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
            index_path, canonical_json_text(state), "prose_decomposition_index"
        )

    written: list[str] = []
    for edit in publish_order(edits.values()):
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


def _plan_row(
    project_root: Path,
    current: _ValidatedPromotionRow,
    targets: dict[str, PromotionTarget],
    composed: Callable[[Path], str | None],
    planned_text_by_path: dict[Path, str],
    creates: dict[Path, tuple[str, str, int] | None],
    next_number: dict[str, int],
    report: ApplyReport,
) -> str | None:
    """Plan one row's entity edit. Returns the `promoted_to` ref, or None for a SKIP.

    A recovered link produces no entity edit at all -- only the index update the caller
    derives from the returned ref.
    """
    row = current.row
    candidate = current.candidate
    if current.recovered_link:
        if candidate.slug is None:
            raise ProsePromotionError(f"recovered link for unit {row.unit_id!r} is missing target ref")
        return candidate.slug

    if candidate.decision == "MINT":
        target = targets[candidate.kind]
        assigned: int | None = None
        dest: Path | None = None
        if target.slug_addressed:
            dest = entity_dest(f"{candidate.kind}:{candidate.slug}", project_root)
        else:
            if candidate.kind not in next_number:
                next_number[candidate.kind] = propose_number(project_root, candidate.kind)
            assigned = next_number[candidate.kind]
            next_number[candidate.kind] += 1
        planned = target.plan_mint(
            candidate, [row.source_ref, row.artifact_unit_ref], project_root, None,
            assigned, composed(dest) if dest is not None else None,
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
        return planned.entity_id

    if candidate.decision == "LINK":
        if candidate.slug is None:
            raise ProsePromotionError(f"LINK decision for unit {row.unit_id!r} is missing target ref")
        dest = find_entity(project_root, candidate.slug).path
        before = composed(dest)
        if before is None:
            raise ProsePromotionError(f"LINK target {candidate.slug} does not exist at {dest}")
        # Two refs, ONE composed post-image -- the second render reads the first's output.
        post_image, _changed = render_entity_source_refs(
            before, [row.source_ref, row.artifact_unit_ref], entity_path=dest
        )
        planned_text_by_path[dest] = post_image
        report.linked += 1
        return candidate.slug

    report.skipped[candidate.reason] += 1
    return None
```

`DecompositionError` is **not** in the write-stage wrap set, and does not need to be: no `record_promotion` call survives into the write stage. If an implementation leaves one there, the wrap set is wrong — but the correct fix is to plan it, not to widen the tuple.

- [ ] **Step 10: Convert `promote_prose_unit`**

`promote_prose_unit` handles one unit, so it needs no aggregation — but it must still plan then write, so a refusal leaves nothing half-written. In `science/src/science_tool/annotation/prose_promote.py`:

Replace the recovery block (`:220-234`) so the index write is planned:

```python
    corpora, derived_refs = load_corpora(project_root)
    if apply and ref in derived_refs:
        recovered_to = _entity_ref_with_source_ref(project_root, ref, kind=unit.candidate.type)
        if recovered_to is None:
            raise ProsePromotionError(f"artifact unit ref {ref!r} is present in derived refs but no entity was found")
        try:
            state = store.plan_promotion(
                source_slug=source_slug, fingerprint=unit.fingerprint, promoted_to=recovered_to
            )
            recovery_report = ApplyReport()
            _publish(project_root, [
                plan_update(store.index_path(source_slug), canonical_json_text(state),
                            "prose_decomposition_index"),
            ], recovery_report)
        except DecompositionError as exc:
            raise ProsePromotionError(str(exc)) from exc
        return recovery_report
```

Replace the write section (`:220-260` in the original numbering, the `report = ApplyReport()` block onward) with plan-then-publish:

```python
    report = ApplyReport()
    planned_text_by_path: dict[Path, str] = {}
    creates: dict[Path, tuple[str, str, int] | None] = {}
    promoted_to: str | None = None
    try:
        if decision.decision == "MINT":
            target = targets[decision.kind]
            assigned = None if target.slug_addressed else propose_number(project_root, decision.kind)
            dest = (
                entity_dest(f"{decision.kind}:{decision.slug}", project_root)
                if target.slug_addressed
                else None
            )
            existing = (
                current_text(dest) if dest is not None and dest.exists() else None
            )
            planned = target.plan_mint(
                decision, [source_ref, decision.ref], project_root, None, assigned, existing
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
            promoted_to = planned.entity_id
        elif decision.decision == "LINK":
            if decision.slug is None:
                raise ProsePromotionError(f"LINK decision for unit {unit_id!r} is missing target ref")
            dest = find_entity(project_root, decision.slug).path
            post_image, _changed = render_entity_source_refs(
                current_text(dest), [source_ref, decision.ref], entity_path=dest
            )
            planned_text_by_path[dest] = post_image
            report.linked += 1
            promoted_to = decision.slug
        else:
            report.skipped[decision.reason] += 1

        edits = edits_for_planned_texts(
            planned_text_by_path, creates,
            reason_create="prose_promotion_mint", reason_update="prose_promotion_accrual",
        )
        if promoted_to is not None:
            state = store.plan_promotion(
                source_slug=source_slug, fingerprint=unit.fingerprint, promoted_to=promoted_to
            )
            index_path = store.index_path(source_slug)
            edits[index_path] = plan_update(
                index_path, canonical_json_text(state), "prose_decomposition_index"
            )
    except (DecompositionError, EntityCommandError, PromotionApplyError) as exc:
        raise ProsePromotionError(str(exc)) from exc

    _publish(project_root, publish_order(edits.values()), report)
    return report
```

and add the shared publisher at module level. It appends created paths to the report, which the current implementation does and a naive conversion drops — `promote_prose_unit` records a newly minted entity path in `ApplyReport.written_paths` today, exactly as both other converted workflows do:

```python
def _publish(project_root: Path, edits: Sequence[PlannedFileEdit], report: ApplyReport) -> None:
    written: list[str] = []
    for edit in edits:
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
```

Both call sites pass the report: `_publish(project_root, publish_order(edits.values()), report)`, and the recovery block's call passes the `ApplyReport()` it is about to return.

Add the assertion to `test_promote_prose_unit_mints_proposition_and_records_state` (`tests/test_prose_promote.py:95`), which does not currently check it:

```python
    assert report.written_paths == [str(dest)]
```

Both prose modules need these imports, replacing `append_entity_source_ref`:

```python
from science_tool.annotation.planned_edits import (
    PlannedFileEdit,
    current_text,
    edits_for_planned_texts,
    path_string,
    plan_update,
    publish_edit,
    publish_order,
)
from science_tool.annotation.prose_decomposition import canonical_json_text
from science_tool.dag.entity_frontmatter import EntityWriteError
from science_tool.entities import EntityCommandError, find_entity, render_entity_source_refs
from science_tool.entity_reservation import propose_number
```

- [ ] **Step 11: Adapt the three existing tests this conversion invalidates**

Three tests assert behavior the conversion deliberately changes. Each names what it was protecting and how the replacement preserves it — do not defer these to Step 12's general rule.

**(a) and (b) — the two recovery tests.** `test_promote_prose_unit_recovers_index_when_retry_sees_minted_ref` (`tests/test_prose_promote.py:135`) and `test_promote_prose_unit_recovers_index_when_retry_sees_linked_ref_without_duplicate_refs` (`:215`) both inject failure by monkeypatching `ProseDecompositionStore.record_promotion` to raise on its first call. The converted workflow never calls that method — it plans through `plan_promotion` and publishes — so `fail_once` is never invoked and both tests fail with `DID NOT RAISE`.

Their contract is still live and still worth protecting: **a write-stage failure may strand the entity edit, and the next run must recover the index without duplicating refs.** `publish_order` (see Task 6) is what makes that reachable — the entity edit publishes before the index. Inject the failure at the new seam instead. In both tests, replace the `original_record` / `fail_once` / `monkeypatch.setattr(ProseDecompositionStore, ...)` block with:

```python
    import science_tool.annotation.prose_promote as prose_promote_mod

    real_publish = prose_promote_mod.publish_edit
    index_path = ProseDecompositionStore(tmp_path).index_path("example")
    failed = {"done": False}

    def fail_the_index_once(edit, *, project_root):
        if edit.path == index_path and not failed["done"]:
            failed["done"] = True
            raise RuntimeError("simulated index write failure")
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(prose_promote_mod, "publish_edit", fail_the_index_once)
```

Then widen the raise expectation, because the workflow now wraps write-stage failures:

```python
    with pytest.raises((RuntimeError, ProsePromotionError)):
```

Every other assertion in both tests stands unchanged — the entity exists after the first run, the index has no `promoted_to`, the retry mints nothing, and the linked case's ref counts stay at 1. That those assertions survive verbatim is the evidence the contract was preserved rather than rewritten.

**(c) — the never-overwrite test.** `test_apply_refuses_overwrite_of_different_claim` (`tests/test_annotation_promote.py:297`) passes `sidecar_path=tmp_path / "x.anno.trig"`, which does not exist. That was harmless while the sidecar was read after the loop; preflight now calls `read_sidecar_strict` **first**, as an environment precondition, so the test would fail on the missing sidecar before ever reaching the guard it exists to test. Seed one:

```python
    from science_tool.annotation import io as anno_io

    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Body.\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sidecar_path, anno_io.Sidecar(annotations=()))
```

and pass `sidecar_path=sidecar_path`. The assertion — `PromotionApplyError` because the slug holds a different claim — is unchanged.

Finally, retarget the slice-1 translation test added in Task 4 Step 7. `test_promote_prose_unit_surfaces_a_degradation_refusal_as_its_own_error` patches `prose_promote_mod.append_entity_source_ref`, which no longer exists. Patch the renderer the converted workflow calls instead:

```python
    def refuse(current_text, refs, *, entity_path, as_of=None):
        raise EntityDegradationError(f"{entity_path} would be degraded")

    monkeypatch.setattr(prose_promote_mod, "render_entity_source_refs", refuse)
```

- [ ] **Step 12: Delete `append_entity_source_ref`**

Confirm it has no production callers left:

```bash
cd science && grep -rn "append_entity_source_ref" src/
```

Expected: no results. Delete the function from `science/src/science_tool/entities.py` and remove it from `tests/test_entity_writer.py`'s import list. Delete the two tests that exercised it directly, `test_append_entity_source_ref_preserves_body_and_updates_timestamp` (`:33`) and `test_append_entity_source_ref_noops_when_ref_exists` (`:58`) — the behavior they covered is now covered by `render_entity_source_refs`'s own tests plus the publish tests in `test_planned_edits.py`. Do not leave it as a compatibility shim.

- [ ] **Step 13: Run the whole affected surface**

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

Expected: all pass. Step 11 named the three tests this conversion knowingly invalidates. If any OTHER existing test fails, decide which of two things it was asserting before changing anything: the immediate-write behavior this design deliberately removes (update the test, and say so in the commit message), or a property that must survive (fix the code).

- [ ] **Step 14: Certify the new guards by mutation**

```bash
cd science
# 1. Aggregation: change `refusals.append(...)` in apply_candidates to `raise`.
uv run --frozen pytest tests/test_annotation_promote.py::test_apply_candidates_aggregates_every_candidate_local_refusal   # expect FAIL, only bad-a named
# 2. Wrap set: narrow apply_candidates' write-stage except to `(OSError,)`.
uv run --frozen pytest tests/test_promote_numeric_mint.py::test_a_write_stage_failure_reports_what_was_already_written    # expect FAIL, naked EntityCommandError
# 3. Slug validation: delete `validate_slug(c.slug)` from _plan_numeric_mint.
uv run --frozen pytest tests/test_promote_numeric_mint.py::test_plan_mint_rejects_a_malformed_slug                        # expect FAIL, DID NOT RAISE
# 4. Composition: make _plan_row's LINK branch read `current_text(dest)` instead of composed(dest).
uv run --frozen pytest tests/test_annotation_promote.py::test_two_links_to_one_record_compose                             # expect FAIL, first ref lost
# 5. Index composition: drop the `state=` argument from the plan_promotion call.
uv run --frozen pytest tests/test_prose_promotion_batch.py::test_two_rows_sharing_a_source_slug_produce_one_index_write   # expect FAIL, one promotion dropped
```

Revert each mutation before applying the next. A guard that cannot be made to fail is not certified, and this plan treats an uncertified guard as unfinished work.

- [ ] **Step 15: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

- [ ] **Step 16: Commit**

```bash
git add science/src/science_tool/annotation/promote.py \
        science/src/science_tool/annotation/prose_promote.py \
        science/src/science_tool/annotation/prose_promotion_batch.py \
        science/src/science_tool/entities.py \
        science/tests/
git commit -m "feat(annotation): preflight every promotion workflow before writing"
```

- [ ] **Step 17: Run the full CLI suite**

This change crosses subsystem boundaries — serialization, entity writers, and three workflow surfaces — which is a full-suite trigger. The top-level agent owns this run and passes an explicit long timeout.

`AGENTS.md` records 6:42–7:24 ("about seven minutes"), but that was measured before this branch and a Dropbox-backed checkout is variable. **Pass at least 900000 ms** so a slower run is not killed mid-suite; a foreground run that exceeds the timeout auto-backgrounds, and a subagent that yields waiting on it will not reliably resume.

```bash
cd science && uv run --frozen pytest    # timeout: 900000
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

**Monkeypatch the symbol the caller uses.** These modules import functions by name (`from science_tool.entities import render_entity_source_refs`), so the caller holds its own module-level binding. Patching `science_tool.entities.render_entity_source_refs` after the import has already run changes nothing the caller sees. Every test in this plan patches the **workflow-local** name — `promote_mod.render_entity_source_refs`, `batch.publish_edit`, `recon.publish_edit` — for that reason.

**Certify every guard by mutation.** Tasks 3, 4, 5, 6 and 8 each name the mutation that must make a specific test fail, with the expected failure. Run them.
