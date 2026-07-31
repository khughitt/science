# Annotation Writer Containment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route `annotation/promote.py` and `annotation/synthesize.py` off the uncontained
full-model dump `entities.write_entity_file` and onto the contained renderers, closing the live
data-loss path where re-minting an existing claim silently deletes synthesis results.

**Architecture:** Ownership of frontmatter keys moves from per-*kind* to per-*writer* (an
`Ownership` value object), because the three writers of `proposition` own genuinely different
sets. The admit-then-render dance currently inlined in `dag/workbench.py` moves into
`dag/entity_frontmatter.py` behind three operation-named entry points — `create_entity_file`,
`update_entity_file`, `upsert_entity_file` — one per operation any writer actually performs.
`promote` becomes create-only: an existing record asserting the *same* claim accrues provenance
via `append_entity_source_ref` rather than being rewritten. Finally `write_entity_file` is
deleted and a guard keeps it retired.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, `uv`, ruff, pyright.

**Design doc:** [`2026-07-31-annotation-writer-containment-design.md`](2026-07-31-annotation-writer-containment-design.md)
(revision 3). Section references below (§4.1, §5.3, …) point at it. Read §2.4 before Task 4 —
it is the defect the whole slice exists to close.

## Global Constraints

- **Branch:** `annotation-writer-containment`, in the worktree
  `.worktrees/proposition-corpus-remediation`. Verify with `git branch --show-current` before
  the first commit of every task — this checkout is Dropbox-synced and its branch can move
  between sessions.
- **Working directory:** all `uv` commands run from `science/`. There is no root
  `pyproject.toml`; running `uv run` from the repo root is the most common orientation mistake.
- **This slice repairs no existing records.** 697 malformed records across three projects stay
  malformed (§3, §6). Any step that looks like a backfill is out of scope — reject it.
- **No legacy/compatibility shims** and no `Unified` prefix (repo conventions, `AGENTS.md`).
- **No AI-attribution trailers** on any commit.
- **Do not touch** the legacy triple (`legacy_relation_label` / `legacy_patch` /
  `legacy_edge_id`), `render_update`'s stale-owned-key hole (F4), or `materialize.py`'s legacy
  emitters. All are explicitly out of scope (§3) and all are live (§2.3).
- **Full suite is ~10 min**, longer than the default 120s timeout. Per-task steps below give
  scoped selections; run the full suite only at the final verification step, with an explicit
  long timeout.
- `-m real_projects` has **three known pre-existing failures on `main`**. Reproduce any failure
  at the merge-base before attributing it to this branch.

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/dag/entity_frontmatter.py` | Ownership value object; the three operation entry points; contained renderers | Modify — the bulk of the slice |
| `science/src/science_tool/dag/workbench.py` | Workbench compile writer | Modify — delegates its inlined dance to the shared upsert |
| `science/src/science_tool/dag/workbench_apply.py` | Workbench apply-plan writer | Modify — three renderer calls carry `ownership` |
| `science/src/science_tool/annotation/promote.py` | Promotion mint/link; `MintFn` contract | Modify — create-only + accrual; widened `MintFn` |
| `science/src/science_tool/annotation/prose_promote.py` | Single prose-unit promotion | Modify — `MintFn` accounting |
| `science/src/science_tool/annotation/prose_promotion_batch.py` | Batch prose promotion | Modify — `MintFn` accounting |
| `science/src/science_tool/annotation/synthesize.py` | Proposition reasoning-field writer | Modify — update-only entry point |
| `science/src/science_tool/entities.py` | General entity layer | Modify — `write_entity_file` deleted |
| `science/tests/test_annotation_writer_containment.py` | New: containment + accrual behaviour | Create |
| `science/tests/test_write_entity_file_retired_guard.py` | New: retirement guard | Create |

**Where the `Ownership` declarations live** — this deviates from the design's §4.1 presentation,
which shows all four in one block, and the deviation is required:

- `Ownership`, `WORKBENCH_PROPOSITION`, `WORKBENCH_EVIDENCE_LINE`, `workbench_ownership()` →
  `dag/entity_frontmatter.py`.
- `PROMOTE_PROPOSITION` → `annotation/promote.py`.
- `SYNTHESIZE_PROPOSITION` → `annotation/synthesize.py`.

`SYNTHESIZE_PROPOSITION` must be derived from `synthesize.SYNTH_FIELDS` in code (§4.1). If it
lived in `entity_frontmatter`, that module would import `annotation.synthesize` — while
`annotation.synthesize` imports `update_entity_file` from `entity_frontmatter` (Task 5). That is
a circular import. Keeping each writer's ownership beside that writer makes the dependency
one-way (`annotation.*` → `dag.entity_frontmatter`) and matches the section's own thesis that
ownership is a property of the writer.

---

### Task 1: The `Ownership` value object

**Files:**
- Modify: `science/src/science_tool/dag/entity_frontmatter.py:65-70`
- Test: `science/tests/test_workbench_writer_containment.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `Ownership(owned: frozenset[str], create_only: frozenset[str] = frozenset())`,
  frozen dataclass; `WORKBENCH_PROPOSITION`, `WORKBENCH_EVIDENCE_LINE`;
  `workbench_ownership(kind: str) -> Ownership` raising `FrontmatterRenderError` on an
  unsupported kind.

Pure addition. `owned_keys` stays until Task 2, so the tree is green throughout.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_workbench_writer_containment.py`:

```python
def test_workbench_ownership_carries_todays_sets_verbatim() -> None:
    from science_tool.dag.entity_frontmatter import (
        CREATE_ONLY_KEYS,
        EVIDENCE_LINE_OWNED_KEYS,
        PROPOSITION_OWNED_KEYS,
        WORKBENCH_EVIDENCE_LINE,
        WORKBENCH_PROPOSITION,
        workbench_ownership,
    )

    # Ownership SEMANTICS are unchanged by construction -- that is the point of §4.1.
    assert WORKBENCH_PROPOSITION.owned == PROPOSITION_OWNED_KEYS
    assert WORKBENCH_PROPOSITION.create_only == CREATE_ONLY_KEYS
    assert WORKBENCH_EVIDENCE_LINE.owned == EVIDENCE_LINE_OWNED_KEYS
    assert WORKBENCH_EVIDENCE_LINE.create_only == CREATE_ONLY_KEYS

    assert workbench_ownership("proposition") is WORKBENCH_PROPOSITION
    assert workbench_ownership("evidence-line") is WORKBENCH_EVIDENCE_LINE


def test_workbench_ownership_rejects_unsupported_kind() -> None:
    from science_tool.dag.entity_frontmatter import FrontmatterRenderError, workbench_ownership

    with pytest.raises(FrontmatterRenderError, match="unsupported workbench entity kind: dataset"):
        workbench_ownership("dataset")


