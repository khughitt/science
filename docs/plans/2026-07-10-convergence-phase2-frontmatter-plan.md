# Convergence Phase 2 — One Frontmatter API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the toolkit a single canonical *frontmatter API* — a non-lossy splitter, a canonical renderer, and a shared atomic-write primitive — centrally owned in `science_model/frontmatter.py`, and stop new divergence with an additive guard, **without changing the on-disk bytes of any existing entity file.**

**Architecture:** Add the genuinely-missing writer/splitter primitives to `science_model.frontmatter` (the package `science_model` already owns the reader and must not import `science_tool`). Migrate only the emitters and hand-rolled splitters whose output is provably byte-equivalent to the new canonical form (that is: the `commons/promote.py` renderer, and the two body-preserving splitters that are already line-for-line identical). Leave every other emitter exactly as it is, recorded on a **named allowlist with a reason**. Rename the `markdown_utils.parse_frontmatter` namesake (different return type) to `frontmatter_span` so the reader name is unambiguous. Land one structural AST guard that fails when a *new* hand-rolled frontmatter emitter appears outside the canonical module and the allowlist.

**Tech Stack:** Python 3.13, PyYAML (`yaml.safe_dump`/`yaml.safe_load`), Pydantic v2 (only indirectly), pytest, `ast` for the guard. Two nested uv packages: `science/` (CLI, `src/science_tool/`) and `science/model/` (`model/src/science_model/`).

## The reframing that governs this plan (read first)

The design doc ([`2026-07-10-half-applied-pattern-convergence-design.md`](2026-07-10-half-applied-pattern-convergence-design.md), Phase 2) assumed all ~16 emitters could delegate to **one byte-for-byte renderer**. A structural re-census of the tree proved that impossible *and* unsafe: the emitters span 7 distinct `safe_dump` kwarg variants, differ in fence spacing (`---\n` vs `---\n\n`) and body handling, include two hand-written force-quoted f-string templates, and — decisively — the two "canonical-looking" writers already disagree on the most basic kwarg (`entities.py` uses `allow_unicode=False`; `commons/promote.py` uses `allow_unicode=True`). No single renderer can be byte-identical to both, so "migrate everything to one renderer" would necessarily **rewrite source-of-truth entity files**, which the design's own migration-risk section forbids.

**Decision (owner-approved):** This phase converges on **one frontmatter *API*, not one byte *format*.** The win is central ownership and no *new* divergence. Full byte unification (choosing `allow_unicode=True` deliberately, renormalizing existing files, updating fixtures, and running commons/project migration checks) is a **separate future phase — "entity file format normalization"** — explicitly out of scope here. See "Deferred" at the end.

Three rules follow from that decision and bind every task:

1. **No existing entity-file bytes change.** Every migration in this plan is byte-neutral and must be proven so by a test or by the unchanged existing suite. If a candidate migration would alter output, it is *not* migrated — it goes on the allowlist instead.
2. **Treat every current byte form as intentional until proven otherwise.** Migrate an emitter only when its output is byte-equivalent to the canonical form under harvested inputs.
3. **The guard is additive.** It bans *new* ad-hoc frontmatter emitters outside the canonical module and a named legacy allowlist. Every allowlist entry carries a one-line reason (byte preservation / structural special case / pending format-normalization).

## Global Constraints

- **`science_model` must never import `science_tool`.** The new primitives live in `science_model/frontmatter.py`; `science_tool` callers import them directly from `science_model.frontmatter` (or via the existing `data_root` re-export pattern where one already exists).
- **No behavior change to any command's stdout under `--format json`.** JSON payloads are a public automation contract; the snapshot suite (`-m snapshot`) must pass unchanged.
- **No on-disk entity-file byte changes.** (Rule 1 above.)
- **No new CLI commands, no renamed flags, no renamed entities/relations/output schemas.** This is concept-preserving.
- **No "legacy"/"compatibility" shim layers; no `Unified` prefix; no AI-attribution trailers on commits.** (Project rules.)
- **Do NOT create a second `write_entity_file`.** `science_tool.entities.write_entity_file` already exists with a *typed-entity* signature (`write_entity_file(entity, *, body, today, ...)`). Adding a `science_model` function of the same name would recreate the exact namesake collision this phase removes. The canonical low-level writer this phase adds is the **atomic-text primitive** `atomic_write_text(path, text)` plus the **renderer** `render_frontmatter(fields, body)`; entity-policy writing stays in `science_tool.entities` (allowlisted, folds onto `render_frontmatter` only in the future normalization phase).
- **Run tests from the right package.** `science/` for `science_tool`, `science/model/` for `science_model`:
  ```bash
  cd science && uv run --frozen pytest
  cd science/model && uv run --frozen pytest
  cd science && uv run ruff check && uv run pyright
  ```
  The snapshot suite is opt-in: `cd science && uv run --frozen pytest -m snapshot`.
- **Guards are written last, against the migrated tree** (umbrella rule): a guard authored from this document rather than from the migrated code will out-scope its migration and land red. Task 7 explicitly builds its allowlist by running the detector and pinning what it reports.

## File Structure

**Canonical module (all new primitives land here):**
- `science/model/src/science_model/frontmatter.py` — already owns `parse_frontmatter` (lossy reader), `PROJECT_CONFIG_FILENAME`, `project_config_path`, `nearest_project_root`. **Adds:** `atomic_write_text`, `split_frontmatter` (non-lossy), `render_frontmatter_block`, `render_frontmatter`, and the private `_coerce_frontmatter_date` + force-quote constants lifted from `promote.py`.

**Migrated (byte-neutral) consumers:**
- `science/src/science_tool/entities.py` — `_atomic_replace_text` delegates to `atomic_write_text`; `_parse_markdown_file_preserving_body` delegates to `split_frontmatter`.
- `science/src/science_tool/datasets_identity.py` — `_atomic_write` delegates to `atomic_write_text`.
- `science/src/science_tool/dag/workbench_apply.py` — `_parse_existing_target_text` delegates to `split_frontmatter`.
- `science/src/science_tool/commons/promote.py` — `_render_canonical` / `_render_overlay` / `_rewrite_rendered_frontmatter` call `render_frontmatter`; the local `_render_frontmatter`, `_coerce_date_for_yaml`, `_DATE_KEYS`, `_FORCE_QUOTED_KEYS` are deleted.

**Renamed:**
- `science/src/science_tool/markdown_utils.py` — `parse_frontmatter` → `frontmatter_span`; 6 source callers + 1 test updated.

**New guard:**
- `science/tests/test_frontmatter_boundary.py` — structural AST guard (emitter allowlist + single-`parse_frontmatter`-definition).

