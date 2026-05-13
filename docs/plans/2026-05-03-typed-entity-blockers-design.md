# Typed Entity Blockers Design & Implementation Plan

> **Status:** Implemented on branch `feature/typed-entity-blockers` (commit range `d1b33ec..accef7e`).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The design portion is informational context; the Implementation Plan section at the bottom is the executable work.

**Goal.** Make `Task.blocked_by` accept typed entity references (`<kind>:<local-id>`), validate them, and surface readiness state derived from the blocker entity itself. Single source of truth for "is this blocker satisfied yet?" lives on the blocker entity, not on the task.

**Motivating case.** A task in `cancer/mechanisms/evolution/tasks/active.md` is blocked because three datasets aren't usable yet — one is unpublished pre-print data, two are dbGaP-controlled and not yet retrieved. Today the task system can only express "blocked by some opaque string"; the goal is to express "blocked by `dataset:lee2026-gbm0510-scwgs` (embargoed), `dataset:shahcompbio-hlamp` (controlled, unverified), `dataset:zhang2024-ecdna-cohort` (controlled, unverified)" — with the access state read from each dataset entity rather than copied onto the task.

---

## Architecture

### The `Readiness` protocol

Two pieces: an entity-local `readiness()` method (handles self-determining cases), and a thin `ReadinessResolver` in the tool layer (handles cross-entity lookup and cycle guarding for derived cases).

```python
# science-model

class Readiness(BaseModel):
    ready: bool
    state: str        # short, display-ready: "done" | "embargoed" | "controlled, unverified" | …
    detail: str = ""  # optional one-line elaboration for `tasks show`


class ReadinessResolverProtocol(Protocol):
    def resolve_ref(self, ref: str) -> Readiness:
        ...


class ProjectEntity(Entity):
    # … existing fields …

    def readiness(self, resolver: ReadinessResolverProtocol | None = None) -> Readiness:
        """Default readiness: ready iff status == 'done'.

        `resolver` is optional; subclasses that need to traverse other
        entities (e.g. derived datasets → producing workflow-run) require
        it and must degrade gracefully when it's missing.
        """
        if self.status == "done":
            return Readiness(ready=True, state="done")
        return Readiness(ready=False, state=self.status or "unknown")
```

```python
# science: tasks_readiness.py

class ReadinessResolver:
    """Looks up entities by id and tracks the visited set for cycle protection.

    Constructed per CLI invocation with a snapshot of the local entity store;
    not shared across invocations. Caches resolved readiness within its own
    lifetime so the same blocker referenced N times costs one resolution.
    """

    def __init__(self, lookup: Callable[[str], ProjectEntity | None]):
        self._lookup = lookup
        self._visiting: set[str] = set()
        self._cache: dict[str, Readiness] = {}

    def resolve_ref(self, ref: str) -> Readiness:
        if ref in self._cache:
            return self._cache[ref]
        if ref in self._visiting:
            return Readiness(ready=False, state="cycle", detail=f"derivation cycle through {ref}")
        entity = self._lookup(ref)
        if entity is None:
            return Readiness(ready=False, state="unresolved", detail=f"unknown entity {ref}")
        self._visiting.add(ref)
        try:
            result = entity.readiness(resolver=self)
        finally:
            self._visiting.discard(ref)
        self._cache[ref] = result
        return result
```

Overrides:

- **`DatasetEntity.readiness(resolver=None)`** branches on `origin`:
  - `origin == "external"`: self-contained, derives from `access` (`AccessBlock`):
    - `availability == "withdrawn"` → `ready=False, state="withdrawn"`.
    - `availability == "embargoed"` → `ready=False, state="embargoed"`, `detail` includes `available_after` if set.
    - `availability == "available"` and `access.exception.mode != ""` (Branch-B decision recorded):
      - `mode == "expanded-to-acquire"` → `ready=False, state="acquiring"`, `detail` from `exception.rationale`. Decision is "in progress."
      - `mode in {"scope-reduced", "substituted"}` → `ready=True, state=f"consumable-via-{mode}"`, `detail` from `exception.rationale`. Decision is "consumable despite verification gap."
    - `availability == "available"`, no exception, `verified == True` → `ready=True, state="available"`.
    - `availability == "available"`, no exception, `verified == False` → `ready=False, state=f"{level}, unverified"`.
  - `origin == "derived"`: requires `resolver`. If `resolver is None`, returns `Readiness(ready=False, state="unknown", detail="derived dataset readiness requires resolver context")`. Otherwise looks up `self.derivation.workflow_run` via the resolver and returns whatever the workflow-run reports.