def test_ownership_defaults_create_only_to_empty() -> None:
    from science_tool.dag.entity_frontmatter import Ownership

    # synthesize owns no create-only keys -- it never creates. The default must be empty,
    # not CREATE_ONLY_KEYS, or an update-only writer would claim `title`.
    assert Ownership(frozenset({"predicate"})).create_only == frozenset()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_workbench_writer_containment.py -k ownership -v
```

Expected: FAIL — `ImportError: cannot import name 'Ownership'`.

- [ ] **Step 3: Write minimal implementation**

In `dag/entity_frontmatter.py`, add `from dataclasses import dataclass` to the imports, then
insert immediately after `CREATE_ONLY_KEYS` (line 62) and **above** `owned_keys`:

```python
@dataclass(frozen=True)
class Ownership:
    """Which frontmatter keys ONE writer owns.

    Per-writer, not per-kind: three writers mint propositions and each owns a different set.
    Widening a shared per-kind allowlist to their union would give the workbench ownership of
    `source_refs` -- so every `compile_workbench` recompile would overwrite an author's curated
    value on a path this design does not otherwise touch.

    `create_only` defaults to EMPTY, not to CREATE_ONLY_KEYS: an update-only writer creates
    nothing and must not claim `title`.
    """

    owned: frozenset[str]
    create_only: frozenset[str] = frozenset()


WORKBENCH_PROPOSITION = Ownership(PROPOSITION_OWNED_KEYS, CREATE_ONLY_KEYS)
WORKBENCH_EVIDENCE_LINE = Ownership(EVIDENCE_LINE_OWNED_KEYS, CREATE_ONLY_KEYS)