**Untouched but allowlisted** (recorded with reasons in the guard): `model/templates.py`, `annotation/source_text.py`, `graph/decision_log.py`, `questions.py`, `cli.py` (`_render_inquiry_source`), `datasets_register.py`, `datasets_catalog.py`, `commons/dataset_lifecycle.py`, `commons/reference_graph_promotion.py`, plus `entities.py`/`datasets_identity.py`/`workbench_apply.py` for their *renderer* functions (only their *splitter*/*atomic-write* helpers are migrated).

---

### Task 1: `atomic_write_text` primitive + delegate the two atomic-write dances

**Files:**
- Modify: `science/model/src/science_model/frontmatter.py` (add `atomic_write_text`; add `import os` if absent)
- Modify: `science/src/science_tool/entities.py:1368-1379` (`_atomic_replace_text` → delegate)
- Modify: `science/src/science_tool/datasets_identity.py:38-43` (`_atomic_write` → delegate)
- Test: `science/model/tests/test_frontmatter_atomic_write.py` (new)

**Interfaces:**
- Produces: `atomic_write_text(path: Path, text: str) -> None` in `science_model.frontmatter`.
- Consumes: nothing new.

**Context:** Two independent copies of the temp-file + `os.replace` atomic-write dance exist (`entities._atomic_replace_text` with `except`+`finally`; `datasets_identity._atomic_write` with `finally` only). Both write to `<path>.<suffix>.tmp` then `os.replace`. Consolidate the dance into one primitive; both callers delegate with byte-identical output (same temp path, same `os.replace`). This is the lower-level primitive that a future `write_entity_file` would build on, but this phase adds only the primitive.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_frontmatter_atomic_write.py`:

```python
from pathlib import Path

import pytest

from science_model.frontmatter import atomic_write_text


def test_atomic_write_text_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "entity.md"
    atomic_write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_atomic_write_text_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "entity.md"
    target.write_text("old", encoding="utf-8")
    atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"


def test_atomic_write_text_leaves_no_tmp_file(tmp_path: Path) -> None:
    target = tmp_path / "entity.md"
    atomic_write_text(target, "content\n")
    assert list(tmp_path.iterdir()) == [target]


def test_atomic_write_text_cleans_tmp_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "entity.md"

    def boom(_src: object, _dst: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("science_model.frontmatter.os.replace", boom)
    with pytest.raises(OSError):
        atomic_write_text(target, "content\n")
    # temp file cleaned up; target never created
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_frontmatter_atomic_write.py -v`
Expected: FAIL with `ImportError: cannot import name 'atomic_write_text'`.

- [ ] **Step 3: Implement `atomic_write_text`**

In `science/model/src/science_model/frontmatter.py`, ensure `import os` is present at the top (add it if not), then add near the other path helpers:

```python
def atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically via a temp file + ``os.replace``.

    The single sanctioned atomic-write dance for entity/frontmatter files. It
    absorbs the duplicated temp-file logic formerly in
    ``science_tool.entities._atomic_replace_text`` and
    ``science_tool.datasets_identity._atomic_write``. Same-filesystem
    ``os.replace`` only (no ``fsync``); on failure the temp file is removed and
    the exception re-raised.
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_frontmatter_atomic_write.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Delegate `entities._atomic_replace_text`**

In `science/src/science_tool/entities.py`, replace the body of `_atomic_replace_text` (lines ~1368-1379) so the function becomes a thin delegator (keep the name and signature — it has several in-module callers):

```python
def _atomic_replace_text(path: Path, text: str) -> None:
    atomic_write_text(path, text)
```

Add the import at the top of `entities.py` (with the other `science_model` imports): `from science_model.frontmatter import atomic_write_text`. If `os` is now unused in `entities.py`, remove the `import os` (run ruff to confirm).

- [ ] **Step 6: Delegate `datasets_identity._atomic_write`**

In `science/src/science_tool/datasets_identity.py`, replace the body of `_atomic_write` (lines ~38-43):

```python
def _atomic_write(path: Path, text: str) -> None:
    atomic_write_text(path, text)
```

Add `from science_model.frontmatter import atomic_write_text` to its imports. Remove a now-unused `import os` if ruff flags it.

- [ ] **Step 7: Run the affected suites**

Run: `cd science && uv run --frozen pytest tests/test_entities.py tests/test_datasets_identity.py -q`
(If those exact test files do not exist, run the entity/dataset-identity test modules that do — discover with `cd science && uv run --frozen pytest --collect-only -q | grep -Ei 'entit|identity'`.)
Expected: PASS, unchanged.

Then the model suite: `cd science/model && uv run --frozen pytest -q` → PASS.

- [ ] **Step 8: Lint/type-check**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: clean (0 errors). Fix any unused-import warnings from Steps 5-6.

- [ ] **Step 9: Commit**

```bash
git add science/model/src/science_model/frontmatter.py \
        science/model/tests/test_frontmatter_atomic_write.py \
        science/src/science_tool/entities.py \
        science/src/science_tool/datasets_identity.py
git commit -m "Add atomic_write_text primitive; delegate the two atomic-write dances (convergence Phase 2)"
```

---

### Task 2: `split_frontmatter` — the non-lossy body-preserving splitter

**Files:**
- Modify: `science/model/src/science_model/frontmatter.py` (add `split_frontmatter`)
- Test: `science/model/tests/test_split_frontmatter.py` (new)

**Interfaces:**
- Produces: `split_frontmatter(text: str) -> tuple[dict, str]` in `science_model.frontmatter`.
- Consumes: `yaml` (already imported in the module).

**Context:** The canonical `parse_frontmatter(path)` is **lossy by design** — it ends with `body = parts[2].strip()`, discarding leading/trailing body whitespace — so it is unsafe for read-modify-write on hand-authored files. Two production sites already hand-rolled a byte-identical, CRLF-aware, body-preserving splitter to route around it: `dag/workbench_apply.py::_parse_existing_target_text` (lines 210-227) and `entities.py::_parse_markdown_file_preserving_body` (lines 1545-1564). A third (`explore_ideas.backfill_lens_views`) consumes the `entities.py` one with an explicit comment saying it avoids `parse_frontmatter`'s strip. This task lands the shared primitive; Task 3 rewires those sites onto it.

The canonical contract is exactly the existing hand-rolls (they are identical): operate on **already-read text** (callers read with `newline=""` so line endings are not translated), support both `\n` and `\r\n` openings, return the body **verbatim** after the closing fence, and return `({}, text)` when there is no parseable block, `({}, body)` when the frontmatter is present but not a mapping.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_split_frontmatter.py`:

```python
from science_model.frontmatter import parse_frontmatter, split_frontmatter


def test_preserves_body_verbatim_unlike_parse_frontmatter(tmp_path):
    text = "---\nid: q:demo\nkind: question\n---\n\n  leading and trailing spaces  \n\n"
    fm, body = split_frontmatter(text)
    assert fm == {"id": "q:demo", "kind": "question"}
    # verbatim: the newline after the closing fence, the blank line, the
    # surrounding whitespace, and the trailing blank are ALL kept. The closing
    # marker is "\n---\n"; the body is everything after it, so it starts with
    # the "\n" that preceded the blank line below the fence.
    assert body == "\n  leading and trailing spaces  \n\n"
    # contrast: the lossy reader strips them
    p = tmp_path / "q.md"
    p.write_text(text, encoding="utf-8")
    _, stripped = parse_frontmatter(p)
    assert stripped == "leading and trailing spaces"


def test_crlf_frontmatter_supported():
    text = "---\r\nid: x\r\n---\r\nbody line\r\n"
    fm, body = split_frontmatter(text)
    assert fm == {"id": "x"}
    assert body == "body line\r\n"


def test_no_frontmatter_returns_text_unchanged():
    text = "no frontmatter here\n"
    assert split_frontmatter(text) == ({}, "no frontmatter here\n")


def test_unterminated_frontmatter_returns_text_unchanged():
    text = "---\nid: x\nnever closes\n"
    assert split_frontmatter(text) == ({}, text)


def test_non_mapping_frontmatter_returns_body_only():
    text = "---\n- just\n- a\n- list\n---\nbody\n"
    fm, body = split_frontmatter(text)
    assert fm == {}
    assert body == "body\n"


def test_adjacent_fences_are_not_a_block():
    # Adjacent fences ("---\n" immediately followed by "---\n") contain no
    # "\n---\n" closing marker, so the hand-rolls treat the whole text as
    # having no parseable frontmatter and return it unchanged. split_frontmatter
    # must match that byte-for-byte.
    text = "---\n---\nbody\n"
    assert split_frontmatter(text) == ({}, "---\n---\nbody\n")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_split_frontmatter.py -v`
Expected: FAIL with `ImportError: cannot import name 'split_frontmatter'`.

- [ ] **Step 3: Implement `split_frontmatter`**

In `science/model/src/science_model/frontmatter.py`, add next to `parse_frontmatter`:

```python
def split_frontmatter(text: str) -> tuple[dict, str]:
    """Parse frontmatter and return the body **verbatim** (non-lossy).

    Unlike :func:`parse_frontmatter`, this does not ``.strip()`` the body and
    does not translate line endings, so it is safe for read-modify-write on
    hand-authored files. Callers must read the file with ``newline=""`` so the
    platform does not rewrite ``\\r\\n`` before this sees it.

    Returns ``({}, text)`` when there is no parseable frontmatter block, and
    ``({}, body)`` when the block is present but not a mapping.
    """
    if text.startswith("---\r\n"):
        newline = "\r\n"
    elif text.startswith("---\n"):
        newline = "\n"
    else:
        return ({}, text)
    after_opening_marker = text[len("---" + newline) :]
    closing_marker = f"{newline}---{newline}"
    closing_marker_index = after_opening_marker.find(closing_marker)
    if closing_marker_index == -1:
        return ({}, text)
    frontmatter_text = after_opening_marker[:closing_marker_index]
    body = after_opening_marker[closing_marker_index + len(closing_marker) :]
    frontmatter = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(frontmatter, dict):
        return ({}, body)
    return (frontmatter, body)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_split_frontmatter.py -v`
Expected: PASS (6 passed).

Note: every assertion here is calibrated to the **exact bytes the two hand-rolls produce** (`workbench_apply._parse_existing_target_text` and `entities._parse_markdown_file_preserving_body`), because byte-neutrality with the code Task 3 replaces is the requirement — not any independent notion of "correct." Two consequences that look surprising but are the hand-roll behavior: (a) the preserved body *keeps the newline that followed the closing fence* (`test_preserves_body_verbatim...` asserts a leading `\n`); (b) adjacent fences `"---\n---\n..."` have no `"\n---\n"` closing marker and so return the whole text unchanged (`test_adjacent_fences_are_not_a_block`). Task 3's existing-suite run is the final confirmation; if any hand-roll edge differs, reconcile `split_frontmatter` to the hand-roll and update the offending expectation here (never weaken the *verbatim body* assertions).

- [ ] **Step 5: Lint/type-check**

Run (two commands, each from the worktree root):
```bash
cd science/model && uv run ruff check
cd science && uv run pyright
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/frontmatter.py \
        science/model/tests/test_split_frontmatter.py
git commit -m "Add non-lossy split_frontmatter primitive (convergence Phase 2)"
```

---

### Task 3: Rewire the two hand-rolled body-preserving splitters onto `split_frontmatter`

**Files:**
- Modify: `science/src/science_tool/dag/workbench_apply.py:210-227` (`_parse_existing_target_text`)
- Modify: `science/src/science_tool/entities.py:1545-1564` (`_parse_markdown_file_preserving_body`)
- Test: existing workbench / entities / explore-ideas suites are the oracle (no new test file)

**Interfaces:**
- Consumes: `split_frontmatter` from Task 2.
- Produces: nothing new (both functions keep their names/signatures).

**Context:** Both functions are **line-for-line identical** to `split_frontmatter` (confirmed by reading them). `_parse_existing_target_text(text)` already takes text; `_parse_markdown_file_preserving_body(path)` reads with `newline=""` then applies the same logic. Replacing their bodies with a call to `split_frontmatter` is byte-neutral. `explore_ideas.backfill_lens_views` consumes the `entities.py` one and rides along unchanged. This deletes two copies of the splitter.

- [ ] **Step 1: Confirm the current suites are green (baseline)**

Run: `cd science && uv run --frozen pytest tests/test_workbench_apply.py tests/test_explore_ideas.py -q`
(Discover exact filenames if these differ: `cd science && uv run --frozen pytest --collect-only -q | grep -Ei 'workbench|explore_ideas|lens'`.)
Expected: PASS. Record the count.

- [ ] **Step 2: Rewire `_parse_existing_target_text`**

In `science/src/science_tool/dag/workbench_apply.py`, replace the body of `_parse_existing_target_text` (lines 210-227) with:

```python
def _parse_existing_target_text(text: str) -> tuple[dict[str, object], str]:
    return split_frontmatter(text)
```

Add `from science_model.frontmatter import split_frontmatter` to the imports. Leave `_read_existing_target` (which opens with `newline=""` and calls this) unchanged.

- [ ] **Step 3: Rewire `_parse_markdown_file_preserving_body`**

In `science/src/science_tool/entities.py`, replace the body of `_parse_markdown_file_preserving_body` (lines 1545-1564) with:

```python
def _parse_markdown_file_preserving_body(path: Path) -> tuple[dict[str, Any], str]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    return split_frontmatter(text)
```

Add `split_frontmatter` to the existing `from science_model.frontmatter import ...` line in `entities.py` (it already imports from that module in Task 1).

- [ ] **Step 4: Run the oracle suites**

Run: `cd science && uv run --frozen pytest tests/test_workbench_apply.py tests/test_explore_ideas.py tests/test_entities.py -q`
Expected: PASS with the **same counts** as Step 1's baseline (plus entities). Any diff here means a boundary-behavior mismatch between the old hand-roll and `split_frontmatter` — if so, reconcile `split_frontmatter` to the hand-roll's exact behavior (it is the byte-neutrality oracle) and re-run Task 2's unit tests.

- [ ] **Step 5: Full CLI suite + lint/type**

Run: `cd science && uv run --frozen pytest -q && uv run ruff check && uv run pyright`
Expected: PASS, clean.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/dag/workbench_apply.py \
        science/src/science_tool/entities.py
git commit -m "Route the two body-preserving splitters through split_frontmatter (convergence Phase 2)"
```

---

### Task 4: `render_frontmatter_block` + `render_frontmatter` — the canonical renderer

**Files:**
- Modify: `science/model/src/science_model/frontmatter.py` (add renderer + private helpers)
- Test: `science/model/tests/test_render_frontmatter.py` (new)

**Interfaces:**
- Produces:
  - `render_frontmatter_block(fields: Mapping[str, Any]) -> str` — the munged YAML block, **no** `---` fences.
  - `render_frontmatter(fields: Mapping[str, Any], body: str) -> str` — the full document `---\n{block}---\n{body}`.
- Consumes: `yaml` (already imported), `date`/`datetime` (add if absent), `Mapping`/`Any` (add if absent).

**Context:** The canonical renderer is **lifted verbatim** from `commons/promote.py::_render_frontmatter` (lines 3051-3085), the most complete existing renderer: it coerces `created`/`updated` to ISO strings, force-double-quotes `created`/`updated`/`version`/`pin_version` via a post-dump line fix-up, and dumps with `sort_keys=False, allow_unicode=True, default_flow_style=False, width=10_000`. Task 5 migrates `promote.py` onto this; keeping it byte-identical to promote's current output is what makes that migration byte-neutral. This renderer is the canonical form **for new or explicitly-migrated writers** — it is *not* retrofitted onto the divergent legacy emitters (see the reframing note).

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_render_frontmatter.py`:

```python
from datetime import date, datetime

from science_model.frontmatter import (
    render_frontmatter,
    render_frontmatter_block,
    split_frontmatter,
)


def test_block_basic_shape():
    block = render_frontmatter_block({"id": "q:demo", "kind": "question"})
    assert block == 'id: q:demo\nkind: question\n'


def test_full_document_fences_and_body():
    doc = render_frontmatter({"id": "x"}, "hello body\n")
    assert doc == "---\nid: x\n---\nhello body\n"


def test_force_quotes_version_and_dates():
    block = render_frontmatter_block(
        {"version": "1.0.0", "created": "2026-07-10", "updated": "2026-07-10", "pin_version": "2.1"}
    )
    assert 'version: "1.0.0"' in block
    assert 'created: "2026-07-10"' in block
    assert 'updated: "2026-07-10"' in block
    assert 'pin_version: "2.1"' in block


def test_coerces_date_and_datetime_objects():
    block = render_frontmatter_block(
        {"created": date(2026, 7, 10), "updated": datetime(2026, 7, 10, 8, 30)}
    )
    assert 'created: "2026-07-10"' in block
    assert 'updated: "2026-07-10"' in block


def test_null_and_empty_force_quoted_values_left_unquoted():
    block = render_frontmatter_block({"version": None})
    # None dumps as `null`; the force-quoter leaves null/empty untouched
    assert "version: null" in block


def test_long_scalar_not_wrapped():
    long_value = "x" * 500
    block = render_frontmatter_block({"note": long_value})
    assert long_value in block  # width=10_000 prevents pyyaml wrapping


def test_allow_unicode_true():
    block = render_frontmatter_block({"title": "café"})
    assert "café" in block  # not \uXXXX-escaped


def test_idempotent_fixed_point():
    # Writer idempotence: render -> split -> render must be a fixed point.
    fields = {"id": "q:demo", "kind": "question", "created": "2026-07-10", "version": "1.0.0"}
    body = "Some body text.\n"
    t1 = render_frontmatter(fields, body)
    f2, b2 = split_frontmatter(t1)
    t2 = render_frontmatter(f2, b2)
    assert t1 == t2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_render_frontmatter.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the renderer**

In `science/model/src/science_model/frontmatter.py`, ensure these imports exist at the top (add any that are missing): `from collections.abc import Mapping`, `from datetime import date, datetime`, `from typing import Any`. Then add:

```python
_FRONTMATTER_DATE_KEYS: frozenset[str] = frozenset({"created", "updated"})
# Scalar keys emitted as double-quoted strings regardless of how pyyaml
# serialises them (version strings look numeric to YAML).
_FRONTMATTER_FORCE_QUOTED_KEYS: frozenset[str] = _FRONTMATTER_DATE_KEYS | frozenset(
    {"version", "pin_version"}
)


def _coerce_frontmatter_date(value: Any) -> str:
    """``date``/``datetime``/``str`` → ISO-8601 string; other types via ``str``."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def render_frontmatter_block(fields: Mapping[str, Any]) -> str:
    """Render the canonical YAML frontmatter block (no ``---`` fences).

    The canonical emission for new or explicitly-migrated writers. Reproduces
    the renderer formerly in ``commons/promote.py``: ``created``/``updated``
    coerced to ISO strings and force-double-quoted together with
    ``version``/``pin_version``; ``safe_dump(sort_keys=False,
    allow_unicode=True, default_flow_style=False, width=10_000)``; trailing
    newline. It is deliberately **not** retrofitted onto the divergent legacy
    emitters — see the Phase 2 plan's reframing note.
    """
    out: dict = {}
    for key, value in fields.items():
        if key in _FRONTMATTER_DATE_KEYS:
            out[key] = _coerce_frontmatter_date(value)
        else:
            out[key] = value
    dumped = yaml.safe_dump(
        out,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=10_000,
    )
    lines = []
    for line in dumped.splitlines():
        for k in _FRONTMATTER_FORCE_QUOTED_KEYS:
            prefix = f"{k}:"
            if line.startswith(prefix):
                raw = line[len(prefix) :].strip()
                if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
                    raw = raw[1:-1]
                if raw and raw != "null":
                    line = f'{k}: "{raw}"'
        lines.append(line)
    return "\n".join(lines) + "\n"


def render_frontmatter(fields: Mapping[str, Any], body: str) -> str:
    """Render a full frontmatter document: ``---\\n{block}---\\n{body}``."""
    return f"---\n{render_frontmatter_block(fields)}---\n{body}"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_render_frontmatter.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Lint/type-check**

Run (two commands, each from the worktree root — `cd ../science` from `science/model` would wrongly resolve to `science/science`):
```bash
cd science/model && uv run ruff check
cd science && uv run pyright
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/frontmatter.py \
        science/model/tests/test_render_frontmatter.py
git commit -m "Add canonical render_frontmatter/render_frontmatter_block (convergence Phase 2)"
```

---

### Task 5: Migrate `commons/promote.py` onto the canonical renderer (Test A: golden equivalence)

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (delete local renderer + constants; call `render_frontmatter`/`render_frontmatter_block`)
- Test: `science/tests/test_promote_render_frontmatter_golden.py` (new — the emitter-equivalence oracle) + existing promote suite + snapshot suite

**Interfaces:**
- Consumes: `render_frontmatter`, `render_frontmatter_block` from Task 4.
- Produces: nothing new. `_render_canonical`/`_render_overlay`/`_rewrite_rendered_frontmatter` keep their names.

**Context:** This is the one clean, byte-neutral emitter migration and the keystone that proves the helper. `promote.py::_render_frontmatter` is the *source* of the canonical logic, so `render_frontmatter_block` is byte-identical to it by construction. The three callers build `f"---\n{fm}---\n{body}"` — exactly `render_frontmatter(fields, body)`. This is **Test A** from the design (emitter equivalence), realized as a golden test that pins promote's current output against `render_frontmatter` before deleting the local copy.

**Known local uses of the four symbols to be deleted** (grep to find any stragglers — see Step 1):
- `_render_frontmatter(head)` in `_render_canonical` (3152), `_render_overlay` (3182), `_rewrite_rendered_frontmatter` (2906-2920).
- `_coerce_date_for_yaml(created)` / `_coerce_date_for_yaml(updated)` in `_render_canonical` (3139-3140).
- `_DATE_KEYS`, `_FORCE_QUOTED_KEYS`, `_coerce_date_for_yaml` — defined at 3035-3049.

- [ ] **Step 1: Enumerate every use of the four symbols**

Run:
```bash
cd science && rg -n "_render_frontmatter\b|_coerce_date_for_yaml\b|_DATE_KEYS\b|_FORCE_QUOTED_KEYS\b" src/science_tool/commons/promote.py
```
Expected: the definitions (3035-3085) plus the call sites listed above. If `rg` reports call sites beyond those listed, migrate them too by the same rule (Step 4). Record the full list.

- [ ] **Step 2: Write the golden equivalence test (Test A) — and watch it PASS against the un-migrated code**

Create `science/tests/test_promote_render_frontmatter_golden.py`. This test imports promote's *current* `_render_frontmatter` and asserts `render_frontmatter_block` matches it byte-for-byte over a corpus of harvested frontmatter dicts, so the migration in Step 4 is provably byte-neutral:

```python
"""Test A (emitter equivalence): the canonical render_frontmatter_block must
reproduce commons/promote._render_frontmatter byte-for-byte over a corpus of
realistic frontmatter dicts. Landed BEFORE the migration deletes the local
copy, so the deletion is provably byte-neutral. After Step 4 deletes
promote._render_frontmatter this test is updated to compare against the
harvested golden strings instead (see Step 5)."""

from datetime import date

import pytest

from science_model.frontmatter import render_frontmatter_block

_CORPUS = [
    {"schema_profile": "science-entity-1.0", "id": "paper:smith2020", "kind": "paper",
     "title": "A Study", "version": "1.0.0", "created": date(2026, 7, 10),
     "updated": date(2026, 7, 10), "bibkey": "smith2020", "tags": []},
    {"id": "topic:cell-cycle", "overlay_of": "topic:cell-cycle", "pin_version": "2.3",
     "notes": "café — long " + "x" * 300},
    {"id": "theme:x", "kind": "theme", "title": "t", "version": "0.1",
     "created": "2026-01-01", "updated": "2026-01-02", "related": ["a", "b"]},
    {"id": "empty-version", "version": None, "created": date(2026, 7, 10)},
]


@pytest.mark.parametrize("fields", _CORPUS)
def test_render_frontmatter_block_matches_promote(fields):
    from science_tool.commons.promote import _render_frontmatter as legacy
    assert render_frontmatter_block(dict(fields)) == legacy(dict(fields))
```

Run: `cd science && uv run --frozen pytest tests/test_promote_render_frontmatter_golden.py -v`
Expected: **PASS** (they are byte-identical). If any case fails, `render_frontmatter_block` diverges from promote — fix `render_frontmatter_block` (Task 4) until every case passes. Do not proceed to Step 4 until green.

- [ ] **Step 3: Harvest the golden strings for the post-deletion version of the test**

Once Step 2 is green, capture the exact expected output so the test survives deleting `promote._render_frontmatter`. Run:
```bash
cd science && uv run --frozen python -c "
from science_tool.commons.promote import _render_frontmatter
from datetime import date
import json
corpus = [
  {'schema_profile': 'science-entity-1.0','id':'paper:smith2020','kind':'paper','title':'A Study','version':'1.0.0','created':date(2026,7,10),'updated':date(2026,7,10),'bibkey':'smith2020','tags':[]},
  {'id':'topic:cell-cycle','overlay_of':'topic:cell-cycle','pin_version':'2.3','notes':'café — long ' + 'x'*300},
  {'id':'theme:x','kind':'theme','title':'t','version':'0.1','created':'2026-01-01','updated':'2026-01-02','related':['a','b']},
  {'id':'empty-version','version':None,'created':date(2026,7,10)},
]
for f in corpus:
    print('=====')
    print(_render_frontmatter(dict(f)), end='')
"
```
Keep this output; Step 5 bakes it into the test as literal golden strings.

- [ ] **Step 4: Migrate promote.py — delete the local renderer, call the canonical one**

In `science/src/science_tool/commons/promote.py`:

1. Add the import (with the other `science_model` imports): `from science_model.frontmatter import render_frontmatter, render_frontmatter_block`.
2. In `_render_canonical`, change the two date lines (3139-3140) to pass raw dates (the canonical block coerces them):
   ```python
       "created": created,
       "updated": updated,
   ```
   and change the emit (3152-3154) from
   ```python
       fm = _render_frontmatter(head)
       body = _render_body(canonical_body)
       return f"---\n{fm}---\n{body}"
   ```
   to
   ```python
       body = _render_body(canonical_body)
       return render_frontmatter(head, body)
   ```
3. In `_render_overlay`, change the emit (3182-3184) to:
   ```python
       body = _render_body(project_only_body)
       return render_frontmatter(head, body)
   ```
4. In `_rewrite_rendered_frontmatter` (2906-2920), change the final line from
   ```python
       return f"---\n{_render_frontmatter(parsed)}---\n{body}"
   ```
   to
   ```python
       return render_frontmatter(parsed, body)
   ```
   (Its `.startswith("---\n")` / `.partition("\n---\n")` fence-parsing stays — that is reading, not emitting.)
5. Delete the now-unused `_render_frontmatter`, `_coerce_date_for_yaml`, `_DATE_KEYS`, and `_FORCE_QUOTED_KEYS` definitions (3035-3085). If Step 1 found any other use of `_coerce_date_for_yaml`, replace it with `render_frontmatter_block`-covered behavior or a local ISO coercion as appropriate — but there should be none beyond `_render_canonical`.

`render_frontmatter_block` is imported for symmetry/other callers; if ruff reports it unused after Step 4, drop it from the import (keep only `render_frontmatter`).

- [ ] **Step 5: Convert the golden test to compare against harvested literals**

Replace the body of `test_render_frontmatter_block_matches_promote` so it no longer imports the deleted `promote._render_frontmatter`. Paste the Step-3 output as the expected golden strings, one per corpus entry, and assert `render_frontmatter_block(dict(fields)) == expected`. (This keeps Test A as a permanent regression oracle without depending on the deleted symbol.)

- [ ] **Step 6: Run promote suite + golden + snapshot**

```bash
cd science && uv run --frozen pytest tests/test_promote_render_frontmatter_golden.py -q
cd science && uv run --frozen pytest -k promote -q
cd science && uv run --frozen pytest -m snapshot -q
```
Expected: all PASS unchanged. The snapshot suite is the guard that no `--format json` / emitted-file bytes moved.

- [ ] **Step 7: Full suite + lint/type**

Run: `cd science && uv run --frozen pytest -q && uv run ruff check && uv run pyright`
Expected: PASS, clean.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_promote_render_frontmatter_golden.py
git commit -m "Migrate promote.py onto canonical render_frontmatter; delete local renderer (convergence Phase 2)"
```

---

### Task 6: Rename `markdown_utils.parse_frontmatter` → `frontmatter_span`

**Files:**
- Modify: `science/src/science_tool/markdown_utils.py:205-228` (rename def)
- Modify callers (6 source + 1 test): `labnote_export.py`, `prose_lint.py`, `commons/overlay.py`, `commons/adapter.py`, `commons/dataset_lifecycle.py`, `qa_audit/runs.py`, `tests/test_markdown_utils.py`
- Modify: `science/src/science_tool/topic_coverage.py:61` (doc-comment reference only)

**Interfaces:**
- Produces: `frontmatter_span(path: Path) -> tuple[dict, int]` (renamed; unchanged behavior — returns `(data, body_start_line)`).
- Removes: `markdown_utils.parse_frontmatter` (the namesake that shadowed the canonical reader's name with a different return type).

**Context:** `markdown_utils.parse_frontmatter` returns `tuple[dict, int]` (frontmatter + 1-based body-start line for lint anchoring) — a legitimately different job from `science_model.frontmatter.parse_frontmatter`'s `tuple[dict, str] | None`. Sharing the name is the "import the wrong one, get a silent bug" hazard the phase removes. No file imports both names (verified), so this is a safe mechanical rename. All 7 callers use the plain-name import form `from science_tool.markdown_utils import parse_frontmatter` and unpack a 2-tuple using the int element — confirming they want this version.

- [ ] **Step 1: Rename the definition**

In `science/src/science_tool/markdown_utils.py`, rename `def parse_frontmatter(path: Path) -> tuple[dict, int]:` to `def frontmatter_span(path: Path) -> tuple[dict, int]:` and update its docstring first line to `"""Return ``(frontmatter_data, body_start_line)`` for a markdown file."""` (already accurate). Leave the sibling `frontmatter_line_numbers` untouched.

- [ ] **Step 2: Update the six source callers**

For each file, change the import and every call site from `parse_frontmatter` to `frontmatter_span`:
```bash
cd science && rg -n "parse_frontmatter" \
  src/science_tool/labnote_export.py \
  src/science_tool/prose_lint.py \
  src/science_tool/commons/overlay.py \
  src/science_tool/commons/adapter.py \
  src/science_tool/commons/dataset_lifecycle.py \
  src/science_tool/qa_audit/runs.py
```
Edit each import statement (`from science_tool.markdown_utils import ... parse_frontmatter ...` → `... frontmatter_span ...`) and each call (`parse_frontmatter(` → `frontmatter_span(`). **Caution:** `dataset_lifecycle.py` imports the canonical reader from `science_model` too? No — it imports `parse_frontmatter` only from `markdown_utils` (line 34). Confirm with the rg output that you are only touching the `markdown_utils`-sourced name; do not touch any `science_model.frontmatter` import.

- [ ] **Step 3: Update the test file**

In `science/tests/test_markdown_utils.py`, update the three function-local imports (lines ~56/74/84) and call sites, and rename the three test functions for clarity:
- `test_parse_frontmatter_returns_data_and_body_start` → `test_frontmatter_span_returns_data_and_body_start`
- `test_parse_frontmatter_returns_empty_when_absent` → `test_frontmatter_span_returns_empty_when_absent`
- `test_parse_frontmatter_returns_empty_when_unterminated` → `test_frontmatter_span_returns_empty_when_unterminated`

- [ ] **Step 4: Update the stray doc reference**

In `science/src/science_tool/topic_coverage.py:61`, update the comment mentioning `markdown_utils.parse_frontmatter` to `markdown_utils.frontmatter_span`.

- [ ] **Step 5: Verify no `markdown_utils.parse_frontmatter` reference remains**

Run (multiline-aware — `prose_lint.py` imports the name inside a parenthesized `from ... import (\n  ...\n)` block that a single-line `[^\n]*` regex would skip):
```bash
# -U makes rg match across newlines, so parenthesized multiline imports are caught.
cd science && rg -U -n "markdown_utils\s+import\s*\(?[^)]*\bparse_frontmatter\b" src tests
cd science && rg -n "markdown_utils\.parse_frontmatter" src tests
# Broad backstop: eyeball that EVERY remaining hit resolves to the canonical
# science_model.frontmatter reader, never markdown_utils.
cd science && rg -n "\bparse_frontmatter\b" src tests
```
Expected: the first two commands report **no matches**; the third reports only `science_model.frontmatter`-sourced imports/uses (the canonical reader), which are unaffected and must still be present. The Task 7 guard (`test_parse_frontmatter_defined_once`) and the full suite (an `ImportError` on any stale `from markdown_utils import parse_frontmatter`) are the durable backstops if the grep is ever wrong.

- [ ] **Step 6: Run affected suites + full suite**

Run: `cd science && uv run --frozen pytest tests/test_markdown_utils.py -q && uv run --frozen pytest -q && uv run ruff check && uv run pyright`
Expected: PASS, clean.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/markdown_utils.py \
        science/src/science_tool/labnote_export.py \
        science/src/science_tool/prose_lint.py \
        science/src/science_tool/commons/overlay.py \
        science/src/science_tool/commons/adapter.py \
        science/src/science_tool/commons/dataset_lifecycle.py \
        science/src/science_tool/qa_audit/runs.py \
        science/src/science_tool/topic_coverage.py \
        science/tests/test_markdown_utils.py
git commit -m "Rename markdown_utils.parse_frontmatter to frontmatter_span (convergence Phase 2)"
```

---

### Task 7: The additive guard — `tests/test_frontmatter_boundary.py`

**Files:**
- Create: `science/tests/test_frontmatter_boundary.py`
- Test: the guard is itself the test

**Interfaces:**
- Consumes: nothing (pure `ast` scan of the two source trees).
- Produces: two assertions — (a) emitter allowlist; (b) single canonical `parse_frontmatter` definition.

**Context:** Written **last**, against the migrated tree (umbrella rule). Modeled on Phase 1's `tests/test_project_root_boundary.py` and on `tests/graph/test_durable_write_boundary.py`. Two rules realize the owner's additive-guard directive:

- **Rule A (no new ad-hoc emitters).** A *frontmatter-emitter function* — one that contains a `---` **fence line** in a string literal used to *build* output **and** emits YAML (calls `yaml.safe_dump`/`yaml.dump` directly, or calls a module-local helper that does) — is permitted only in the canonical module, a named emitter allowlist, or a named detector-false-positive set. Each emitter-allowlist entry carries a reason: `byte-preservation` (kwargs/unicode differ), `structural` (fence spacing / body handling differ), `hand-template` (does not dump the top-level frontmatter), or `pending-normalization`.
- **Rule B (reader-name uniqueness).** Exactly one function named `parse_frontmatter` is defined across both source trees, and it is `science_model/frontmatter.py`'s canonical reader. Prevents the namesake collision (just removed in Task 6) from regrowing.

**Two detector subtleties that the naive version got wrong (both found in review):**

1. **Fence detection must be line-based, not exact-equality, because Python folds implicitly-concatenated string literals.** `datasets_register._entity_yaml_block` writes `"---\n" f'schema_profile: "{...}"\n' ... "---\n"`. CPython merges the leading `"---\n"` with the adjacent f-string into a single `Constant("---\nschema_profile: \"")`, which is never `== "---\n"`. So the detector checks whether *any line of any string constant* (walking into `JoinedStr` values, which `ast.walk` yields) is exactly `---` — catching the merged form. Exact-set membership would silently miss this hand-template emitter and let future ones hide behind the same shape.
2. **A `---` literal that is the argument of a string *parsing* method is a read, not an emit.** `cli.py::inquiry_import` calls the local dumper `_render_inquiry_source` **and** later does `text.split("---")`; a naive detector flags it as an emitter, polluting the normalization worklist with a pure consumer. The detector therefore excludes fence constants that appear as arguments to `split`/`partition`/`startswith`/`find`/… so a validator that parses fences is not mistaken for one that emits them.

**Necessary-but-not-sufficient, stated candidly** (as the durable-write guard does): even so, the scan matches a *fence-line literal* + a *dump/known-dumper call* in one function. It will not catch an emitter that constructs the fence at runtime (`"--" + "-"`), emits via a cross-module helper it neither defines nor is a known local dumper for, or writes through `str.format`. Those are not in the tree today; reviewers of new frontmatter code still check by eye. The guard catches the one form that actually recurred. Any residual *consumer* the parsing-arg exclusion does not clear is recorded in `_DETECTOR_FALSE_POSITIVES` (a category kept separate from the emitter allowlist so the normalization worklist stays clean).

- [ ] **Step 1: Draft the guard with an empty allowlist and see what it reports**

Create `science/tests/test_frontmatter_boundary.py` with the detector below but an **empty** `_ALLOWED_EMITTERS`, then run it and read the offender list — that list *is* the migrated tree's emitter set, which you pin in Step 2 (do not hand-transcribe from this plan):

```python
"""Frontmatter-emitter boundary guard (convergence Phase 2).

Additive ratchet: a *new* hand-rolled frontmatter emitter must not appear
outside the canonical module (science_model/frontmatter.py) and the named
legacy allowlist below. It also asserts the reader name `parse_frontmatter` is
defined in exactly one place, so the namesake collision cannot regrow.

Detection (Rule A): a function is a frontmatter emitter if it contains a `---`
*fence line* inside a string literal that is NOT a parsing-method argument, AND
emits YAML — either a direct `yaml.safe_dump`/`yaml.dump` call, or a call to a
module-local helper that itself calls one. Fence detection is line-based (any
line of any string constant equal to `---`), so it survives CPython folding
implicitly-concatenated literals into one `Constant`; `ast.walk` descends into
`JoinedStr` values, so f-strings are covered. Parsing-method arguments
(`split`/`partition`/`startswith`/…) are excluded so a fence *reader* is not
mistaken for an emitter. This is necessary-but-not-sufficient: it will not catch
a fence constructed at runtime, emitted via an unknown cross-module helper, or
written through `str.format`. None exist today; this guard stops the bare form
that recurred.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SCIENCE_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_MODEL_SRC = Path(__file__).resolve().parents[1] / "model" / "src" / "science_model"

# Canonical module: the one place a frontmatter renderer/dumper may co-exist
# with fence literals without allowlisting.
_CANONICAL = _MODEL_SRC / "frontmatter.py"

# String methods that *read* a fence rather than emit one; a fence literal
# passed to one of these is not evidence of emission.
_PARSING_METHODS = {
    "split", "rsplit", "partition", "rpartition",
    "startswith", "endswith", "find", "rfind", "index", "rindex", "count",
}


def _source_files() -> list[Path]:
    files: list[Path] = []
    for root in (_SCIENCE_SRC, _MODEL_SRC):
        files.extend(p for p in root.rglob("*.py"))
    return files


def _contains_fence(value: str) -> bool:
    """True if any line of ``value`` is exactly a ``---`` frontmatter fence.

    Line-based (not exact-equality) so it matches the merged ``Constant`` that
    results from implicitly-concatenating ``"---\\n"`` with an adjacent
    f-string (e.g. ``"---\\nschema_profile: \\""``).
    """
    return any(line.rstrip("\r") == "---" for line in value.split("\n"))


def _is_yaml_dump_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"safe_dump", "dump"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "yaml"
    )


def _local_dumper_names(tree: ast.Module) -> set[str]:
    """Names of module-level functions whose body calls yaml.safe_dump/dump."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            _is_yaml_dump_call(n) for n in ast.walk(node)
        ):
            names.add(node.name)
    return names


def _parsing_arg_constant_ids(func: ast.AST) -> set[int]:
    """id()s of string constants passed to fence-*parsing* methods, so a
    ``text.split("---")`` validator is not read as an emitter."""
    ids: set[int] = set()
    for n in ast.walk(func):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in _PARSING_METHODS
        ):
            for arg in n.args:
                ids.add(id(arg))
    return ids


def _function_is_emitter(func: ast.AST, dumpers: set[str]) -> bool:
    parsing_ids = _parsing_arg_constant_ids(func)
    has_emitting_fence = False
    emits = False
    for n in ast.walk(func):
        if (
            isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and _contains_fence(n.value)
            and id(n) not in parsing_ids
        ):
            has_emitting_fence = True
        if _is_yaml_dump_call(n):
            emits = True
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in dumpers:
            emits = True
    return has_emitting_fence and emits


def _emitter_functions() -> list[tuple[str, str]]:
    """Return (relative_path, function_name) for every frontmatter emitter."""
    found: list[tuple[str, str]] = []
    repo_root = Path(__file__).resolve().parents[1]
    for path in _source_files():
        if path == _CANONICAL:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        dumpers = _local_dumper_names(tree)
        rel = str(path.relative_to(repo_root))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _function_is_emitter(
                node, dumpers
            ):
                found.append((rel, node.name))
    return found


# (rel_path, function_name) -> reason. Genuinely-divergent legacy emitters =
# the format-normalization worklist. Filled in Step 2 from the Step-1 report.
_ALLOWED_EMITTERS: dict[tuple[str, str], str] = {}

# (rel_path, function_name) -> reason. Consumers/validators that trip the
# heuristic but emit nothing distinct (e.g. call a renderer AND parse fences).
# Kept OUT of _ALLOWED_EMITTERS so the normalization worklist stays clean.
_DETECTOR_FALSE_POSITIVES: dict[tuple[str, str], str] = {}


def _exempt() -> set[tuple[str, str]]:
    return set(_ALLOWED_EMITTERS) | set(_DETECTOR_FALSE_POSITIVES)


def test_no_new_frontmatter_emitters() -> None:
    offenders = [pair for pair in _emitter_functions() if pair not in _exempt()]
    assert not offenders, (
        "New hand-rolled frontmatter emitter(s) found outside the canonical "
        "module (science_model/frontmatter.py) and the named allowlist. Route "
        "new writers through render_frontmatter(fields, body); if the byte form "
        "is deliberately divergent add an _ALLOWED_EMITTERS entry with a reason; "
        "if it is a consumer the detector misclassified, add a "
        f"_DETECTOR_FALSE_POSITIVES entry. Offenders: {sorted(offenders)}"
    )


def test_allowlist_has_no_stale_entries() -> None:
    live = set(_emitter_functions())
    stale = [pair for pair in _exempt() if pair not in live]
    assert not stale, (
        "Allowlisted/false-positive entries no longer detected as emitters "
        f"(migrated or removed?). Delete these stale entries: {sorted(stale)}"
    )


def test_parse_frontmatter_defined_once() -> None:
    definitions: list[str] = []
    repo_root = Path(__file__).resolve().parents[1]
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "parse_frontmatter":
                definitions.append(str(path.relative_to(repo_root)))
    assert definitions == ["model/src/science_model/frontmatter.py"], (
        "parse_frontmatter must be defined in exactly one place "
        "(science_model/frontmatter.py). A same-named reader elsewhere is the "
        f"namesake collision Phase 2 removed. Definitions found: {sorted(definitions)}"
    )
```

Run: `cd science && uv run --frozen pytest tests/test_frontmatter_boundary.py -v`
Expected: `test_no_new_frontmatter_emitters` FAILS, printing the emitter list. `test_parse_frontmatter_defined_once` should PASS (Task 6 already removed the namesake). `test_allowlist_has_no_stale_entries` PASSES (both exemption sets empty). Confirm the printed list **includes** `datasets_register.py::_entity_yaml_block` (the line-based fence check must catch the folded-constant hand-template) and **excludes** `cli.py::inquiry_import` (the parsing-arg exclusion must drop the `text.split("---")` consumer). If either is wrong, the detector is not behaving as intended — fix it before Step 2.

- [ ] **Step 2: Pin the reported emitters into the allowlist with reasons**

Take the exact `(rel_path, function_name)` pairs the Step-1 failure printed and fill `_ALLOWED_EMITTERS`. The expected set (verify against the actual report — the report governs) is:

```python
_ALLOWED_EMITTERS: dict[tuple[str, str], str] = {
    # --- byte-preservation: allow_unicode=False core-entity format; folds onto
    #     render_frontmatter only in the future format-normalization phase.
    ("src/science_tool/entities.py", "_render_markdown"): "pending-normalization: allow_unicode=False core-entity renderer",
    ("src/science_tool/entities.py", "build_entity_markdown"): "pending-normalization: allow_unicode=False core-entity renderer",
    ("src/science_tool/entities.py", "_merge_extra_frontmatter"): "pending-normalization: allow_unicode=False core-entity renderer",
    ("src/science_tool/dag/workbench_apply.py", "_render_entity_text_from_frontmatter"): "pending-normalization: allow_unicode=False entity update on RMW path",
    # --- structural: fence spacing / body handling differ from canonical.
    ("src/science_tool/annotation/source_text.py", "render_source_md"): "structural: ---\\n\\n spacing + passage-offset fixpoint loop",
    ("src/science_tool/graph/decision_log.py", "render_owner_file"): "structural: ---\\n\\n spacing + rstrip body",
    ("src/science_tool/questions.py", "_render_stub"): "structural: yaml.dump + rstrip + ---\\n\\n",
    ("src/science_tool/cli.py", "_render_inquiry_source"): "structural: Variant D kwargs + ---\\n\\n",
    ("src/science_tool/datasets_identity.py", "_render_entity"): "structural: no newline after closing fence (body_suffix)",
    ("src/science_tool/datasets_catalog.py", "_render_candidate"): "structural: ---\\n\\n spacing",
    ("src/science_tool/datasets_catalog.py", "_render_entity"): "structural: ---\\n\\n + body .strip()",
    ("src/science_tool/datasets_catalog.py", "verify_access"): "structural: ---\\n\\n + body lstrip; fm mutated in place",
    ("src/science_tool/datasets_register.py", "_rewrite_run_frontmatter"): "byte-preservation: Variant C kwargs, no force-quoting on run entities",
    ("src/science_tool/commons/reference_graph_promotion.py", "_render_entity"): "byte-preservation: no allow_unicode; frontmatter-only block",
    # --- hand-template: top-level frontmatter is hand-written, not dumped.
    ("src/science_tool/datasets_register.py", "_entity_yaml_block"): "hand-template: force-quoted f-string scaffold; safe_dump only for sub-blocks",
    ("src/science_tool/commons/dataset_lifecycle.py", "_entity_text"): "hand-template: triple-quoted scaffold; safe_dump only for sub-blocks",
    # --- pending-normalization: templated-entity renderer inside science_model.
    ("model/src/science_model/templates.py", "render"): "pending-normalization: templated-entity Renderer, placeholder substitution, no allow_unicode",
}
```

Note `datasets_register.py::_entity_yaml_block` and `commons/dataset_lifecycle.py::_entity_text` appear (both are hand-templates the line-based fence check now catches). Note `cli.py::inquiry_import` should **not** appear (parsing-arg exclusion).

Triage every reported pair into exactly one of two sets:
- **Genuinely-divergent legacy emitter** → `_ALLOWED_EMITTERS` (above), with a `byte-preservation` / `structural` / `hand-template` / `pending-normalization` reason. These are the format-normalization worklist.
- **Detector false positive** (a consumer/validator that calls a renderer and/or parses fences but emits no distinct byte form) → `_DETECTOR_FALSE_POSITIVES`, with a `consumer:` reason. Keeping these out of `_ALLOWED_EMITTERS` stops the worklist from being polluted. If the parsing-arg exclusion already cleared the ones you expected (e.g. `inquiry_import`), this set may stay empty.

If a pair listed above is *absent* from the report, remove it (stale entries fail `test_allowlist_has_no_stale_entries`). If a pair appears that is in neither category, it is a real new emitter the detector correctly caught — that is the guard doing its job, not something to allowlist away.

- [ ] **Step 3: Run the guard green**

Run: `cd science && uv run --frozen pytest tests/test_frontmatter_boundary.py -v`
Expected: all three tests PASS.

- [ ] **Step 4: Adversarial check — the guard actually bites**

Temporarily add a new emitter to a non-allowlisted module to confirm Rule A fails, then revert. For example, append to `science/src/science_tool/refs.py`:
```python
def _bogus_emitter(fm: dict, body: str) -> str:
    import yaml
    return "---\n" + yaml.safe_dump(fm) + "---\n" + body
```
Run the guard → `test_no_new_frontmatter_emitters` must FAIL naming `refs.py::_bogus_emitter`. Then delete the function and confirm the guard passes again. (Do not commit the bogus function.)

- [ ] **Step 5: Lint/type-check**

Run: `cd science && uv run ruff check tests/test_frontmatter_boundary.py && uv run pyright`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add science/tests/test_frontmatter_boundary.py
git commit -m "Guard: ban new hand-rolled frontmatter emitters + single parse_frontmatter def (convergence Phase 2)"
```

---

## Deferred (explicitly out of scope) — record, do not implement

- **Entity file format normalization** (the full byte-unification the design originally imagined): pick `allow_unicode=True` deliberately, fold every allowlisted emitter onto `render_frontmatter`, renormalize existing `*.md` entity files across projects and `~/d/science-commons`, produce reviewable before/after fixture diffs, and run commons/project migration + validation checks. This *rewrites source-of-truth bytes* and must be its own designed migration — not hidden in a convergence cleanup. Every `_ALLOWED_EMITTERS` entry tagged `pending-normalization` / `byte-preservation` is a worklist item for that phase.
- **`write_entity_file` in `science_model`**: not added (name already taken in `science_tool.entities` with a typed-entity signature). Entity-policy writing stays in `science_tool`; it consumes `render_frontmatter` only after normalization resolves the `allow_unicode` conflict.
- **`datasets_register._rewrite_run_frontmatter` / `datasets_catalog` / `dataset_lifecycle` emitters**: left byte-exact on the allowlist; candidates for normalization, not for this phase.

## Test strategy (whole-phase)

Behavior-preserving, so the existing suite is the primary oracle. At the end of every task and once at the end of the branch:
```bash
cd science && uv run --frozen pytest -q
cd science/model && uv run --frozen pytest -q
cd science && uv run --frozen pytest -m snapshot -q      # emitted-bytes / --format json contract
cd science && uv run ruff check && uv run pyright
cd science/model && uv run ruff check
```
The two additions that carry real risk are **Test A** (Task 5's golden equivalence — the only place a silent byte regression was plausible, now pinned) and the **snapshot suite** (proves no emitted entity file or JSON payload moved). Both must be green before the branch is finished.

## Notes reconciled against the design doc

- The design's "12 importing modules" of the canonical reader is currently **13** (a re-census figure; `graph/migrate.py` is a newer importer). No task depends on the count; noted for accuracy.
- The design mandated migrating `model/templates.py` "first" to validate the helper's generality. Under the owner's byte-equivalence rule that renderer is **not** byte-equivalent (Variant D, no `allow_unicode`, no force-quoting), so it is **allowlisted (`pending-normalization`)**, not migrated. Its generality question — can `render_frontmatter` express the templated case — is a normalization-phase concern, not a byte-migration this phase performs.
- The design's Phase 2 guard allowlisted exactly two modules (assuming full migration). Under Option A the allowlist is the named legacy-emitter set above; the guard is additive (bans *new* emitters) rather than proving *global* single-ownership. This is the owner-approved trade.