- **`WorkflowRunEntity.readiness(resolver=None)`** — `ready=True, state="complete"` iff `self.status == "complete"` (matches the existing workflow-run template's vocabulary). Otherwise `ready=False, state=self.status or "unknown"`.
- All other project entities use the default. Domain/catalog entities are not valid task blockers in this spec.

Each entity that wants non-default readiness overrides the method directly. The resolver is the only piece that's generalizable infrastructure.

### Dataset availability extension

`AccessBlock` (in `science-model/src/science_model/packages/schema.py`) gets two new fields:

```python
class AccessBlock(BaseModel):
    level: Literal["public", "registration", "controlled", "commercial", "mixed"]
    availability: Literal["available", "embargoed", "withdrawn"] = "available"
    available_after: str = ""   # free-form availability window; only meaningful when availability == "embargoed". ISO date when known; otherwise free-form ("2026-Q3", "after Lee2026 publication", "TBD").
    verified: bool
    # … existing fields unchanged
```

**Rationale.** Availability is orthogonal to access level. A pre-publication dataset is `availability=embargoed, level=<anticipated>`. A retracted dataset is `availability=withdrawn`. Default value `"available"` keeps existing dataset entities valid without migration.

**Validator.** `available_after` set with `availability != "embargoed"` is rejected.

### Storage model

`Task.blocked_by` stays `list[str]`. **No schema change.** The strings are always typed entity references (`<kind>:<local-id>`); untyped strings are rejected at write time but tolerated at read time (warning).

`tasks/active.md` serialization is unchanged: `- blocked-by: [task:t007, dataset:lee2026-gbm0510-scwgs]`.

### Scope: single-project only

This spec is **single-project**. A task can be blocked by entities in the same project; it cannot be blocked by entities in a sibling/parent/child project.

Rationale: cross-project resolution is explicitly deferred per `docs/federation.md:99`. The current `_audit_reference` path (`science/src/science_tool/graph/migrate.py:316`) is called without `allow_cross_project_address`, and the resolver (`science/src/science_tool/graph/reference_resolution.py:30`) only knows aliases for loaded local entities. Designing cross-project blockers properly requires settling the cross-project address syntax, the resolver source (live entity-store sweep vs. federated graph snapshot), stale-graph behavior, and audit semantics — all of which belong to the federation workstream rather than this spec.

Cross-project blockers move to the trajectory section, conditional on cross-project entity resolution landing first.

---

## CLI & Display Surface

### Block command

`science tasks block <task_id> --by <typed-ref>`:

- **Strict typing.** Rejects untyped strings: `--by some-string` → error `"blocker must be typed: <kind>:<local-id> (e.g. dataset:foo, task:t007)"`.
- **Strict resolution.** Validates the ref resolves to a known project entity in the local project (cross-project refs and domain/catalog entities are out of scope; see trajectory item 1). If not: error with create-stub hint: `"unknown entity dataset:foo. Create the entity first (for datasets, add doc/datasets/foo.md or use the appropriate dataset workflow)."`
- **Repeatable.** `--by` accepts multiple values in one invocation: `tasks block t002 --by dataset:a --by dataset:b --by dataset:c`. (Current single-blocker form is a regression vs. the underlying data model, which has always supported a list.)
- **`--force` escape hatch.** Records the blocker even if the entity doesn't yet exist. Emits a warning; `graph audit` will flag the unresolved reference. Used for the legitimate case of "I know I'll need this dataset but haven't created the entity yet."

### Add / edit commands

`tasks add` and `tasks edit` already accept `--blocked-by` (multiple). Same validation rules apply: typed refs only, must resolve, `--force` to bypass.

### Display

**`tasks list`** stays compact. When a task is `blocked`, append a brief blocker count and worst-state summary on a continuation line:

```
[t002] P1 blocked  Quantify ecDNA selection coefficients
        blocked-by: 3 (1 embargoed, 2 controlled-unverified)
```

**`tasks show t002`** expands per-blocker:

```
blocked-by:
  - dataset:lee2026-gbm0510-scwgs    embargoed (available_after: 2026-Q3, dbGaP)
  - dataset:shahcompbio-hlamp        controlled, unverified
  - dataset:zhang2024-ecdna-cohort   controlled, unverified
```

The display layer calls `entity.readiness()` for each blocker; `state` populates the inline label, `detail` populates the parenthetical. Unresolved refs render as `<unresolved>` with a warning row.

### Auto-status semantics

`tasks block` continues to set `status: blocked`. **`tasks unblock` is unchanged for now** — it clears `blocked_by` and sets `status: active`. This spec does **not** add auto-unblock-on-readiness.

But: `tasks list` and `tasks show` compute and display **derived readiness** even when stored status is `blocked`. So if all blockers become ready, the task displays:

```
[t002] P1 blocked  Quantify ecDNA selection coefficients
        blocked-by: 3 (all ready — run 'tasks unblock t002')
```

This is a nudge, not enforcement; it gives the auto-unblock value without committing to the implementation.

### New introspection command

`science tasks blockers <task_id>`:

- Default: prints per-blocker readiness as a table.
- `--format=json`: machine-readable output, **always includes per-blocker readiness** (`ref`, `ready`, `state`, `detail`, `unresolved` flag). Useful for scripting and for the future auto-unblock sweep.

`science tasks list --format=json` likewise includes a `blocked_by_readiness` array per blocked task inside each row in the existing `{"rows": [...], "meta": {...}}` payload, so scripted callers don't have to issue per-task follow-up calls.

### Legacy migration command

`science tasks fix-blockers`:

- Interactive sweep of all tasks with stored untyped blockers.
- For each, prompts the user to either retype (e.g., `cleanup-old-data` → `task:t017`) or `--force`-keep with a note.

---

## Validation Rules & Service Boundary

### Helper

A single task-layer helper owns ref validation; CLI `block`/`add`/`edit` all route through it:

```python
# science/src/science_tool/tasks_blockers.py

def validate_blocker_refs(
    project_root: Path,
    refs: list[str],
    *,
    force: bool = False,
) -> list[str]:
    """Validate and normalize a list of blocker refs.

    - Rejects refs not matching `^<kind>:<local-id>$` (always; --force does not bypass format).
    - Rejects refs that don't resolve to a known local entity, unless `force=True`.
    - Returns the (possibly normalized) ref list on success.
    - Raises `BlockerValidationError` with a concrete actionable message on failure.
    """
```

### Updated function signatures

`block_task`, `edit_task`, and `add_task` (in `science/src/science_tool/tasks.py`) gain a `project_root: Path` parameter so they can call `validate_blocker_refs`. The CLI commands already have `project_root` available as `Path.cwd()` in the current task command group; threading it down is a small change.

### Read path

`parse_tasks(path)` stays clean: it does not emit warnings, so programmatic callers (graph build, archive, tests, library users) get pure parse semantics. A separate `parse_tasks_for_cli(path) -> tuple[list[Task], list[Warning]]` wrapper detects legacy untyped blockers and returns warnings alongside the tasks; only the user-facing CLI commands (`tasks list`, `tasks show`, etc.) call this wrapper.

### Rules table

| Where | Rule | On violation |
|---|---|---|
| `validate_blocker_refs` (called by `block` / `add --blocked-by` / `edit --blocked-by`) | Ref must match `^<kind>:<local-id>$` | Reject with format hint; `--force` does **not** bypass |
| Same | Ref must resolve to a known local entity | Reject with create-stub hint; `--force` bypasses (writes ref, warns) |
| `parse_tasks_for_cli` (CLI read wrapper) | Untyped legacy string in stored `blocked_by` | Warn, continue |
| `parse_tasks` (programmatic) | (no warnings; library callers are responsible for their own checks) | — |
| `graph audit` | Unresolved typed ref | Existing audit row; no new code |
| `AccessBlock` validator | `available_after` set but `availability != "embargoed"` | Pydantic validation error |

---

## Migration

**Schema.** `AccessBlock.availability` defaults to `"available"`; existing dataset entities continue to validate without edits.

**Data.** No automatic rewrite of existing `tasks/active.md` files. Read-path warnings surface legacy untyped blockers; `science tasks fix-blockers` provides an interactive retype flow.

---

## Testing Strategy

Three layers, in TDD execution order.

### 1. `science-model` unit tests (`tests/test_readiness.py`)

- Default `ProjectEntity.readiness()` for each `status` value (proposed, active, blocked, deferred, done, retired).
- `DatasetEntity.readiness()` branches (no resolver needed for external):
  - `origin=external`, `availability=available`, `verified=true` → ready.
  - `origin=external`, `availability=available`, `verified=false`, no exception → not ready, state from level.
  - `origin=external`, `availability=available`, `exception.mode="scope-reduced"` → ready, state `consumable-via-scope-reduced`.
  - `origin=external`, `availability=available`, `exception.mode="substituted"` → ready, state `consumable-via-substituted`.
  - `origin=external`, `availability=available`, `exception.mode="expanded-to-acquire"` → not ready, state `acquiring`.
  - `origin=external`, `availability=embargoed`, with and without `available_after`.
  - `origin=external`, `availability=withdrawn`.
  - `origin=derived` without resolver → not ready, state `unknown`.
- `WorkflowRunEntity.readiness()`: ready iff `status == "complete"`; otherwise echoes status.
- `AccessBlock` validator rejects `available_after` set without `availability=embargoed`.

### 2. `science` task layer + resolver tests (`tests/test_tasks_blockers.py`, `tests/test_readiness_resolver.py`)

- `validate_blocker_refs` rejects untyped string (always; `--force` does not bypass).
- `validate_blocker_refs` rejects unknown typed ref; `force=True` returns the ref with no error.
- Repeatable `--by` accumulates blockers; `block_task` integration test.
- `parse_tasks` does **not** emit warnings for legacy untyped blockers (clean parse).
- `parse_tasks_for_cli` returns warnings for legacy untyped blockers.
- `ReadinessResolver`:
  - Returns `unresolved` for unknown refs.
  - Returns `cycle` when a derivation chain loops back.
  - Caches: same ref resolved twice does one underlying lookup.
  - Derived dataset → workflow-run delegation works.

### 3. CLI / display tests (`tests/test_tasks_cli.py`, `tests/test_tasks_display.py`)

- `tasks list` emits the blocker-count summary line.
- `tasks show` renders per-blocker readiness with state + detail.
- "All blockers now ready" nudge appears when applicable.
- `tasks blockers <id> --format=json` shape.
- `tasks fix-blockers` interactive flow (Click testing runner).

### End-to-end smoke

In a tmp project with one task and one embargoed dataset: `block` → `show` → flip dataset to `availability=available, verified=true` → `show` → confirm the nudge appears.

---

## File Touch List

| File | Change |
|---|---|
| `science-model/src/science_model/entities.py` | Add `Readiness` model; default `readiness(resolver=None)` on `ProjectEntity`; overrides on `DatasetEntity` and `WorkflowRunEntity` |
| `science-model/src/science_model/packages/schema.py` | Extend `AccessBlock` with `availability` + `available_after` + validator |
| `science-model/tests/test_readiness.py` | New |
| `science/src/science_tool/tasks.py` | Thread `project_root` into `block_task` / `edit_task` / `add_task`; route blocker writes through `validate_blocker_refs`; add `parse_tasks_for_cli` wrapper. `parse_tasks` itself stays clean |
| `science/src/science_tool/tasks_blockers.py` | New: `validate_blocker_refs`, `BlockerValidationError` |
| `science/src/science_tool/tasks_readiness.py` | New: `ReadinessResolver` |
| `science/src/science_tool/entities.py` | Add `load_local_entity_ids()` and `load_local_entity_index()` helpers backed by `load_project_sources()` and filtered to `ProjectEntity` |
| `science/src/science_tool/cli.py` | Repeatable `--by`, `--force`; new `tasks blockers` and `tasks fix-blockers` commands; CLI commands call `parse_tasks_for_cli` |
| `science/src/science_tool/tasks_display.py` | Construct `ReadinessResolver`, resolve and render readiness, add nudge |
| `science/tests/test_tasks_blockers.py` | New |
| `science/tests/test_readiness_resolver.py` | New |
| `science/tests/test_tasks_cli.py` | Extend |
| `science/tests/test_tasks_display.py` | Extend |
| `commands/tasks.md` | Document typed-ref convention; mention `--force` and `fix-blockers` |
| active tasks skill, if present (find with `rg -l "Manage the project task queue" skills .codex 2>/dev/null`) | Same |
| `templates/dataset.md` (if it exists) | Add `availability` field with default and HTML hint |

---

## Out of Scope (Trajectory)

These are named so the future direction is documented. **None are built in this spec.**

1. **Cross-project blockers.** A task in project A blocked by an entity in project B (sibling/parent/child). Requires settling: the cross-project address syntax, the resolver source (live entity-store sweep across federated peers vs. federated graph snapshot), stale-graph behavior, and audit semantics. Belongs to the federation workstream; lands when cross-project entity resolution lands. The single-project blocker design here generalizes naturally — `validate_blocker_refs` and `ReadinessResolver` both grow a project-scope parameter.
2. **Auto-unblock sweep.** A command that flips `status: blocked → active` for tasks whose blockers all report `ready`. Defer until manual workflow validates the readiness signal — premature automation here risks confusing flicker behavior.
3. **Generalized graph operations primitives** — subgraph extraction, fold/aggregate over a subgraph, registered per-entity properties. Extract when a second concrete consumer (uncertainty diffusion, dependency-graph planning, knowledge-gap detection) appears, not before.
4. **Graph substrate unification** — single conceptual schema with project-local lazy materialization plus explicit federated build. Significant design surface (especially the strict-vs-tolerant materialization-failure question). Justified when consumers beyond blockers (inquiries, knowledge-gap detection, uncertainty diffusion) accumulate.
5. **Typed cross-project edge vocabulary** — `depends-on`, `cites-as-context`, `conditions-on`, `boundary-condition`, `ambient-influence`. Blockers are the first concrete `depends-on` instance; the broader vocabulary lands when a second intent class needs to be expressed.
6. **Federation-status discovery tooling** — `science federation status` showing parent/peer updates relative to local state.
7. **Lateral `peers:` topology** for DAG-of-projects shapes (cancer ↔ circadian ↔ immune). Today's `parent` / `children` is tree-shaped; an additive `peers:` arrives when cross-cutting projects exist in your portfolio.
8. **`Readiness.detail` enrichment beyond datasets.** Workflow-runs surfacing "failed at step X"; tasks surfacing "in-progress, last touched N days ago". Add as needs arise.

---

## Risks

- **Strict validation is breaking.** Existing projects with untyped blockers see CLI warnings on read, errors on next write. Mitigation: warnings live in the CLI wrapper (not the parser), so library callers stay clean; `tasks fix-blockers` interactive command for migration.
- **Embargoed datasets with no `available_after` give vague readiness.** Acceptable — `embargoed` alone is informative; `available_after` is a nice-to-have when known.
- **Generalizing `Readiness` beyond `ProjectEntity` later.** If a non-project entity needs readiness, it gets its own implementation. Acceptable — none today.
- **Derived-dataset readiness recursion.** A derived dataset delegates to its producing workflow-run, which could in principle delegate further. The `ReadinessResolver` owns the visited-set and returns a `cycle` readiness when a loop is detected. Cycles in derivation chains are themselves a data error, but readiness resolution must not infinite-loop.
- **Per-`tasks list` readiness cost.** Every `tasks list` invocation resolves every blocker on every blocked task to compute the summary line and the all-ready nudge. Reads are local markdown frontmatter, so cheap in absolute terms, but scales linearly with `(blocked tasks × avg blockers per task)`. Mitigation: `ReadinessResolver` caches per-invocation, so the same dataset referenced by N tasks costs one resolution.
- **`AccessException` semantics drift.** The dataset readiness rule pins specific behavior to `exception.mode` values (`scope-reduced` and `substituted` → ready; `expanded-to-acquire` → not ready; empty → fall through). If new modes are added later, dataset readiness must be updated explicitly (no fall-through default for unknown modes — treat as not-ready with a warning).

---

## Self-Review

- **Placeholders.** None. All sections describe concrete behavior; no TBD or TODO markers.
- **Internal consistency.** `Readiness` shape (`bool + state + detail`) consistent across entity overrides, `ReadinessResolver`, CLI display, `tasks blockers --format=json`, and `tasks list --format=json`. `tasks list --format=json` preserves the existing `{"rows": [...], "meta": {...}}` envelope and adds `blocked_by_readiness` inside rows. `AccessBlock.availability` and `exception.mode` semantics match across the entity validator, dataset readiness override, display strings, and tests. `ReadinessResolver` is the single owner of cross-entity lookup, cycle protection, and per-invocation caching.
- **Scope.** Single-project, single-spec scope: data-model extension + readiness protocol/resolver + validation helper + CLI/display surface. Cross-project blockers, auto-unblock, and graph-substrate work are explicitly deferred. Sized for one implementation plan.
- **Service boundary.** `validate_blocker_refs` is the single owner of ref validation; `block_task` / `edit_task` / `add_task` route through it. `ReadinessResolver` is the single owner of readiness resolution; entity `readiness()` methods are pure local logic plus optional resolver delegation. `load_local_entity_ids()` and `load_local_entity_index()` are the single local project-entity lookup helpers for validation and display. `parse_tasks` stays pure; `parse_tasks_for_cli` is the warning-surfacing wrapper.
- **Workflow-run rule.** Pinned to `status == "complete"` (matches the existing template vocabulary). No deferral.
- **Cross-project blockers.** Explicitly out of scope; promoted to trajectory item 1 with prerequisites named.

---

# Implementation Plan

**Tech Stack:** Python 3.11+, Pydantic v2, Click, pytest. Workspace uses `uv`. Tests run with `uv run --frozen pytest <path> -q`.

**Worktree:** Implementation should run in an isolated git worktree. If not already in one, create it with `superpowers:using-git-worktrees`.

**Commit cadence:** One commit per task (after the test passes). Conventional-commit prefixes (`feat`, `fix`, `docs`, `test`, `chore`, `refactor`) — see `git log --oneline -20` for the project style.

**TDD discipline:** Each task writes the failing test first, runs it to confirm failure, implements, runs to confirm success, then commits. Do not skip the failing-run step — it catches typos and import-path mistakes before they hide bugs.

---

## Task 1: Extend `AccessBlock` with `availability` and `available_after`

**Files:**
- Modify: `science-model/src/science_model/packages/schema.py` — `AccessBlock`
- Modify: `science-model/tests/test_packages.py` — add availability cases

- [ ] **Step 1: Write the failing tests**

Add to `science-model/tests/test_packages.py`:

```python
import pytest
from pydantic import ValidationError

from science_model.packages.schema import AccessBlock


def test_access_block_availability_default_is_available():
    block = AccessBlock(level="public", verified=True)
    assert block.availability == "available"
    assert block.available_after == ""


def test_access_block_embargoed_with_window():
    block = AccessBlock(
        level="controlled",
        verified=False,
        availability="embargoed",
        available_after="2026-Q3",
    )
    assert block.availability == "embargoed"
    assert block.available_after == "2026-Q3"


def test_access_block_embargoed_without_window_is_valid():
    block = AccessBlock(level="controlled", verified=False, availability="embargoed")
    assert block.availability == "embargoed"
    assert block.available_after == ""


def test_access_block_withdrawn():
    block = AccessBlock(level="controlled", verified=True, availability="withdrawn")
    assert block.availability == "withdrawn"


def test_access_block_rejects_available_after_when_not_embargoed():
    with pytest.raises(ValidationError, match="available_after"):
        AccessBlock(
            level="public",
            verified=True,
            availability="available",
            available_after="2026-Q3",
        )
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science-model/tests/test_packages.py -q -k availability
```

Expected: FAIL with errors about unexpected keyword arguments `availability` / `available_after` on `AccessBlock`.

- [ ] **Step 3: Implement**

In `science-model/src/science_model/packages/schema.py`, modify `AccessBlock`. The full class (preserving existing fields) becomes:

```python
class AccessBlock(BaseModel):
    """External dataset access verification gate state."""

    level: Literal["public", "registration", "controlled", "commercial", "mixed"]
    availability: Literal["available", "embargoed", "withdrawn"] = "available"
    available_after: str = ""
    verified: bool
    verification_method: Literal["", "retrieved", "credential-confirmed"] = ""
    last_reviewed: str = ""
    verified_by: str = ""
    source_url: str = ""
    credentials_required: str = ""
    exception: AccessException = Field(default_factory=AccessException)

    @model_validator(mode="after")
    def _validate_availability(self) -> "AccessBlock":
        if self.available_after and self.availability != "embargoed":
            raise ValueError(
                "available_after may only be set when availability == 'embargoed'"
            )
        return self
```

Add `model_validator` to the existing `pydantic` import line at the top of the file.

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science-model/tests/test_packages.py -q
```

Expected: PASS (both new and pre-existing tests).

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/packages/schema.py science-model/tests/test_packages.py
git commit -m "feat(model): add availability + available_after to AccessBlock"
```

---

## Task 2: `Readiness` model + default `ProjectEntity.readiness()` + `WorkflowRunEntity` override

These three pieces are small and tightly coupled — the model is the return type for the protocol, the default lives on `ProjectEntity`, and the workflow-run override is one line plus tests.

**Files:**
- Modify: `science-model/src/science_model/entities.py` — add `Readiness`, default `readiness()` on `ProjectEntity`, override on `WorkflowRunEntity`
- Create: `science-model/tests/test_readiness.py`

- [ ] **Step 1: Write the failing tests**

Create `science-model/tests/test_readiness.py`:

```python
"""Tests for the Readiness protocol on project entities."""
from __future__ import annotations

import pytest

from science_model.entities import (
    ProjectEntity,
    Readiness,
    TaskEntity,
    WorkflowRunEntity,
)


def _task(status: str = "active") -> TaskEntity:
    return TaskEntity(id="task:t001", type="task", title="example", status=status)


def _workflow_run(status: str = "complete") -> WorkflowRunEntity:
    return WorkflowRunEntity(
        id="workflow-run:wfr-001", type="workflow-run", title="example", status=status
    )


def test_readiness_model_shape():
    r = Readiness(ready=True, state="done")
    assert r.ready is True
    assert r.state == "done"
    assert r.detail == ""


def test_default_readiness_done_is_ready():
    assert _task(status="done").readiness() == Readiness(ready=True, state="done")


@pytest.mark.parametrize("status", ["proposed", "active", "blocked", "deferred", "retired"])
def test_default_readiness_non_done_is_not_ready(status: str):
    r = _task(status=status).readiness()
    assert r.ready is False
    assert r.state == status


def test_default_readiness_empty_status_is_unknown():
    r = _task(status="").readiness()
    assert r.ready is False
    assert r.state == "unknown"


def test_workflow_run_readiness_complete():
    r = _workflow_run(status="complete").readiness()
    assert r.ready is True
    assert r.state == "complete"


@pytest.mark.parametrize("status", ["", "pending", "running", "failed"])
def test_workflow_run_readiness_not_complete(status: str):
    r = _workflow_run(status=status).readiness()
    assert r.ready is False
    assert r.state == (status or "unknown")
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science-model/tests/test_readiness.py -q
```

Expected: FAIL with `ImportError: cannot import name 'Readiness' from science_model.entities`.

- [ ] **Step 3: Implement**

In `science-model/src/science_model/entities.py`, add `Protocol` to the typing imports:

```python
from typing import Protocol
```

Then add the readiness models/protocol near the other small models near the top, e.g. just above `class ProjectEntity`:

```python
class Readiness(BaseModel):
    """Result of evaluating an entity's readiness for downstream use.

    `state` is a short, display-ready label (e.g. "done", "embargoed",
    "controlled, unverified"). `detail` is an optional one-line elaboration
    rendered by `tasks show`.
    """

    ready: bool
    state: str
    detail: str = ""


class ReadinessResolverProtocol(Protocol):
    """Structural protocol implemented by science's ReadinessResolver."""

    def resolve_ref(self, ref: str) -> Readiness: ...
```

Add the default `readiness()` method to `ProjectEntity`:

```python
class ProjectEntity(Entity):
    # … existing fields unchanged …

    def readiness(self, resolver: ReadinessResolverProtocol | None = None) -> Readiness:
        """Default readiness: ready iff status == 'done'.

        `resolver` is optional context for subclasses that need to traverse
        other entities (e.g. derived datasets → producing workflow-run).
        Subclasses without cross-entity dependencies ignore it.
        """
        if self.status == "done":
            return Readiness(ready=True, state="done")
        return Readiness(ready=False, state=self.status or "unknown")
```

Override on `WorkflowRunEntity`:

```python
class WorkflowRunEntity(ProjectEntity):
    """Workflow run — readiness is `complete` when status == 'complete'."""

    def readiness(self, resolver: ReadinessResolverProtocol | None = None) -> Readiness:
        if self.status == "complete":
            return Readiness(ready=True, state="complete")
        return Readiness(ready=False, state=self.status or "unknown")
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science-model/tests/test_readiness.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/tests/test_readiness.py
git commit -m "feat(model): add Readiness protocol + default + workflow-run override"
```

---

## Task 3: `DatasetEntity.readiness()` — full implementation

Implements both `origin == "external"` (self-contained) and `origin == "derived"` (degrades when no resolver). The resolver-driven derived-dataset integration test lands in Task 4 alongside the resolver itself.

**Files:**
- Modify: `science-model/src/science_model/entities.py` — `DatasetEntity`
- Modify: `science-model/tests/test_readiness.py` — add dataset cases

- [ ] **Step 1: Write the failing tests**

Append to `science-model/tests/test_readiness.py`:

```python
from science_model.entities import DatasetEntity
from science_model.packages.schema import AccessBlock, AccessException, DerivationBlock


def _external_dataset(access: AccessBlock) -> DatasetEntity:
    return DatasetEntity(
        id="dataset:foo",
        type="dataset",
        title="example",
        origin="external",
        access=access,
    )


def _derived_dataset(workflow_run: str = "workflow-run:wfr-001") -> DatasetEntity:
    return DatasetEntity(
        id="dataset:foo-derived",
        type="dataset",
        title="example",
        origin="derived",
        derivation=DerivationBlock(
            workflow="workflow:foo",
            workflow_run=workflow_run,
            git_commit="deadbeef",
            config_snapshot="cfg",
            produced_at="2026-05-03",
        ),
    )


def test_dataset_external_available_verified_is_ready():
    ds = _external_dataset(AccessBlock(level="public", verified=True))
    r = ds.readiness()
    assert r.ready is True
    assert r.state == "available"


def test_dataset_external_available_unverified_is_not_ready():
    ds = _external_dataset(AccessBlock(level="controlled", verified=False))
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "controlled, unverified"


def test_dataset_external_embargoed_is_not_ready():
    ds = _external_dataset(
        AccessBlock(level="controlled", verified=False, availability="embargoed")
    )
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "embargoed"


def test_dataset_external_embargoed_with_window_includes_detail():
    ds = _external_dataset(
        AccessBlock(
            level="controlled",
            verified=False,
            availability="embargoed",
            available_after="2026-Q3",
        )
    )
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "embargoed"
    assert "2026-Q3" in r.detail


def test_dataset_external_withdrawn_is_not_ready():
    ds = _external_dataset(
        AccessBlock(level="controlled", verified=True, availability="withdrawn")
    )
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "withdrawn"


def test_dataset_external_exception_scope_reduced_is_ready():
    ds = _external_dataset(
        AccessBlock(
            level="controlled",
            verified=False,
            exception=AccessException(mode="scope-reduced", rationale="subset only"),
        )
    )
    r = ds.readiness()
    assert r.ready is True
    assert r.state == "consumable-via-scope-reduced"
    assert "subset only" in r.detail


def test_dataset_external_exception_substituted_is_ready():
    ds = _external_dataset(
        AccessBlock(
            level="controlled",
            verified=False,
            exception=AccessException(mode="substituted", rationale="using mirror"),
        )
    )
    r = ds.readiness()
    assert r.ready is True
    assert r.state == "consumable-via-substituted"


def test_dataset_external_exception_acquiring_is_not_ready():
    ds = _external_dataset(
        AccessBlock(
            level="controlled",
            verified=False,
            exception=AccessException(mode="expanded-to-acquire", rationale="dbGaP request open"),
        )
    )
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "acquiring"
    assert "dbGaP" in r.detail


def test_dataset_derived_without_resolver_degrades_gracefully():
    ds = _derived_dataset()
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "unknown"
    assert "resolver" in r.detail
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science-model/tests/test_readiness.py -q -k dataset
```

Expected: FAIL — `DatasetEntity.readiness()` falls back to the default and returns `state` based on `status`, not the derived branches.

- [ ] **Step 3: Implement**

In `science-model/src/science_model/entities.py`, override `readiness()` on `DatasetEntity`:

```python
class DatasetEntity(ProjectEntity):
    """Dataset — typed entity with rev 2.2 invariants (origin/access/derivation)."""

    @model_validator(mode="after")
    def _enforce_dataset_invariants(self) -> "DatasetEntity":
        # … existing invariant enforcement unchanged …
        return self

    def readiness(self, resolver: ReadinessResolverProtocol | None = None) -> Readiness:
        if self.origin == "external":
            return self._external_readiness()
        if self.origin == "derived":
            return self._derived_readiness(resolver)
        return Readiness(ready=False, state="unknown", detail=f"unknown origin {self.origin!r}")

    def _external_readiness(self) -> Readiness:
        access = self.access
        if access is None:
            # Should be unreachable per invariant #7, but guard anyway.
            return Readiness(ready=False, state="missing-access-block")
        if access.availability == "withdrawn":
            return Readiness(ready=False, state="withdrawn")
        if access.availability == "embargoed":
            detail = f"available_after: {access.available_after}" if access.available_after else ""
            return Readiness(ready=False, state="embargoed", detail=detail)
        # availability == "available"
        if access.exception.mode:
            mode = access.exception.mode
            rationale = access.exception.rationale
            if mode == "expanded-to-acquire":
                return Readiness(ready=False, state="acquiring", detail=rationale)
            if mode in ("scope-reduced", "substituted"):
                return Readiness(ready=True, state=f"consumable-via-{mode}", detail=rationale)
            # Unknown mode — fail closed (see Risks).
            return Readiness(ready=False, state=f"exception:{mode}", detail=rationale)
        if access.verified:
            return Readiness(ready=True, state="available")
        return Readiness(ready=False, state=f"{access.level}, unverified")

    def _derived_readiness(self, resolver: ReadinessResolverProtocol | None) -> Readiness:
        if resolver is None:
            return Readiness(
                ready=False,
                state="unknown",
                detail="derived dataset readiness requires resolver context",
            )
        if self.derivation is None:
            return Readiness(ready=False, state="missing-derivation-block")
        return resolver.resolve_ref(self.derivation.workflow_run)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science-model/tests/test_readiness.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/tests/test_readiness.py
git commit -m "feat(model): DatasetEntity readiness from access block + derivation"
```

---

## Task 4: `ReadinessResolver` in `science`

Implements the resolver and tests both resolver-internal behavior (cycle, cache, unresolved) and the integration with derived datasets.

**Files:**
- Create: `science/src/science_tool/tasks_readiness.py`
- Create: `science/tests/test_readiness_resolver.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_readiness_resolver.py`:

```python
"""Tests for ReadinessResolver."""
from __future__ import annotations

from science_model.entities import (
    DatasetEntity,
    ProjectEntity,
    Readiness,
    WorkflowRunEntity,
)
from science_model.packages.schema import AccessBlock, DerivationBlock

from science_tool.tasks_readiness import ReadinessResolver


def _wfr(run_id: str, status: str) -> WorkflowRunEntity:
    return WorkflowRunEntity(id=run_id, type="workflow-run", title="t", status=status)


def _derived(ds_id: str, run_id: str) -> DatasetEntity:
    return DatasetEntity(
        id=ds_id,
        type="dataset",
        title="d",
        origin="derived",
        derivation=DerivationBlock(
            workflow="workflow:w",
            workflow_run=run_id,
            git_commit="x",
            config_snapshot="y",
            produced_at="2026-05-03",
        ),
    )


def test_resolver_returns_unresolved_for_unknown_ref():
    resolver = ReadinessResolver(lookup=lambda ref: None)
    r = resolver.resolve_ref("dataset:nope")
    assert r.ready is False
    assert r.state == "unresolved"
    assert "dataset:nope" in r.detail


def test_resolver_delegates_to_entity_readiness():
    wfr = _wfr("workflow-run:r1", status="complete")
    resolver = ReadinessResolver(lookup={"workflow-run:r1": wfr}.get)
    r = resolver.resolve_ref("workflow-run:r1")
    assert r == Readiness(ready=True, state="complete")


def test_resolver_caches_repeated_lookups():
    wfr = _wfr("workflow-run:r1", status="complete")
    calls: list[str] = []

    def lookup(ref: str) -> ProjectEntity | None:
        calls.append(ref)
        return wfr if ref == "workflow-run:r1" else None

    resolver = ReadinessResolver(lookup=lookup)
    resolver.resolve_ref("workflow-run:r1")
    resolver.resolve_ref("workflow-run:r1")
    resolver.resolve_ref("workflow-run:r1")
    assert calls == ["workflow-run:r1"]


def test_resolver_detects_cycle():
    # dataset:A is derived from workflow-run:R, which (in this synthetic case)
    # has been authored to reference dataset:A. The resolver must not infinite-loop.
    ds_a = _derived("dataset:A", "workflow-run:R")

    class CyclingRun(WorkflowRunEntity):
        def readiness(self, resolver=None):
            # Simulate a cycle: this run's readiness re-asks about dataset:A.
            assert resolver is not None
            return resolver.resolve_ref("dataset:A")

    run = CyclingRun(id="workflow-run:R", type="workflow-run", title="t", status="complete")
    store = {"dataset:A": ds_a, "workflow-run:R": run}
    resolver = ReadinessResolver(lookup=store.get)
    r = resolver.resolve_ref("dataset:A")
    assert r.ready is False
    assert r.state == "cycle"


def test_resolver_drives_derived_dataset_to_workflow_run():
    wfr = _wfr("workflow-run:r1", status="complete")
    ds = _derived("dataset:derived", "workflow-run:r1")
    store = {"dataset:derived": ds, "workflow-run:r1": wfr}
    resolver = ReadinessResolver(lookup=store.get)
    r = resolver.resolve_ref("dataset:derived")
    assert r.ready is True
    assert r.state == "complete"


def test_resolver_drives_derived_dataset_workflow_run_not_yet_complete():
    wfr = _wfr("workflow-run:r1", status="running")
    ds = _derived("dataset:derived", "workflow-run:r1")
    store = {"dataset:derived": ds, "workflow-run:r1": wfr}
    resolver = ReadinessResolver(lookup=store.get)
    r = resolver.resolve_ref("dataset:derived")
    assert r.ready is False
    assert r.state == "running"
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_readiness_resolver.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.tasks_readiness'`.

- [ ] **Step 3: Implement**

Create `science/src/science_tool/tasks_readiness.py`:

```python
"""ReadinessResolver: tool-layer entity-lookup + cycle-guarded readiness resolution.

Constructed per CLI invocation with a snapshot of the local entity store.
Caches resolved readiness within its own lifetime so the same blocker
referenced by N tasks costs one resolution.
"""
from __future__ import annotations

from typing import Callable

from science_model.entities import ProjectEntity, Readiness


class ReadinessResolver:
    """Resolves entity references to Readiness, guarding against cycles."""

    def __init__(self, lookup: Callable[[str], ProjectEntity | None]) -> None:
        self._lookup = lookup
        self._visiting: set[str] = set()
        self._cache: dict[str, Readiness] = {}

    def resolve_ref(self, ref: str) -> Readiness:
        cached = self._cache.get(ref)
        if cached is not None:
            return cached
        if ref in self._visiting:
            return Readiness(
                ready=False, state="cycle", detail=f"derivation cycle through {ref}"
            )
        entity = self._lookup(ref)
        if entity is None:
            return Readiness(
                ready=False, state="unresolved", detail=f"unknown entity {ref}"
            )
        self._visiting.add(ref)
        try:
            result = entity.readiness(resolver=self)
        finally:
            self._visiting.discard(ref)
        self._cache[ref] = result
        return result
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_readiness_resolver.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/tasks_readiness.py science/tests/test_readiness_resolver.py
git commit -m "feat(tool): add ReadinessResolver with cycle protection + caching"
```

---

## Task 5: Local entity lookup helpers + `validate_blocker_refs`

**Files:**
- Modify: `science/src/science_tool/entities.py` — add `load_local_entity_ids()` and `load_local_entity_index()`
- Create: `science/src/science_tool/tasks_blockers.py`
- Create: `science/tests/test_tasks_blockers.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_tasks_blockers.py`:

```python
"""Tests for blocker ref validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_model.entities import DatasetEntity
from science_tool.entities import load_local_entity_ids, load_local_entity_index
from science_tool.tasks_blockers import (
    BlockerValidationError,
    validate_blocker_refs,
)


def _setup_project_with_dataset(tmp_path: Path) -> Path:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/datasets/foo.md",
        {
            "id": "dataset:foo",
            "type": "dataset",
            "title": "Foo",
            "status": "active",
            "origin": "external",
            "access": {"level": "public", "verified": True},
        },
    )
    return tmp_path


def test_load_local_entity_ids_returns_project_entity_ids(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    ids = load_local_entity_ids(tmp_path)
    assert "dataset:foo" in ids


def test_load_local_entity_index_returns_project_entities(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    index = load_local_entity_index(tmp_path)
    assert isinstance(index["dataset:foo"], DatasetEntity)


def test_validate_rejects_untyped_string(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    with pytest.raises(BlockerValidationError, match="must be typed"):
        validate_blocker_refs(tmp_path, ["just-a-string"])


def test_validate_rejects_untyped_even_with_force(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    with pytest.raises(BlockerValidationError, match="must be typed"):
        validate_blocker_refs(tmp_path, ["just-a-string"], force=True)


def test_validate_accepts_known_typed_ref(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    result = validate_blocker_refs(tmp_path, ["dataset:foo"])
    assert result == ["dataset:foo"]


def test_validate_rejects_unknown_typed_ref(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    with pytest.raises(BlockerValidationError, match="unknown entity"):
        validate_blocker_refs(tmp_path, ["dataset:does-not-exist"])


def test_validate_force_accepts_unknown_typed_ref(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    result = validate_blocker_refs(tmp_path, ["dataset:does-not-exist"], force=True)
    assert result == ["dataset:does-not-exist"]


def test_validate_multiple_refs_reports_first_failure(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    with pytest.raises(BlockerValidationError, match="dataset:bogus"):
        validate_blocker_refs(tmp_path, ["dataset:foo", "dataset:bogus"])
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_tasks_blockers.py -q
```

Expected: FAIL with import errors for missing `load_local_entity_ids`, `load_local_entity_index`, and `science_tool.tasks_blockers`.

- [ ] **Step 3: Implement**

First, add local project-entity lookup helpers to `science/src/science_tool/entities.py` near `list_entities()`:

```python
from science_model.entities import ProjectEntity


def load_local_entity_index(project_root: Path) -> dict[str, ProjectEntity]:
    """Return local project entities keyed by canonical id.

    Domain/catalog entities are intentionally excluded: task blockers are
    project-state dependencies such as tasks, datasets, workflow-runs, and
    other ProjectEntity subclasses. Cross-project entities are out of scope.
    """
    index: dict[str, ProjectEntity] = {}
    for entity in load_project_sources(project_root.resolve()).entities:
        if isinstance(entity, ProjectEntity):
            index[entity.canonical_id] = entity
    return index


def load_local_entity_ids(project_root: Path) -> set[str]:
    """Return canonical ids for local ProjectEntity records."""
    return set(load_local_entity_index(project_root))
```

Then create `science/src/science_tool/tasks_blockers.py`:

```python
"""Validation helpers for typed blocker refs on tasks."""
from __future__ import annotations

import re
from pathlib import Path

from science_tool.entities import load_local_entity_ids

# Format: <kind>:<local-id> where kind is lowercase letters/digits/hyphens
# and local-id is anything non-empty without whitespace.
_TYPED_REF_RE = re.compile(r"^[a-z][a-z0-9-]*:\S+$")


class BlockerValidationError(ValueError):
    """Raised when a blocker reference fails validation."""


def validate_blocker_refs(
    project_root: Path,
    refs: list[str],
    *,
    force: bool = False,
) -> list[str]:
    """Validate and normalize a list of blocker refs.

    - Rejects refs not matching `^<kind>:<local-id>$` (always; --force does not bypass).
    - Rejects refs that don't resolve to a known local ProjectEntity, unless `force=True`.
    - Returns the (possibly normalized) ref list on success.
    - Raises `BlockerValidationError` with a concrete actionable message on failure.
    """
    for ref in refs:
        if not _TYPED_REF_RE.match(ref):
            raise BlockerValidationError(
                f"blocker {ref!r} must be typed: <kind>:<local-id> "
                "(e.g. dataset:foo, task:t007)"
            )

    if force:
        return list(refs)

    known = load_local_entity_ids(project_root)
    for ref in refs:
        if ref not in known:
            raise BlockerValidationError(
                f"unknown entity {ref}. Create it first with: "
                "add the corresponding entity file or use the appropriate creation workflow "
                "(or pass --force to record anyway)"
            )
    return list(refs)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_tasks_blockers.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities.py science/src/science_tool/tasks_blockers.py science/tests/test_tasks_blockers.py
git commit -m "feat(tool): add local entity lookup + typed blocker validation"
```

---

## Task 6: `parse_tasks_for_cli` wrapper

Keeps `parse_tasks` pure (no warnings) and adds a CLI-only wrapper that surfaces legacy untyped-blocker warnings.

**Files:**
- Modify: `science/src/science_tool/tasks.py`
- Create: `science/tests/test_tasks_parse_for_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_tasks_parse_for_cli.py`:

```python
"""Tests for the CLI-only parse wrapper that surfaces legacy-blocker warnings."""
from __future__ import annotations

from pathlib import Path

from science_tool.tasks import parse_tasks, parse_tasks_for_cli


def _write_active(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "active.md"
    path.write_text(body, encoding="utf-8")
    return path


_LEGACY_TASK = """## [t001] Old task
- type: dev
- priority: P2
- status: blocked
- blocked-by: [some-old-string, dataset:foo]
- created: 2026-05-01

Body.
"""


def test_parse_tasks_does_not_emit_warnings(tmp_path: Path):
    path = _write_active(tmp_path, _LEGACY_TASK)
    tasks = parse_tasks(path)
    assert len(tasks) == 1
    assert tasks[0].blocked_by == ["some-old-string", "dataset:foo"]


def test_parse_tasks_for_cli_warns_about_untyped_blockers(tmp_path: Path):
    path = _write_active(tmp_path, _LEGACY_TASK)
    tasks, warnings = parse_tasks_for_cli(path)
    assert len(tasks) == 1
    assert any("some-old-string" in w for w in warnings)
    # Properly typed refs do NOT generate warnings.
    assert not any("dataset:foo" in w for w in warnings)


def test_parse_tasks_for_cli_no_warnings_when_all_typed(tmp_path: Path):
    body = """## [t001] All-typed
- type: dev
- priority: P2
- status: blocked
- blocked-by: [dataset:foo, task:t002]
- created: 2026-05-01

Body.
"""
    path = _write_active(tmp_path, body)
    tasks, warnings = parse_tasks_for_cli(path)
    assert len(tasks) == 1
    assert warnings == []
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_tasks_parse_for_cli.py -q
```

Expected: FAIL with `ImportError: cannot import name 'parse_tasks_for_cli'`.

- [ ] **Step 3: Implement**

Add to `science/src/science_tool/tasks.py` (alongside `parse_tasks`):

```python
import re

_TYPED_REF_RE = re.compile(r"^[a-z][a-z0-9-]*:\S+$")


def parse_tasks_for_cli(path: Path) -> tuple[list[Task], list[str]]:
    """Parse tasks AND surface user-facing warnings.

    Detects legacy untyped blocker refs and returns them as warning strings.
    Programmatic callers should prefer `parse_tasks` to avoid noise.
    """
    tasks = parse_tasks(path)
    warnings: list[str] = []
    for task in tasks:
        for ref in task.blocked_by:
            if not _TYPED_REF_RE.match(ref):
                warnings.append(
                    f"task {task.id}: legacy untyped blocker {ref!r} — "
                    f"run 'science tasks fix-blockers' to retype"
                )
    return tasks, warnings
```

Add `parse_tasks_for_cli` to the module's `__all__` list.

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_tasks_parse_for_cli.py -q
```

Expected: PASS. Re-run `parse_tasks` tests to confirm no regression:

```bash
uv run --frozen pytest science/tests/test_tasks.py -q
```

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/tasks.py science/tests/test_tasks_parse_for_cli.py
git commit -m "feat(tool): add parse_tasks_for_cli wrapper for legacy-blocker warnings"
```

---

## Task 7: Wire validation into `block_task` / `edit_task` / `add_task`

Thread `project_root` through and route blocker writes through `validate_blocker_refs`.

**Files:**
- Modify: `science/src/science_tool/tasks.py` — `block_task`, `edit_task`, `add_task`
- Modify: `science/tests/test_tasks.py` — extend with validation cases

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_tasks.py` (or wherever `block_task` is tested):

```python
import pytest
from pathlib import Path

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_tool.tasks_blockers import BlockerValidationError
from science_tool.tasks import (
    add_task,
    block_task,
)


def _seed_with_dataset(tmp_path: Path) -> Path:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/datasets/foo.md",
        {
            "id": "dataset:foo",
            "type": "dataset",
            "title": "Foo",
            "status": "active",
            "origin": "external",
            "access": {"level": "public", "verified": True},
        },
    )
    # Also create a baseline task to block.
    add_task(
        project_root=tmp_path,
        tasks_dir=tmp_path / "tasks",
        title="baseline",
        priority="P2",
        task_type="dev",
    )
    return tmp_path