def workbench_ownership(kind: str) -> Ownership:
    """Workbench two-kind dispatch. Retains today's fail-early raise on an unsupported kind."""
    if kind == "proposition":
        return WORKBENCH_PROPOSITION
    if kind == "evidence-line":
        return WORKBENCH_EVIDENCE_LINE
    raise FrontmatterRenderError(f"unsupported workbench entity kind: {kind}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_workbench_writer_containment.py -v
```

Expected: PASS, including the pre-existing containment tests.

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/proposition-corpus-remediation
git branch --show-current   # must print: annotation-writer-containment
git add science/src/science_tool/dag/entity_frontmatter.py science/tests/test_workbench_writer_containment.py
git commit -m "feat(entity-frontmatter): add per-writer Ownership value object

Ownership is a property of the writer, not the kind: three writers mint
propositions and each owns a different set. The workbench sets are carried
over verbatim, so its ownership semantics are unchanged by construction."
```

---

### Task 2: Renderers take `Ownership` explicitly

**Files:**
- Modify: `science/src/science_tool/dag/entity_frontmatter.py:124-133` (`render_create`),
  `:165-192` (`render_update`), and delete `owned_keys` at `:65-70`
- Modify: `science/src/science_tool/dag/workbench.py:372` (`render_update`), `:380` (`render_create`)
- Modify: `science/src/science_tool/dag/workbench_apply.py:178` (`render_create`), `:196` and
  `:206` (`render_update`)
- Test: `science/tests/test_workbench_apply.py`, `science/tests/test_workbench_writer_containment.py`

**Interfaces:**
- Consumes: `Ownership`, `workbench_ownership` (Task 1).
- Produces:
  `render_create(entity, *, ownership: Ownership, body: str, created: str, updated: str) -> str`
  and
  `render_update(entity, *, ownership: Ownership, existing_frontmatter: dict[str, object], body: str, created: str, updated: str) -> str`.
  `owned_keys` no longer exists.

**All five renderer call sites** must be carried through explicitly (§5.2). Ownership equality
is guaranteed by construction; nothing else on the workbench path is. The call site at
`workbench_apply.py:196` is the **unchanged-timestamp no-op probe** — its result feeds a
`== current_text` comparison, so it is the one most likely to change behaviour silently.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_workbench_apply.py`:

```python
def test_noop_entity_edit_still_writes_nothing(tmp_path: Path) -> None:
    """The unchanged-timestamp probe (workbench_apply.py:196) must keep detecting no-ops.

    Its verdict depends on render_update's OUTPUT, not on ownership alone, so threading an
    `ownership` argument through it could flip a no-op into a spurious write without any
    ownership set changing. Re-planning an already-applied edit must stay `changed=False`.
    """
    _seed_project(tmp_path)
    entity = _proposition()

    first = _entity_edit(tmp_path, entity, as_of=date(2026, 7, 4))
    assert first.changed is True
    first.path.parent.mkdir(parents=True, exist_ok=True)
    first.path.write_text(first.final_text, encoding="utf-8")

    # Same entity, LATER date. The timestamp probe must recognise the content as unchanged
    # and decline to bump `updated`.
    second = _entity_edit(tmp_path, entity, as_of=date(2026, 8, 1))
    assert second.changed is False
    assert second.final_text == first.final_text
    assert "updated: '2026-07-04'" in second.final_text
```

Add `_entity_edit` to the imports at the top of the file if it is not already imported:

```python
from science_tool.dag.workbench_apply import _entity_edit
```

- [ ] **Step 2: Run test to verify it passes on the current code**

```bash
cd science && uv run --frozen pytest tests/test_workbench_apply.py::test_noop_entity_edit_still_writes_nothing -v
```

Expected: **PASS**. This is a characterization test — it pins behaviour that must survive the
refactor, so it is green before and after. If it fails now, stop: the probe is already broken
and that is a separate bug.

- [ ] **Step 3: Change the renderer signatures**

In `dag/entity_frontmatter.py`, delete `owned_keys` (lines 65-70) and rewrite both renderers:

```python
def render_create(
    entity: WorkbenchEntity, *, ownership: Ownership, body: str, created: str, updated: str
) -> str:
    """Render a NEW entity file from the owned allowlist plus the writer's create-only keys."""
    generated = generated_frontmatter(entity, created=created, updated=updated)
    allowed = ownership.owned | ownership.create_only
    final = {key: value for key, value in generated.items() if key in allowed}
    final["created"] = created
    final["updated"] = updated
    text = render_from_frontmatter(final, body)
    certify_persisted(entity, text)
    return text


def render_update(
    entity: WorkbenchEntity,
    *,
    ownership: Ownership,
    existing_frontmatter: dict[str, object],
    body: str,
    created: str,
    updated: str,
) -> str:
    """Render an EXISTING entity file: overwrite only owned keys, preserve everything else.

    `ownership.create_only` is deliberately NOT applied here -- that is what makes `title`
    create-only and lets an author's replacement survive.
    """
    final = {
        key: value
        for key, value in existing_frontmatter.items()
        if key not in RENDERER_DERIVED_KEYS
    }
    generated = generated_frontmatter(entity, created=created, updated=updated)
    for key in ownership.owned:
        if key in generated:
            final[key] = generated[key]
    final["created"] = created
    final["updated"] = updated
    text = render_from_frontmatter(final, body)
    certify_persisted(entity, text)
    return text
```

`created` / `updated` are still stamped unconditionally after the allowlist filter, which is why
the per-writer sets in Tasks 4 and 5 may omit them (§4.1).

- [ ] **Step 4: Carry all five call sites**

In `dag/workbench.py`, add `workbench_ownership` to the local import at line 358, then pass it:

```python
        text = render_update(
            entity,
            ownership=workbench_ownership(entity.kind),
            existing_frontmatter=existing_frontmatter,
            body=existing_body,
            created=str(existing_frontmatter["created"]),
            updated=today,
        )
    else:
        text = render_create(
            entity,
            ownership=workbench_ownership(entity.kind),
            body=workbench_entity_body(entity),
            created=today,
            updated=today,
        )
```

In `dag/workbench_apply.py`, add `workbench_ownership` to the import block at lines 20-21, then
pass `ownership=workbench_ownership(entity.kind)` to **all three** calls — `:178`, the `:196`
probe, and `:206`.

- [ ] **Step 5: Run the workbench suites**

```bash
cd science && uv run --frozen pytest \
  tests/test_workbench_apply.py \
  tests/test_workbench_writer_containment.py \
  tests/test_workbench_compile_conformance.py -v
```

Expected: PASS, including `test_noop_entity_edit_still_writes_nothing`.

- [ ] **Step 6: Verify no `owned_keys` references survive**

```bash
cd science && grep -rn "owned_keys" src/ tests/
```

Expected: only `PROPOSITION_OWNED_KEYS` / `EVIDENCE_LINE_OWNED_KEYS` constant names. No bare
`owned_keys(`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/dag/ science/tests/test_workbench_apply.py
git commit -m "refactor(entity-frontmatter)!: renderers take Ownership explicitly

Replaces owned_keys(kind) with an explicit ownership argument at all five
renderer call sites. Adds a characterization test for the unchanged-timestamp
no-op probe, whose verdict depends on render_update's output rather than on
ownership alone."
```

---

### Task 3: Three operation-named entry points

**Files:**
- Modify: `science/src/science_tool/dag/entity_frontmatter.py` (append)
- Modify: `science/src/science_tool/dag/workbench.py:345-385` (delegate)
- Test: `science/tests/test_annotation_writer_containment.py` (create)

**Interfaces:**
- Consumes: `Ownership`, `render_create`, `render_update`, `read_existing_target` (Tasks 1-2).
- Produces:
  - `create_entity_file(entity, *, project_root: Path, ownership: Ownership, create_body: str, as_of: date | None = None) -> Path` — raises `EntityWriteError` if the destination **exists**.
  - `update_entity_file(entity, *, project_root: Path, ownership: Ownership, as_of: date | None = None) -> Path` — raises `EntityWriteError` if the destination is **missing**; takes no `create_body`.
  - `upsert_entity_file(entity, *, project_root: Path, ownership: Ownership, create_body: str, as_of: date | None = None) -> Path` — today's workbench behaviour.
  - `class EntityWriteError(ValueError)`.

Three entry points, not one, because each writer performs exactly one operation and naming it is
what keeps the other branches from existing (§4.2). Handing `synthesize` an upsert would force a
`create_body` argument that can never be used — and a value invented to satisfy a signature is
the silent fallback that would one day mint a proposition from a stub body.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_annotation_writer_containment.py`:

```python
"""Containment of the annotation writers (design 2026-07-31, §4.2-§4.4)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from science_model.propositions import PropositionEntity

from science_tool.dag.entity_frontmatter import (
    EntityWriteError,
    Ownership,
    create_entity_file,
    update_entity_file,
)

OWNERSHIP = Ownership(frozenset({"id", "kind", "subject", "object"}), frozenset({"title", "status"}))


def _seed(tmp_path: Path) -> Path:
    # `resolve_path_policy` needs no science.yaml for the default layout -- see
    # test_annotation_promote.py:265, which seeds exactly this and nothing else.
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    return tmp_path


def _prop(**kw) -> PropositionEntity:
    base = dict(id="proposition:p", title="A affects B", subject="concept:a", object="concept:b")
    base.update(kw)
    return PropositionEntity(**base)


def test_create_entity_file_refuses_existing_destination(tmp_path: Path) -> None:
    root = _seed(tmp_path)
    entity = _prop()
    create_entity_file(entity, project_root=root, ownership=OWNERSHIP,
                       create_body="# body\n", as_of=date(2026, 7, 31))

    with pytest.raises(EntityWriteError, match="already exists"):
        create_entity_file(entity, project_root=root, ownership=OWNERSHIP,
                           create_body="# body\n", as_of=date(2026, 7, 31))


def test_update_entity_file_refuses_missing_destination(tmp_path: Path) -> None:
    root = _seed(tmp_path)
    with pytest.raises(EntityWriteError, match="does not exist"):
        update_entity_file(_prop(), project_root=root, ownership=OWNERSHIP, as_of=date(2026, 7, 31))


def test_update_entity_file_takes_no_create_body(tmp_path: Path) -> None:
    """An update-only writer has no body to supply; the signature must not accept one."""
    root = _seed(tmp_path)
    with pytest.raises(TypeError):
        update_entity_file(_prop(), project_root=root, ownership=OWNERSHIP,
                           create_body="# nope\n")  # type: ignore[call-arg]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_annotation_writer_containment.py -v
```

Expected: FAIL — `ImportError: cannot import name 'EntityWriteError'`.

- [ ] **Step 3: Implement the three entry points**

Append to `dag/entity_frontmatter.py`:

```python
class EntityWriteError(ValueError):
    """A write was refused because the destination's existence contradicts the operation."""


def _entity_dest(entity: WorkbenchEntity, project_root: Path) -> Path:
    from science_tool.entities import resolve_path_policy

    assert entity.id is not None
    local_part = entity.id.split(":", 1)[1]
    root = resolve_path_policy(entity.kind, project_root=project_root).root
    return project_root / root / f"{local_part}.md"


def _write(dest: Path, text: str) -> Path:
    from science_tool.entities import _atomic_replace_text

    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace_text(dest, text)
    return dest


def _render_update_for(
    entity: WorkbenchEntity, dest: Path, *, ownership: Ownership, updated: str
) -> str:
    # ADMIT FIRST. `read_existing_target` refuses a wrong-identity, undated or unparseable
    # destination. Reading the file directly and defaulting `created` lets `render_update`
    # repair a record into validity before `certify_persisted` ever sees it.
    frontmatter, body, _current = read_existing_target(dest, entity)
    return render_update(
        entity,
        ownership=ownership,
        existing_frontmatter=frontmatter,
        body=body,
        created=str(frontmatter["created"]),
        updated=updated,
    )


def create_entity_file(
    entity: WorkbenchEntity,
    *,
    project_root: Path,
    ownership: Ownership,
    create_body: str,
    as_of: date | None = None,
) -> Path:
    """Write a NEW entity file. Refuses an existing destination."""
    dest = _entity_dest(entity, project_root)
    if dest.exists():
        raise EntityWriteError(f"refusing to create {dest}: it already exists")
    today = (as_of or date.today()).isoformat()
    return _write(dest, render_create(
        entity, ownership=ownership, body=create_body, created=today, updated=today
    ))


def update_entity_file(
    entity: WorkbenchEntity,
    *,
    project_root: Path,
    ownership: Ownership,
    as_of: date | None = None,
) -> Path:
    """Update an EXISTING entity file. Refuses a missing destination.

    Takes no `create_body`: an update-only writer has none to supply, and inventing one to
    satisfy a signature is how a stub body eventually reaches a real record.
    """
    dest = _entity_dest(entity, project_root)
    if not dest.exists():
        raise EntityWriteError(f"refusing to update {dest}: it does not exist")
    today = (as_of or date.today()).isoformat()
    return _write(dest, _render_update_for(entity, dest, ownership=ownership, updated=today))


def upsert_entity_file(
    entity: WorkbenchEntity,
    *,
    project_root: Path,
    ownership: Ownership,
    create_body: str,
    as_of: date | None = None,
) -> Path:
    """Create or update. Used ONLY by the workbench, which legitimately recompiles over rows."""
    dest = _entity_dest(entity, project_root)
    today = (as_of or date.today()).isoformat()
    if dest.exists():
        text = _render_update_for(entity, dest, ownership=ownership, updated=today)
    else:
        text = render_create(
            entity, ownership=ownership, body=create_body, created=today, updated=today
        )
    return _write(dest, text)
```

Add `from datetime import date` to the module imports.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && uv run --frozen pytest tests/test_annotation_writer_containment.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Delegate the workbench's inlined copy**

Replace the body of `workbench._write_entity_file` (`dag/workbench.py:345-385`) — keeping the
function and its docstring, which explain *why* it is an upsert — with:

```python
    from science_tool.dag.entity_frontmatter import upsert_entity_file, workbench_ownership

    upsert_entity_file(
        entity,
        project_root=project_root,
        ownership=workbench_ownership(entity.kind),
        create_body=workbench_entity_body(entity),
        as_of=as_of,
    )
```

This **removes a copy rather than adding an abstraction** (§4.2): leaving the dance inline would
put the admit-then-render ordering in three places.

- [ ] **Step 6: Run the workbench suites**

```bash
cd science && uv run --frozen pytest \
  tests/test_workbench_apply.py tests/test_workbench_writer_containment.py \
  tests/test_workbench_compile_conformance.py tests/test_annotation_writer_containment.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/dag/ science/tests/test_annotation_writer_containment.py
git commit -m "refactor(entity-frontmatter): add create/update/upsert entry points

One entry point per operation a writer actually performs. The workbench's
inlined admit-then-render dance now delegates to the shared upsert, so the
subtle ordering lives in one place instead of three."
```

---

### Task 4: Promotion accrual and the `MintFn` accounting contract

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py:247` (`MintFn`), `:264-288`
  (`_mint_proposition`), `:307-345` (`_mint_numeric`), `:380-383` (`apply_candidates`)
- Modify: `science/src/science_tool/annotation/prose_promote.py:225-227`
- Modify: `science/src/science_tool/annotation/prose_promotion_batch.py:122-125`
- Test: `science/tests/test_annotation_writer_containment.py`

**Interfaces:**
- Consumes: `create_entity_file`, `Ownership` (Tasks 1, 3).
- Produces: `MintOutcome(entity_id: str, created: bool)` frozen dataclass;
  `MintFn = Callable[[PromotionCandidate, list[str], Path, date | None], MintOutcome]`;
  `PROMOTE_PROPOSITION: Ownership`.

**Read §2.4 of the design before starting.** This is the data-loss path the slice exists to
close: `write_entity_file` renders with `exclude_none`, so re-minting an existing claim deletes
`predicate`, `polarity`, `claim_layer`, `reasoning_source` and the curated body. Containment
alone does **not** close it — a contained *update* would still replace `source_refs`, `subject`
and `object`, because the minting writer owns them. Only the create-only + accrual ruling closes
it.

**`MintFn` has three callers**, all of which currently assume a mint created a file. Widening the
return type is what forces every one to be touched.

- [ ] **Step 1: Write the failing regression test (§5.3)**

Append to `science/tests/test_annotation_writer_containment.py`:

```python
def test_reminting_identical_claim_accrues_and_destroys_nothing(tmp_path: Path) -> None:
    """§2.4: the live data-loss path. Fails on `main`.

    The source_refs / subject / object assertions are the ones a naive contained-UPDATE
    implementation would still fail -- they are the point of §4.3, not incidental coverage.
    """
    from science_tool.annotation.promote import PromotionCandidate, apply_candidates

    root = _seed(tmp_path)
    dest = root / "entities" / "propositions" / "a-affects-b.md"
    dest.write_text(
        "---\n"
        "id: proposition:a-affects-b\n"
        "kind: proposition\n"
        "title: A affects B\n"
        "status: active\n"
        "subject: concept:a-refined\n"
        "object: concept:b-refined\n"
        "predicate: affects\n"
        "polarity: positive\n"
        "claim_layer: causal_effect\n"
        "reasoning_source: llm-synth:model-x:proposition-synthesize-v1\n"
        "source_refs:\n"
        "  - paper:earlier\n"
        "created: '2026-07-01'\n"
        "updated: '2026-07-01'\n"
        "---\n"
        "\n"
        "CURATED BODY\n",
        encoding="utf-8",
    )

    report = apply_candidates(
        [_mint_candidate()],
        sidecar_path=_sidecar(root, claim="A affects B"),
        project_root=root,
        paper_ref="paper:new",
        as_of=date(2026, 7, 31),
    )

    text = dest.read_text(encoding="utf-8")
    assert "predicate: affects" in text
    assert "polarity: positive" in text
    assert "claim_layer: causal_effect" in text
    assert "reasoning_source: llm-synth:model-x:proposition-synthesize-v1" in text
    assert "CURATED BODY" in text
    # Provenance ACCRUES; it is not replaced with only the current paper's refs.
    assert "paper:earlier" in text and "paper:new" in text
    # subject/object refinements owned by synthesize survive the promotion's values.
    assert "concept:a-refined" in text and "concept:a\n" not in text
    # Accounting: accrual counts as linked, not minted, and names no written path.
    assert report.minted == 0
    assert report.linked == 1
    assert report.written_paths == []
```

Add the helpers this and the following tests share. The sidecar shape is copied from the working
end-to-end fixture at `science/tests/test_annotation_promote.py:262-290` — do **not** invent a
second one:

```python
def _sidecar(root: Path, *, claim: str = "A affects B") -> Path:
    """A real sidecar with one open statement annotation. `apply_candidates` reads it back
    whenever any candidate produced a backlink, so a stub path will not do."""
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status

    # BARE module import: tests/ has no __init__.py, and pytest puts it on sys.path.
    # `from tests.test_... import` would fail. House convention -- see
    # test_commons_promote_source.py:6 (`from promote_source_fixtures import ...`).
    from test_annotation_promote import _statement_ann

    (root / "papers").mkdir(exist_ok=True)
    md = root / "papers" / "p.source.md"
    md.write_text(f"{claim}.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(
        sp, anno_io.Sidecar(annotations=(_statement_ann("a-1", claim, status=Status.OPEN),))
    )
    return sp


def _mint_candidate():
    """A forced same-slug MINT -- the curator-override shape. `reason` is a required field."""
    from science_tool.annotation.promote import PromotionCandidate

    return PromotionCandidate(
        ref="annotation:papers/p.source#a-1", frag="a-1", claim="A affects B",
        subject="concept:a", object="concept:b", decision="MINT",
        slug="a-affects-b", reason="forced override", kind="proposition",
    )
```

If `_statement_ann` will not import across test modules here, lift it and `_sidecar` into
`science/tests/promote_source_fixtures.py` — that module already exists for shared promotion
fixtures — and import from there in both places.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_annotation_writer_containment.py -k reminting -v
```

Expected: FAIL — `predicate` absent, body replaced by the stub, `report.minted == 1`.

- [ ] **Step 3: Widen `MintFn` and add `PROMOTE_PROPOSITION`**

In `annotation/promote.py`, replace the `MintFn` alias at line 247:

```python
@dataclass(frozen=True)
class MintOutcome:
    """What a mint did. `created` is False when an identical claim already existed and the
    mint accrued provenance onto it instead (§4.3) -- provenance accrual, not a rewrite."""

    entity_id: str
    created: bool


MintFn = Callable[["PromotionCandidate", list[str], Path, "date | None"], MintOutcome]
```

Add, near the other module constants:

```python
# `source_refs` is owned at CREATE only; promote never updates a record (§4.3), so this
# ownership never reaches `render_update`. `created`/`updated` are omitted deliberately --
# both renderers stamp them unconditionally after the allowlist filter.
PROMOTE_PROPOSITION = Ownership(
    frozenset(("id", "kind", "subject", "object", "source_refs")), CREATE_ONLY_KEYS
)
```

with `from science_tool.dag.entity_frontmatter import CREATE_ONLY_KEYS, Ownership, create_entity_file`.

- [ ] **Step 4: Make `_mint_proposition` create-only**

Replace the tail of `_mint_proposition` (`promote.py:271-287`):

```python
    dest = entity_dest(prop_ref, project_root)
    if dest.exists():
        # Never-overwrite guard: a MINT slug colliding with a DIFFERENT-claim proposition
        # (only reachable via an explicit-id override; auto mints are pre-screened) fails loud.
        existing_fm, _ = _parse_markdown_file(dest)
        if normalize_claim(str(existing_fm.get("title") or "")) != normalize_claim(c.claim):
            raise PromotionApplyError(
                f"refusing to overwrite {dest.name}: it holds a different proposition"
            )
        # Same claim from a second source: ACCRUE, exactly as the LINK path does. Rendering it
        # as an update would replace source_refs with only this paper's refs and overwrite the
        # subject/object refinements synthesize owns.
        for ref in source_refs:
            append_entity_source_ref(dest, ref, as_of=as_of)
        return MintOutcome(entity_id=prop_ref, created=False)

    prop = PropositionEntity(
        id=prop_ref, title=c.claim, subject=c.subject, object=c.object,
        source_refs=list(source_refs),
    )
    create_entity_file(
        prop,
        project_root=project_root,
        ownership=PROMOTE_PROPOSITION,
        create_body=_proposition_body(c.claim),
        as_of=as_of,
    )
    return MintOutcome(entity_id=prop_ref, created=True)
```

In `_mint_numeric`, change the final `return reservation.entity_id` to
`return MintOutcome(entity_id=reservation.entity_id, created=True)` — `reserve_entity` plus the
template render have no accrual path.

- [ ] **Step 5: Update all three callers with identical accounting**

`promote.apply_candidates` (`:380-383`):

```python
        if c.decision == "MINT":
            outcome = targets[c.kind].mint(c, [paper_ref, c.ref], project_root, as_of)
            if outcome.created:
                report.written_paths.append(str(entity_dest(outcome.entity_id, project_root)))
                report.minted += 1
            else:
                report.linked += 1
            backlinks[c.frag] = outcome.entity_id
```

`prose_promote.py:225-227`:

```python
        if decision.decision == "MINT":
            outcome = targets[decision.kind].mint(
                decision, [source_ref, decision.ref], project_root, None
            )
            if outcome.created:
                report.written_paths.append(str(entity_dest(outcome.entity_id, project_root)))
                report.minted += 1
            else:
                report.linked += 1
            promoted_to = outcome.entity_id
```

`prose_promotion_batch.py:122-125`:

```python
        if candidate.decision == "MINT":
            outcome = targets[candidate.kind].mint(
                candidate, [row.source_ref, row.artifact_unit_ref], project_root, None
            )
            if outcome.created:
                report.written_paths.append(str(entity_dest(outcome.entity_id, project_root)))
                report.minted += 1
            else:
                report.linked += 1
            promoted_to = outcome.entity_id
```

- [ ] **Step 6: Write the three-caller accounting test (REQUIRED)**

Type-checking forces every caller to *handle* `MintOutcome`; it cannot prove each one **branches
correctly**. Each caller needs its own assertion. Append to
`science/tests/test_annotation_writer_containment.py`:

```python
def _accruing_targets():
    """Targets whose proposition mint always reports accrual, so each caller's non-created
    branch is exercised directly. Independent of whether `decide_all` can produce this state."""
    from science_tool.annotation.promote import MintOutcome, PromotionTarget, build_targets

    real = build_targets()

    def accruing_mint(c, source_refs, project_root, as_of):
        real["proposition"].mint(c, source_refs, project_root, as_of)
        return MintOutcome(entity_id=f"proposition:{c.slug}", created=False)

    return {**real, "proposition": PromotionTarget(
        kind="proposition", slug_addressed=True, mint=accruing_mint
    )}


def _write_existing_identical_claim(root: Path) -> Path:
    """The destination `_mint_candidate()` would mint onto, already holding the SAME claim."""
    dest = root / "entities" / "propositions" / "a-affects-b.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "---\n"
        "id: proposition:a-affects-b\n"
        "kind: proposition\n"
        "title: A affects B\n"
        "status: active\n"
        "source_refs:\n"
        "  - paper:earlier\n"
        "created: '2026-07-01'\n"
        "updated: '2026-07-01'\n"
        "---\n"
        "\n"
        "Existing body.\n",
        encoding="utf-8",
    )
    return dest


def _prose_project_with_existing_claim(tmp_path: Path) -> Path:
    """A prose project whose unit u001 targets a proposition that already exists.

    Built from the existing batch scaffolding rather than a second fixture shape:
    `_persist_artifact` creates the artifact whose unit claims "Basalt flows record the
    cooling history."; `_write_existing_proposition` writes a record holding that same claim.
    """
    from test_prose_promotion_batch import _persist_artifact, _write_existing_proposition

    _persist_artifact(tmp_path)
    _write_existing_proposition(tmp_path)
    return tmp_path


def test_apply_candidates_counts_accrual_as_linked(tmp_path: Path, monkeypatch) -> None:
    from science_tool.annotation import promote

    root = _seed(tmp_path)
    _write_existing_identical_claim(root)
    report = promote.apply_candidates(
        [_mint_candidate()], sidecar_path=_sidecar(root), project_root=root,
        paper_ref="paper:new", as_of=date(2026, 7, 31), targets=_accruing_targets(),
    )
    assert (report.minted, report.linked, report.written_paths) == (0, 1, [])


def test_prose_promote_counts_accrual_as_linked(tmp_path: Path, monkeypatch) -> None:
    from science_tool.annotation.prose_promote import promote_prose_unit

    monkeypatch.setattr(
        "science_tool.annotation.prose_promote.build_targets", _accruing_targets
    )
    root = _prose_project_with_existing_claim(tmp_path)
    report = promote_prose_unit(root, "prose-source:example", "u001", apply=True)
    assert (report.minted, report.linked, report.written_paths) == (0, 1, [])


def test_prose_promotion_batch_counts_accrual_as_linked(tmp_path: Path, monkeypatch) -> None:
    from science_tool.annotation.prose_promotion_batch import (
        apply_prose_promotion_plan,
        plan_prose_promotions,
    )

    monkeypatch.setattr(
        "science_tool.annotation.prose_promotion_batch.build_targets", _accruing_targets
    )
    root = _prose_project_with_existing_claim(tmp_path)
    plan = plan_prose_promotions(root, "example", ["u001"])
    report = apply_prose_promotion_plan(root, plan)
    assert (report.minted, report.linked, report.written_paths) == (0, 1, [])
```

Build `_prose_project_with_existing_claim` from the existing scaffolding in
`science/tests/test_prose_promotion_batch.py` — `_persist_artifact` plus
`_write_existing_proposition` (`:152-166`) already produce exactly this shape. Import and reuse
them rather than duplicating; model the assertion style on
`test_apply_matches_single_unit_promotion_behavior` (`:250`), which already compares batch and
single reports.

- [ ] **Step 7: Write the skeleton-key and LINK-equivalence tests (§5.4, §5.8)**

Append to `science/tests/test_annotation_writer_containment.py`:

```python
SKELETON_KEYS = ("datapackage", "local_path", "accessions", "siblings", "parent_dataset", "license")


def test_minted_proposition_carries_no_skeleton_keys(tmp_path: Path) -> None:
    """§5.4. `render_entity_text` full-dumps the model, which is what wrote `datapackage: ''`
    and `accessions: []` onto 391 evidence lines. Rendering from an allowlist is what stops it.
    """
    from science_tool.annotation.promote import apply_candidates

    root = _seed(tmp_path)
    apply_candidates(
        [_mint_candidate()], sidecar_path=_sidecar(root), project_root=root,
        paper_ref="paper:new", as_of=date(2026, 7, 31),
    )
    frontmatter = (root / "entities" / "propositions" / "a-affects-b.md").read_text(
        encoding="utf-8"
    ).split("---\n")[1]
    for key in SKELETON_KEYS:
        assert f"{key}:" not in frontmatter, f"skeleton key {key} leaked into a minted record"


def test_forced_mint_and_link_leave_the_same_state(tmp_path: Path) -> None:
    """§5.8: one behaviour, two routes to it -- file state AND report.

    Asserting only the file state would let the accounting diverge unnoticed, which is exactly
    the hole the unconditional `report.minted += 1` opened.
    """
    from science_tool.annotation.promote import PromotionCandidate, apply_candidates

    mint_root, link_root = _seed(tmp_path / "mint"), _seed(tmp_path / "link")
    mint_dest = _write_existing_identical_claim(mint_root)
    link_dest = _write_existing_identical_claim(link_root)

    link_candidate = PromotionCandidate(
        ref="annotation:papers/p.source#a-1", frag="a-1", claim="A affects B",
        subject="concept:a", object="concept:b", decision="LINK",
        slug="proposition:a-affects-b", reason="existing claim", kind="proposition",
    )

    mint_report = apply_candidates(
        [_mint_candidate()], sidecar_path=_sidecar(mint_root), project_root=mint_root,
        paper_ref="paper:new", as_of=date(2026, 7, 31),
    )
    link_report = apply_candidates(
        [link_candidate], sidecar_path=_sidecar(link_root), project_root=link_root,
        paper_ref="paper:new", as_of=date(2026, 7, 31),
    )

    assert mint_dest.read_text(encoding="utf-8") == link_dest.read_text(encoding="utf-8")
    assert (mint_report.minted, mint_report.linked) == (link_report.minted, link_report.linked)
    assert mint_report.written_paths == link_report.written_paths
```

`_seed` takes a path that may not exist yet — make sure its `mkdir` uses `parents=True`
(it does) so `tmp_path / "mint"` works.

- [ ] **Step 8: Run the promotion suites**

```bash
cd science && uv run --frozen pytest \
  tests/test_annotation_writer_containment.py tests/test_annotation_promote.py \
  tests/test_promote_numeric_mint.py tests/test_promote_qh_integration.py \
  tests/test_prose_promote.py tests/test_prose_promotion_batch.py -v
```

Expected: PASS. Pre-existing prose and promotion tests that assert `minted == 1` must stay
green — the accrual branch only triggers on an existing identical claim.
`test_promote_numeric_mint.py` and `test_promote_qh_integration.py` cover the `_mint_numeric`
path whose return type changed.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/annotation/ science/tests/test_annotation_writer_containment.py
git commit -m "fix(promote)!: make proposition mint create-only, accrue on identical claim

Re-minting an existing claim rendered the whole model with exclude_none,
silently deleting predicate, polarity, claim_layer, reasoning_source and the
curated body. An identical claim arriving from a second source is provenance
accrual, not a rewrite, so the mint now appends source_refs exactly as LINK
does and touches nothing else.

MintFn returns MintOutcome so all three callers -- apply_candidates,
prose_promote and prose_promotion_batch -- branch on whether a file was
actually created instead of assuming it was."
```

---

### Task 5: Synthesize onto the update-only entry point

**Files:**
- Modify: `science/src/science_tool/annotation/synthesize.py:32` (imports), `:35`
  (`SYNTH_FIELDS` area), `:419-430` (`_write_proposition`)
- Test: `science/tests/test_annotation_writer_containment.py`, `science/tests/test_proposition_synthesize.py`

**Interfaces:**
- Consumes: `update_entity_file`, `Ownership` (Tasks 1, 3).
- Produces: `SYNTHESIZE_PROPOSITION: Ownership`, derived from `SYNTH_FIELDS` in code.

The `PropositionEntity(**merged_fm)` reconstruction **stays** — `render_update` renders owned
keys from a typed entity, so one must be built. What `read_existing_target` replaces is the
`_parse_markdown_file` body read and the absent identity check (§4.3).

- [ ] **Step 1: Write the failing tests (§5.1 and §5.6)**

Append to `science/tests/test_annotation_writer_containment.py`:

```python
def test_synthesize_ownership_is_derived_from_synth_fields() -> None:
    """Derived in code, not retyped: a hand-copied five-element tuple silently diverges the
    first time a field is added."""
    from science_tool.annotation.synthesize import SYNTH_FIELDS, SYNTHESIZE_PROPOSITION

    assert SYNTHESIZE_PROPOSITION.owned == set(SYNTH_FIELDS) | {"reasoning_source"}
    # An update-only writer claims no create-only keys.
    assert SYNTHESIZE_PROPOSITION.create_only == frozenset()


def test_synthesize_refuses_pre_containment_record(tmp_path: Path) -> None:
    """§5.6 + §6: a REJECTION, not a backfill. This slice repairs no existing records."""
    from science_tool.dag.entity_frontmatter import PersistedShapeError
    from science_tool.annotation.synthesize import SYNTHESIZE_PROPOSITION, _write_proposition

    root = _seed(tmp_path)
    dest = root / "entities" / "propositions" / "legacy.md"
    dest.write_text(
        "---\n"
        "id: proposition:legacy\n"
        "kind: proposition\n"
        "title: ''\n"                      # the 697-record defect
        "status: active\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "---\n"
        "\n"
        "Body.\n",
        encoding="utf-8",
    )
    merged = {"id": "proposition:legacy", "kind": "proposition", "title": "",
              "predicate": "affects", "reasoning_source": "llm-synth:m:proposition-synthesize-v1"}

    # PropositionEntity.title is `str = ""`, so the entity CONSTRUCTS fine and the refusal
    # comes from certify_persisted -- not from pydantic.
    with pytest.raises(PersistedShapeError, match="legacy"):
        _write_proposition("proposition:legacy", merged, root, date(2026, 7, 31))
    assert "title: ''" in dest.read_text(encoding="utf-8")   # untouched
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_annotation_writer_containment.py -k synthesize -v
```

Expected: FAIL — `ImportError: cannot import name 'SYNTHESIZE_PROPOSITION'`.

- [ ] **Step 3: Implement**

In `annotation/synthesize.py`, replace the `write_entity_file` import at line 32:

```python
from science_tool.dag.entity_frontmatter import Ownership, update_entity_file
```

(drop `_parse_markdown_file` too if nothing else in the module uses it — check with
`grep -n "_parse_markdown_file" src/science_tool/annotation/synthesize.py`.)

Immediately after `SYNTH_FIELDS` (line 35):

```python
# DERIVED from SYNTH_FIELDS, never retyped. `create_only` is empty: synthesize only updates.
SYNTHESIZE_PROPOSITION = Ownership(frozenset(SYNTH_FIELDS) | {"reasoning_source"})
```

Replace `_write_proposition`:

```python
def _write_proposition(
    prop_ref: str, merged_fm: dict[str, Any], project_root: Path, as_of: date | None
) -> None:
    """Contained frontmatter update: only synthesis-owned keys are overwritten.

    The typed reconstruction stays -- `render_update` renders owned keys from an entity. The
    body and the identity check now come from `read_existing_target` inside
    `update_entity_file`, so there is exactly one reader of this file's frontmatter.
    """
    prop = PropositionEntity(**merged_fm)          # re-runs interlock validator
    update_entity_file(
        prop,
        project_root=project_root,
        ownership=SYNTHESIZE_PROPOSITION,
        as_of=as_of,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run --frozen pytest \
  tests/test_annotation_writer_containment.py tests/test_proposition_synthesize.py -v
```

Expected: the two new tests PASS. **Some `test_proposition_synthesize.py` tests may now fail**
because their fixtures were built by `write_entity_file` — that is Task 6's `_write_prop` move.
If so, note which and proceed; do not weaken an assertion to make them pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/synthesize.py science/tests/test_annotation_writer_containment.py
git commit -m "fix(synthesize): write propositions through the contained update path

Only the synthesis-owned keys are overwritten now; title, source_refs and the
curated body survive. A record predating containment is REJECTED with
PersistedShapeError rather than silently backfilled."
```

---

### Task 6: Delete `write_entity_file` and guard its retirement

**Files:**
- Modify: `science/src/science_tool/entities.py:477-...` (delete `write_entity_file`)
- Modify: `science/tests/test_proposition_synthesize.py:283-286` (`_write_prop`)
- Modify: `science/tests/test_entity_writer.py:35` (delete one test)
- Modify: `science/tests/test_workbench_apply.py:59` (delete one test)
- Test: `science/tests/test_write_entity_file_retired_guard.py` (create)

**Interfaces:**
- Consumes: `create_entity_file` (Task 3).
- Produces: nothing. `entities.write_entity_file` no longer exists.

**What the guard claims, and what it does not.** It proves this one symbol stayed retired. It
does **not** prove the full-model dump stayed gone — a writer reintroduced under another name, or
an inlined `model_dump(exclude_none=True)` at a call site, passes it cleanly. The behavioural
protection comes from the containment tests (§5.3, §5.4). Do not describe the guard as covering
their half (§4.4).

- [ ] **Step 1: Write the guard**

Create `science/tests/test_write_entity_file_retired_guard.py`:

```python
"""Guard: `write_entity_file` stays retired (design 2026-07-31, §4.4).

Scope is a TREE WALK with no allowlist -- a guard that enumerates its own scope has a hole
by construction, and this programme has already been bitten by one.

This guard proves one symbol stayed gone. It does NOT prove the full-model dump stayed gone:
a writer reintroduced under another name passes it. That half belongs to the containment
tests in test_annotation_writer_containment.py.
"""
from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"


def test_write_entity_file_appears_nowhere_in_src() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{n}"
        for path in sorted(SRC.rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "write_entity_file" in line
    ]
    assert offenders == [], (
        "`write_entity_file` was retired by the annotation-writer-containment slice; "
        "route the write through dag.entity_frontmatter's create/update/upsert entry points "
        f"instead. Found: {offenders}"
    )


def test_symbol_is_absent_from_the_entities_module() -> None:
    import science_tool.entities as entities

    assert not hasattr(entities, "write_entity_file")
```

Note the substring check also catches `_write_entity_file` in `dag/workbench.py` — that private
method is a *different* symbol that legitimately survives. Scope the predicate to exclude a
leading underscore:

```python
        if re.search(r"(?<!_)\bwrite_entity_file\b", line)
```

with `import re`. Verify by mutation in Step 5 that this still catches the real thing.

- [ ] **Step 2: Run the guard to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_write_entity_file_retired_guard.py -v
```

Expected: FAIL — offenders lists `entities.py` (the definition) and nothing else, since Tasks 4
and 5 removed the two production callers.

- [ ] **Step 3: Delete the function and fix the test references**

Delete `write_entity_file` from `science/src/science_tool/entities.py` (starting at line 477).
Then:

- **Move the fixture.** In `tests/test_proposition_synthesize.py`, rewrite `_write_prop`
  (`:283-286`) onto the contained path:

  ```python
  def _write_prop(root: Path, slug: str, *, title: str, body: str = "# t\n\n## Claim\n\nKEEP-ME\n",
                  **fields) -> str:
      from science_tool.annotation.promote import PROMOTE_PROPOSITION
      from science_tool.dag.entity_frontmatter import create_entity_file

      ref = f"proposition:{slug}"
      create_entity_file(
          PropositionEntity(id=ref, title=title, **fields),
          project_root=root,
          ownership=PROMOTE_PROPOSITION,
          create_body=body,
      )
      return ref
  ```

  This is not cosmetic: the full-model dump seeds skeleton keys that `render_update` preserves
  (they are not owned) and `certify_persisted` does not reject (base 2.0 deliberately omits
  `unevaluatedProperties`). Left alone, the suite would certify containment against inputs only
  the uncontained writer could produce.

  `_write_prop` is called with `**fields` that may include keys `PROMOTE_PROPOSITION` does not
  own (e.g. `predicate`). If a caller needs such a key persisted, widen that *call site* to
  write the frontmatter directly — do **not** widen `PROMOTE_PROPOSITION`, which is promote's
  real ownership and is asserted in Task 4.

- **Delete two tests** whose subject is the deleted writer:
  - `tests/test_entity_writer.py::test_write_entity_file_places_custom_body` (`:35`). Delete the
    **test only** — the other eleven in that module cover `slug_*`, `append_entity_source_ref`
    and `render_entity_*`, all of which survive. Remove `write_entity_file` from the module's
    import block at `:7`.
  - `tests/test_workbench_apply.py::test_render_entity_text_matches_write_entity_file_output`
    (`:59`). Remove `write_entity_file` from its import at `:24`.

- [ ] **Step 4: Run the guard and the affected suites**

```bash
cd science && uv run --frozen pytest \
  tests/test_write_entity_file_retired_guard.py tests/test_entity_writer.py \
  tests/test_workbench_apply.py tests/test_proposition_synthesize.py \
  tests/test_annotation_writer_containment.py -v
```

Expected: PASS.

- [ ] **Step 5: Certify the guard by mutation (§5.5)**

A guard that has never failed is an assertion, not a check. Run both mutations and confirm RED
each time, then revert:

```bash
cd science
# (a) re-introduce the definition
printf '\n\ndef write_entity_file():\n    pass\n' >> src/science_tool/entities.py
uv run --frozen pytest tests/test_write_entity_file_retired_guard.py -v   # expect FAIL (both tests)
git checkout src/science_tool/entities.py

# (b) re-introduce a caller
printf '\n# write_entity_file(prop)\n' >> src/science_tool/annotation/promote.py
uv run --frozen pytest tests/test_write_entity_file_retired_guard.py -v   # expect FAIL (tree walk)
git checkout src/science_tool/annotation/promote.py
```

Confirm mutation (a) fails **both** tests and (b) fails the tree walk. If (b) passes, the
underscore-exclusion regex is too narrow — fix it and re-run.

- [ ] **Step 6: Commit**

```bash
git add science/src/ science/tests/
git commit -m "refactor(entities)!: delete write_entity_file, guard its retirement

Zero production callers remain: the workbench uses the contained renderers and
the two annotation writers now do too. question/hypothesis promotion never used
it -- _mint_numeric renders through the template path -- so no kind needs a
general full-model dump. That dump IS the defect this slice closed.

The guard is a tree walk with no allowlist. It proves this symbol stayed
retired; the containment tests prove the dump stayed gone."
```

---

### Task 7: Full validation

**Files:** none — verification only.

- [ ] **Step 1: Confirm the branch**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/proposition-corpus-remediation
git branch --show-current   # must print: annotation-writer-containment
git status --short           # must be clean
```

- [ ] **Step 2: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
cd ../science/model && uv run ruff check
```

Expected: clean. Pyright is configured once by the repo-root `pyrightconfig.json` and covers all
three source trees regardless of which package you run from.

- [ ] **Step 3: Full default suite** (~10 min — needs the explicit timeout)

```bash
cd science && uv run --frozen pytest
```

Run this with a `timeout` of at least `900000` ms. Do not run two suites concurrently in this
worktree — they race on shared test-output paths.

- [ ] **Step 4: Model suite**

```bash
cd science/model && uv run --frozen pytest
```

- [ ] **Step 5: Confirm the accepted costs held (§6)**

The design predicts **zero** blast radius absent an explicit curator override: all 307 legacy mm30
propositions already have all five `SYNTH_FIELDS` set, so `plan_writes` produces no writes and
`synthesize` skips them. Verify the prediction rather than assuming it:

```bash
cd science && uv run --frozen pytest -m real_projects
```

Expected: the **three known pre-existing failures** and no others. Reproduce any additional
failure at the merge-base (`0c7a6ba6`) before attributing it to this branch.

- [ ] **Step 6: Confirm the 697 records were not touched**

```bash
cd ~/d/r/mm30 && git status --short entities/
```

Expected: **empty**. This slice repairs no records (§6); any modification here is a bug.

---

## Notes for the implementer

**The three follow-ups this slice does not close** (§7) — do not opportunistically fix them:

1. The corpus migration (697 records, two populations with different repair physics).
2. The legacy triple's three live consumers, which need three separate verdicts.
3. mm30's DAG validation is red with 670 error-severity findings (362
   `proposition_edge_missing`, 307 `legacy_dag_edge_unresolved`, 1 `acyclicity`). Surfaced by
   this design, owned by neither it nor this plan.

One in-scope doc fix, if you want it in Task 6: `compile_workbench`'s docstring still says
entities are "(re)written via the canonical entity-layer writer", which stopped being true when
piece 1 landed and is now actively wrong.

**When measuring anything in a Science project**, exclude `.worktrees` as well as `.git` —
projects carry nested checkouts of themselves and a bare `find` multiplies every count. Prefer
the code path's own discovery function over an ad-hoc scan.