def test_block_task_rejects_untyped_blocker(tmp_path: Path):
    root = _seed_with_dataset(tmp_path)
    with pytest.raises(BlockerValidationError):
        block_task(
            project_root=root,
            tasks_dir=root / "tasks",
            task_id="t001",
            blocked_by=["just-a-string"],
        )


def test_block_task_rejects_unknown_typed_ref(tmp_path: Path):
    root = _seed_with_dataset(tmp_path)
    with pytest.raises(BlockerValidationError):
        block_task(
            project_root=root,
            tasks_dir=root / "tasks",
            task_id="t001",
            blocked_by=["dataset:does-not-exist"],
        )


def test_block_task_accepts_known_typed_ref(tmp_path: Path):
    root = _seed_with_dataset(tmp_path)
    task = block_task(
        project_root=root,
        tasks_dir=root / "tasks",
        task_id="t001",
        blocked_by=["dataset:foo"],
    )
    assert task.status == "blocked"
    assert task.blocked_by == ["dataset:foo"]


def test_block_task_force_accepts_unknown_typed_ref(tmp_path: Path):
    root = _seed_with_dataset(tmp_path)
    task = block_task(
        project_root=root,
        tasks_dir=root / "tasks",
        task_id="t001",
        blocked_by=["dataset:does-not-exist"],
        force=True,
    )
    assert task.blocked_by == ["dataset:does-not-exist"]


def test_block_task_multiple_blockers(tmp_path: Path):
    root = _seed_with_dataset(tmp_path)
    write_markdown_entity(
        root,
        "doc/datasets/bar.md",
        {
            "id": "dataset:bar",
            "type": "dataset",
            "title": "Bar",
            "status": "active",
            "origin": "external",
            "access": {"level": "public", "verified": True},
        },
    )
    task = block_task(
        project_root=root,
        tasks_dir=root / "tasks",
        task_id="t001",
        blocked_by=["dataset:foo", "dataset:bar"],
    )
    assert task.blocked_by == ["dataset:foo", "dataset:bar"]
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_tasks.py -q -k blocker
```

Expected: FAIL — `block_task` doesn't accept `project_root` / `force`, and accepts a single `blocked_by: str`, not a list.

- [ ] **Step 3: Implement**

In `science/src/science_tool/tasks.py`, modify `block_task`:

```python
from science_tool.tasks_blockers import validate_blocker_refs


def block_task(
    project_root: Path,
    tasks_dir: Path,
    task_id: str,
    blocked_by: list[str],
    *,
    force: bool = False,
) -> Task:
    """Add typed blockers to a task, set status to 'blocked'."""
    validated = validate_blocker_refs(project_root, blocked_by, force=force)
    tasks = _read_active(tasks_dir)
    task = _find_task(tasks, task_id)

    task.status = "blocked"
    for ref in validated:
        if ref not in task.blocked_by:
            task.blocked_by.append(ref)

    _write_active(tasks_dir, tasks)
    return task
```

In `edit_task`, when `blocked_by is not None`, call `validate_blocker_refs(project_root, blocked_by, force=force)` before assigning. Add `project_root: Path` and `force: bool = False` parameters.

In `add_task`, when `blocked_by` is non-empty, call the same validator before constructing the Task. Add `project_root: Path` and `force: bool = False` parameters.

The signatures become, and the current assignment sites change as shown:

```python
def add_task(
    project_root: Path,
    tasks_dir: Path,
    title: str,
    priority: str,
    task_type: str = "",
    aspects: list[str] | None = None,
    related: list[str] | None = None,
    blocked_by: list[str] | None = None,
    group: str = "",
    description: str = "",
    *,
    force: bool = False,
) -> Task:
    validated_blockers = (
        validate_blocker_refs(project_root, blocked_by, force=force)
        if blocked_by
        else []
    )
    task = Task(
        id=next_task_id(tasks_dir),
        title=title,
        type=task_type,
        aspects=aspects or [],
        priority=priority,
        status="proposed",
        created=date.today(),
        related=related or [],
        blocked_by=validated_blockers,
        group=group,
        description=description,
    )
```

```python
def edit_task(
    project_root: Path,
    tasks_dir: Path,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    aspects: list[str] | None = None,
    related: list[str] | None = None,
    blocked_by: list[str] | None = None,
    group: str | None = None,
    *,
    force: bool = False,
) -> Task:
    location = find_task_location(tasks_dir, task_id)
    task = location.task
    if blocked_by is not None:
        task.blocked_by = validate_blocker_refs(project_root, blocked_by, force=force)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_tasks.py -q
```

Expected: PASS. Update any pre-existing tests that call `block_task` with the old single-string signature or `add_task` / `edit_task` without `project_root`; the test failures will name them precisely.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/tasks.py science/tests/test_tasks.py
git commit -m "feat(tool): require typed blockers in block/add/edit task"
```

---

## Task 8: CLI — `tasks block` repeatable + `--force`

**Files:**
- Modify: `science/src/science_tool/cli.py` — `tasks_block` command (around line 2473)
- Modify: `science/tests/test_tasks_cli.py` — add CLI cases

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_tasks_cli.py`:

```python
from click.testing import CliRunner

from science_tool.cli import main
from _fixtures.entity_helpers import seed_project, write_markdown_entity


def _setup(tmp_path):
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/datasets/foo.md",
        {
            "id": "dataset:foo",
            "type": "dataset",
            "title": "Foo",
            "status": "active",
            "origin": "external",
            "access": {"level": "public", "verified": True},
        },
    )
    write_markdown_entity(
        tmp_path,
        "doc/datasets/bar.md",
        {
            "id": "dataset:bar",
            "type": "dataset",
            "title": "Bar",
            "status": "active",
            "origin": "external",
            "access": {"level": "public", "verified": True},
        },
    )
    runner = CliRunner()
    runner.invoke(
        main,
        ["tasks", "add", "Block-me", "--priority", "P2"],
    )
    return runner


def test_tasks_block_rejects_untyped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    result = runner.invoke(main, ["tasks", "block", "t001", "--by", "untyped"])
    assert result.exit_code != 0
    assert "must be typed" in result.output


def test_tasks_block_repeatable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    result = runner.invoke(
        main,
        ["tasks", "block", "t001", "--by", "dataset:foo", "--by", "dataset:bar"],
    )
    assert result.exit_code == 0, result.output
    assert "dataset:foo" in result.output
    assert "dataset:bar" in result.output


def test_tasks_block_force_accepts_unknown(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    result = runner.invoke(
        main,
        ["tasks", "block", "t001", "--by", "dataset:not-yet", "--force"],
    )
    assert result.exit_code == 0, result.output
    assert "dataset:not-yet" in result.output
    assert "WARNING" in result.output
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_tasks_cli.py -q -k block
```

Expected: FAIL — `--by` is not `multiple`; no `--force` flag exists.

- [ ] **Step 3: Implement**

In `science/src/science_tool/cli.py`, replace the existing `tasks_block` command:

```python
@tasks.command("block")
@click.argument("task_id")
@click.option("--by", "blocked_by", multiple=True, required=True,
              help="Typed blocker ref (repeatable): <kind>:<local-id>")
@click.option("--force", is_flag=True,
              help="Record blocker even if entity not yet known")
def tasks_block(
    task_id: str, blocked_by: tuple[str, ...], force: bool
) -> None:
    """Block a task by one or more typed entity references."""
    from science_tool.tasks import block_task
    from science_tool.tasks_blockers import BlockerValidationError
    from science_tool.entities import load_local_entity_ids

    try:
        task = block_task(
            project_root=Path.cwd(),
            tasks_dir=DEFAULT_TASKS_DIR,
            task_id=task_id,
            blocked_by=list(blocked_by),
            force=force,
        )
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    except BlockerValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    if force:
        known = load_local_entity_ids(Path.cwd())
        for ref in blocked_by:
            if ref not in known:
                click.echo(
                    f"WARNING: recorded unresolved blocker {ref}; graph audit will flag it",
                    err=True,
                )

    refs = ", ".join(task.blocked_by)
    click.echo(f"[{task.id}] blocked by {refs}")
```

Apply the same `--force` flag to `tasks_add` and `tasks_edit`'s `--blocked-by` handling: thread `project_root=Path.cwd()` and `force=force` through to `add_task` / `edit_task`. Do not add a `--type` option to `tasks add`; the current CLI intentionally rejects it, and existing tests cover that behavior.

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_tasks_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_tasks_cli.py
git commit -m "feat(cli): tasks block accepts repeatable --by + --force"
```

---

## Task 9: CLI — `tasks blockers` introspection command

Adds a new command that reports per-blocker readiness, used both interactively and as the JSON source for the future auto-unblock sweep.

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_tasks_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_tasks_cli.py`:

```python
import json


def test_tasks_blockers_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:foo"])
    result = runner.invoke(main, ["tasks", "blockers", "t001"])
    assert result.exit_code == 0, result.output
    assert "dataset:foo" in result.output
    assert "available" in result.output  # the readiness state for verified public datasets


def test_tasks_blockers_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:foo"])
    result = runner.invoke(main, ["tasks", "blockers", "t001", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["task_id"] == "t001"
    assert len(payload["blockers"]) == 1
    blocker = payload["blockers"][0]
    assert blocker["ref"] == "dataset:foo"
    assert blocker["ready"] is True
    assert blocker["state"] == "available"
    assert "detail" in blocker
    assert blocker["unresolved"] is False


def test_tasks_blockers_json_unresolved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:gone", "--force"])
    result = runner.invoke(main, ["tasks", "blockers", "t001", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    blocker = payload["blockers"][0]
    assert blocker["ref"] == "dataset:gone"
    assert blocker["unresolved"] is True
    assert blocker["ready"] is False
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_tasks_cli.py -q -k blockers
```

Expected: FAIL with `Error: No such command 'blockers'`.

- [ ] **Step 3: Implement**

In `science/src/science_tool/cli.py`, add the `tasks_blockers` command:

```python
@tasks.command("blockers")
@click.argument("task_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def tasks_blockers(task_id: str, fmt: str) -> None:
    """Show per-blocker readiness for a task."""
    import json as _json

    from science_tool.tasks import _find_task, _read_active
    from science_tool.tasks_readiness import ReadinessResolver
    from science_tool.entities import load_local_entity_index

    tasks = _read_active(DEFAULT_TASKS_DIR)
    try:
        task = _find_task(tasks, task_id)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    index = load_local_entity_index(Path.cwd())  # dict[str, ProjectEntity]
    resolver = ReadinessResolver(lookup=index.get)

    rows = []
    for ref in task.blocked_by:
        readiness = resolver.resolve_ref(ref)
        rows.append(
            {
                "ref": ref,
                "ready": readiness.ready,
                "state": readiness.state,
                "detail": readiness.detail,
                "unresolved": readiness.state == "unresolved",
            }
        )

    if fmt == "json":
        click.echo(_json.dumps({"task_id": task.id, "blockers": rows}, indent=2))
        return

    # Table form — use whatever table helper this CLI already uses; if there
    # isn't one handy, a plain printf is fine for the first cut.
    click.echo(f"Blockers for [{task.id}] {task.title}:")
    for row in rows:
        marker = "✓" if row["ready"] else "·"
        line = f"  {marker} {row['ref']:40s}  {row['state']}"
        if row["detail"]:
            line += f"  ({row['detail']})"
        click.echo(line)
```

`load_local_entity_index(project_root) -> dict[str, ProjectEntity]` was added in Task 5. It returns local project entities keyed by canonical id; domain/catalog entities and federated peers are intentionally excluded.

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_tasks_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/src/science_tool/entities.py science/tests/test_tasks_cli.py
git commit -m "feat(cli): add tasks blockers command (table + json)"
```

---

## Task 10: CLI — `tasks fix-blockers` migration command

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_tasks_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_tasks_cli.py`:

```python
def test_tasks_fix_blockers_lists_legacy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    # Hand-write an active.md with a legacy untyped blocker, since the new
    # CLI rejects them at write time.
    (tmp_path / "tasks").mkdir(exist_ok=True)
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Old\n"
        "- type: dev\n"
        "- priority: P2\n"
        "- status: blocked\n"
        "- blocked-by: [old-string]\n"
        "- created: 2026-05-01\n\n"
        "Body.\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    # Non-interactive dry-run: just lists what would change.
    result = runner.invoke(main, ["tasks", "fix-blockers", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "t001" in result.output
    assert "old-string" in result.output


def test_tasks_fix_blockers_retypes_with_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/datasets/foo.md",
        {
            "id": "dataset:foo",
            "type": "dataset",
            "title": "Foo",
            "status": "active",
            "origin": "external",
            "access": {"level": "public", "verified": True},
        },
    )
    (tmp_path / "tasks").mkdir(exist_ok=True)
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Old\n"
        "- type: dev\n"
        "- priority: P2\n"
        "- status: blocked\n"
        "- blocked-by: [old-string]\n"
        "- created: 2026-05-01\n\n"
        "Body.\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    # Interactive: provide replacement, then accept.
    result = runner.invoke(
        main, ["tasks", "fix-blockers"], input="dataset:foo\ny\n"
    )
    assert result.exit_code == 0, result.output
    rewritten = (tmp_path / "tasks" / "active.md").read_text()
    assert "dataset:foo" in rewritten
    assert "old-string" not in rewritten
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_tasks_cli.py -q -k fix_blockers
```

Expected: FAIL with `Error: No such command 'fix-blockers'`.

- [ ] **Step 3: Implement**

In `science/src/science_tool/cli.py`:

```python
@tasks.command("fix-blockers")
@click.option("--dry-run", is_flag=True,
              help="List legacy untyped blockers without modifying any files")
def tasks_fix_blockers(dry_run: bool) -> None:
    """Interactive sweep to retype legacy untyped blockers."""
    from science_tool.tasks import (
        _write_active,
        parse_tasks_for_cli,
    )
    from science_tool.tasks_blockers import _TYPED_REF_RE

    tasks_path = DEFAULT_TASKS_DIR / "active.md"
    tasks_, warnings = parse_tasks_for_cli(tasks_path)
    if not warnings:
        click.echo("No legacy untyped blockers found.")
        return

    if dry_run:
        click.echo("Legacy untyped blockers (dry-run):")
        for w in warnings:
            click.echo(f"  {w}")
        return

    changed = False
    for task in tasks_:
        new_blockers: list[str] = []
        for ref in task.blocked_by:
            if _TYPED_REF_RE.match(ref):
                new_blockers.append(ref)
                continue
            click.echo(f"\nTask [{task.id}] {task.title}")
            click.echo(f"  legacy blocker: {ref!r}")
            replacement = click.prompt(
                "  replace with (typed ref, or empty to drop, or '!' to keep as-is)",
                default="",
                show_default=False,
            ).strip()
            if replacement == "!":
                new_blockers.append(ref)
            elif replacement == "":
                pass  # drop
            else:
                if not _TYPED_REF_RE.match(replacement):
                    click.echo(f"  ! {replacement!r} not a typed ref; keeping original")
                    new_blockers.append(ref)
                else:
                    new_blockers.append(replacement)
                    changed = True
        task.blocked_by = new_blockers

    if changed and click.confirm("\nWrite changes to tasks/active.md?", default=True):
        _write_active(DEFAULT_TASKS_DIR, tasks_)
        click.echo("Updated.")
    else:
        click.echo("No changes written.")
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_tasks_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_tasks_cli.py
git commit -m "feat(cli): add tasks fix-blockers interactive migration"
```

---

## Task 11: Display — `tasks list` summary line, JSON readiness, "all-ready" nudge

**Files:**
- Modify: `science/src/science_tool/tasks_display.py`
- Modify: `science/src/science_tool/cli.py` — `tasks_list` (call site)
- Modify: `science/tests/test_tasks_display.py` (or test_tasks_cli.py if list is tested there)

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_tasks_cli.py`:

```python
def test_tasks_list_shows_blocker_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:foo"])
    result = runner.invoke(main, ["tasks", "list"])
    assert result.exit_code == 0, result.output
    # Default render must include a blocker-count line for blocked tasks.
    assert "blocked-by: 1" in result.output
    # Since dataset:foo is verified-public → ready, the all-ready nudge fires.
    assert "all ready" in result.output
    assert "tasks unblock t001" in result.output


def test_tasks_list_shows_mixed_blocker_states(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    # Embargoed dataset (not ready) + available dataset (ready).
    write_markdown_entity(
        tmp_path,
        "doc/datasets/foo.md",
        {
            "id": "dataset:foo",
            "type": "dataset",
            "title": "Foo",
            "status": "active",
            "origin": "external",
            "access": {"level": "public", "verified": True},
        },
    )
    write_markdown_entity(
        tmp_path,
        "doc/datasets/bar.md",
        {
            "id": "dataset:bar",
            "type": "dataset",
            "title": "Bar",
            "status": "active",
            "origin": "external",
            "access": {
                "level": "controlled",
                "verified": False,
                "availability": "embargoed",
            },
        },
    )
    runner = CliRunner()
    runner.invoke(main, ["tasks", "add", "T", "--priority", "P2"])
    runner.invoke(
        main,
        ["tasks", "block", "t001", "--by", "dataset:foo", "--by", "dataset:bar"],
    )
    result = runner.invoke(main, ["tasks", "list"])
    assert result.exit_code == 0
    assert "blocked-by: 2" in result.output
    assert "embargoed" in result.output
    # Mixed → no all-ready nudge.
    assert "all ready" not in result.output


def test_tasks_list_json_includes_blocker_readiness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:foo"])
    result = runner.invoke(main, ["tasks", "list", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    blocked = [t for t in payload["rows"] if t["status"] == "blocked"]
    assert blocked
    assert "blocked_by_readiness" in blocked[0]
    readiness = blocked[0]["blocked_by_readiness"]
    assert readiness[0]["ref"] == "dataset:foo"
    assert readiness[0]["ready"] is True
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_tasks_cli.py -q -k list
```

Expected: FAIL — current display does not surface blocker counts/states; JSON output lacks `blocked_by_readiness`.

- [ ] **Step 3: Implement**

In `science/src/science_tool/tasks_display.py`, extend the rendering helpers. The exact integration depends on the current shape of `render_tasks_table`; the contract:

```python
def render_blocker_summary(task: Task, resolver: ReadinessResolver) -> str | None:
    """Render the second-line blocker summary, or None when not blocked."""
    if task.status != "blocked" or not task.blocked_by:
        return None
    readinesses = [resolver.resolve_ref(ref) for ref in task.blocked_by]
    by_state: dict[str, int] = {}
    for r in readinesses:
        by_state[r.state] = by_state.get(r.state, 0) + 1
    if all(r.ready for r in readinesses):
        return f"        blocked-by: {len(readinesses)} (all ready — run 'tasks unblock {task.id}')"
    parts = [f"{count} {state}" for state, count in by_state.items() if not any(r.ready and r.state == state for r in readinesses)]
    breakdown = ", ".join(parts)
    return f"        blocked-by: {len(readinesses)} ({breakdown})"
```

Then in the existing `render_tasks_table` (or wherever rows are emitted), after each row print the blocker summary line if non-None. The renderer needs a `ReadinessResolver` — pass it in as a parameter and have the CLI construct it once per invocation.

For the JSON path, modify the `tasks list --format json` serialization (in `cli.py`) to include `blocked_by_readiness` per blocked task with the same `ref/ready/state/detail/unresolved` shape used by `tasks blockers --format json`. Reuse the helper from Task 9 to avoid duplication — extract if needed.

Also wire `tasks list` (and any other CLI command that reads the active task list) to call `parse_tasks_for_cli` and surface the warnings on `stderr` before the main output.

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_tasks_cli.py -q
uv run --frozen pytest science/tests/test_tasks_display.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/tasks_display.py science/src/science_tool/cli.py science/tests/test_tasks_cli.py science/tests/test_tasks_display.py
git commit -m "feat(cli): tasks list surfaces blocker readiness + all-ready nudge"
```

---

## Task 12: Display — `tasks show` per-blocker readiness

**Files:**
- Modify: `science/src/science_tool/cli.py` — `tasks_show` command
- Modify: `science/tests/test_tasks_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_tasks_cli.py`:

```python
def test_tasks_show_renders_per_blocker_readiness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/datasets/embargoed.md",
        {
            "id": "dataset:embargoed",
            "type": "dataset",
            "title": "E",
            "status": "active",
            "origin": "external",
            "access": {
                "level": "controlled",
                "verified": False,
                "availability": "embargoed",
                "available_after": "2026-Q3",
            },
        },
    )
    runner = CliRunner()
    runner.invoke(main, ["tasks", "add", "T", "--priority", "P2"])
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:embargoed"])
    result = runner.invoke(main, ["tasks", "show", "t001"])
    assert result.exit_code == 0, result.output
    assert "dataset:embargoed" in result.output
    assert "embargoed" in result.output
    assert "2026-Q3" in result.output
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_tasks_cli.py -q -k tasks_show_renders_per_blocker
```

Expected: FAIL — current `tasks show` lists blockers as raw ids only, no readiness state, no `available_after` window.

- [ ] **Step 3: Implement**

In `science/src/science_tool/cli.py`, modify `tasks_show` to construct a `ReadinessResolver` and render each blocker with state/detail. After the existing per-field output, replace any line that prints `blocked_by` raw with:

```python
if task.blocked_by:
    click.echo("blocked-by:")
    for ref in task.blocked_by:
        readiness = resolver.resolve_ref(ref)
        line = f"  - {ref:40s}  {readiness.state}"
        if readiness.detail:
            line += f"  ({readiness.detail})"
        click.echo(line)
```

The `resolver` is built the same way as in Task 9 (`load_local_entity_index` + `ReadinessResolver`).

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_tasks_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_tasks_cli.py
git commit -m "feat(cli): tasks show renders per-blocker readiness"
```

---

## Task 13: Documentation updates

**Files:**
- Modify: `commands/tasks.md`
- Modify: active tasks skill, if present — find with `rg -l "Manage the project task queue" skills .codex 2>/dev/null`
- Modify: `templates/dataset.md` (and `science-model/src/science_model/templates/dataset.md` if it exists per the templates packaging convention) — add the new `availability` and `available_after` fields with HTML hint comments

- [ ] **Step 1: Locate and read current docs**

```bash
rg -n "tasks block|blocked-by" commands skills 2>/dev/null
ls templates/dataset.md science-model/src/science_model/templates/dataset.md 2>/dev/null
```

Expected: identifies the files mentioning blocker semantics, plus confirms whether a packaged template copy exists.

- [ ] **Step 2: Update `commands/tasks.md`**

Edit the section that documents `block <task_id> --by <blocker_id>`:

```markdown
### "block <task_id> --by <typed-ref> [--by <typed-ref>...]"

Block a task by one or more **typed entity references** (`<kind>:<local-id>`).
Refs must resolve to known local entities. Repeatable.

- `--force` records the ref even if the entity is not yet known (e.g.
  you plan to create the dataset shortly). The unresolved reference will
  be flagged by `science graph audit`.
- Blockers are validated at write time. Untyped strings (legacy form) are
  rejected. Use `science tasks fix-blockers` to retype existing
  legacy blockers.

### "blockers <task_id>"

Show per-blocker readiness for a task. `--format json` for scripting.

### "fix-blockers"

Interactive sweep to retype legacy untyped blockers in `tasks/active.md`.
`--dry-run` lists what would change without modifying files.
```

Also update the existing "block_by dependencies" guidance in the Execution Guidance section to reference typed refs and the new commands.

- [ ] **Step 3: Update the tasks skill**

In the skill (path from Step 1), apply the same documentation updates: replace any single-blocker `--by` form, mention `--force`, mention `tasks blockers` and `tasks fix-blockers`. Keep wording aligned with the command doc.

- [ ] **Step 4: Update `templates/dataset.md`**

In the dataset template's frontmatter `access:` block, add the new fields with hint comments:

```yaml
access:
  level: ""              # public | registration | controlled | commercial | mixed
  availability: "available"   # available | embargoed | withdrawn
  available_after: ""    # free-form window (ISO date when known, else e.g. "2026-Q3", "after Lee2026 publication"). Only set when availability is "embargoed".
  verified: false
  # … existing fields …
```

If `science-model/src/science_model/templates/dataset.md` exists per the template-packaging convention introduced by the templates plan, apply the same edit there. Add a verification step:

```bash
diff templates/dataset.md science-model/src/science_model/templates/dataset.md
```

Expected: no diff (per the existing test `test_root_and_packaged_migrated_templates_match` if `dataset` is migrated; otherwise the two copies just need to be hand-kept in sync per the templates plan's pattern).

- [ ] **Step 5: Run all tests one more time**

```bash
uv run --frozen pytest science-model/tests/ science/tests/ -q
```

Expected: PASS across the board. Investigate and fix any failures before committing.

- [ ] **Step 6: Static checks**

```bash
uv run --frozen ruff check science-model/src/science_model science/src/science_tool
uv run --frozen pyright science-model/src/science_model science/src/science_tool
```

Expected: PASS. Common issues: unused imports in the CLI module, or a resolver annotation that names the concrete tool-layer class instead of the `ReadinessResolverProtocol`.

- [ ] **Step 7: End-to-end smoke**

```bash
tmpdir="$(mktemp -d)"
cat > "$tmpdir/science.yaml" <<'EOF'
name: "blockers-smoke"
id: smoke
role: research
profile: research
layout_version: 2
status: active
created: "2026-05-03"
last_modified: "2026-05-03"
EOF
mkdir -p "$tmpdir/doc/datasets" "$tmpdir/tasks"
cat > "$tmpdir/doc/datasets/embargoed.md" <<'EOF'
---
id: "dataset:embargoed"
type: "dataset"
title: "Embargoed example"
status: "active"
origin: "external"
access:
  level: "controlled"
  availability: "embargoed"
  available_after: "2026-Q3"
  verified: false
---
# Embargoed example
EOF
(
  cd "$tmpdir"
  uv run --project ~/d/science/science science tasks add "Use embargoed data" --priority P1
  uv run --project ~/d/science/science science tasks block t001 --by dataset:embargoed
  uv run --project ~/d/science/science science tasks show t001
  uv run --project ~/d/science/science science tasks blockers t001 --format json
)
```

Expected:
- `tasks block` exits 0 and prints `[t001] blocked by dataset:embargoed`.
- `tasks show` includes `dataset:embargoed`, `embargoed`, and `2026-Q3`.
- `tasks blockers --format json` returns `{"task_id": "t001", "blockers": [{"ref": "dataset:embargoed", "ready": false, "state": "embargoed", "detail": "available_after: 2026-Q3", "unresolved": false}]}`.

- [ ] **Step 8: Commit**

```bash
git add commands/tasks.md skills templates science-model/src/science_model/templates
git commit -m "docs: document typed blockers, --force, blockers, fix-blockers, dataset availability"
```

---

## Self-Review of the Plan

- **Spec coverage:** Each spec section maps to at least one task —
  - `Readiness` protocol & resolver → Tasks 2, 4
  - `AccessBlock` extension → Task 1
  - `DatasetEntity.readiness()` external + derived → Task 3 (external/derived shape) + Task 4 (resolver-driven derived)
  - `WorkflowRunEntity.readiness()` → Task 2
  - Storage stays `list[str]` → Task 7 (validation routes through helper, no schema change)
  - Single-project scope → enforced by `validate_blocker_refs` only loading local entities (Task 5)
  - Block CLI repeatable + `--force` → Task 8
  - Display nudge + per-blocker → Tasks 11, 12
  - `tasks blockers` introspection → Task 9
  - `tasks fix-blockers` migration → Task 10
  - Validation table → Tasks 5, 6, 7
  - Documentation → Task 13
- **Placeholder scan:** None of "TBD"/"TODO"/"add appropriate error handling"/"similar to Task N". Repo-specific helper names and CLI signatures are pinned to the current codebase.
- **Type consistency:** `Readiness(ready, state, detail)` shape matches across Tasks 2/3/4/9/11/12. `ReadinessResolver` uses `ProjectEntity` lookup and satisfies `ReadinessResolverProtocol` structurally. `validate_blocker_refs(project_root, refs, *, force=False) -> list[str]` matches across Tasks 5/7/8. `block_task(project_root, tasks_dir, task_id, blocked_by: list[str], *, force=False)`, `add_task(project_root, tasks_dir, ...)`, and `edit_task(project_root, tasks_dir, ...)` match across Tasks 7/8. `tasks list --format=json` preserves the existing rows/meta envelope; per-blocker JSON shape `{ref, ready, state, detail, unresolved}` matches across Tasks 9 and 11.
- **Commit cadence:** 13 commits, one per task, scoped narrowly enough to revert any one without unwinding others.
