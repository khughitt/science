# Typed Entity Blockers Design

> **Status:** design spec, not yet an implementation plan. The implementation plan (Task 1, Task 2, …) is produced by `superpowers:writing-plans` from this document.

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


class ProjectEntity(Entity):
    # … existing fields …

    def readiness(self, resolver: "ReadinessResolver | None" = None) -> Readiness:
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
# science-tool: tasks_readiness.py

class ReadinessResolver:
    """Looks up entities by id and tracks the visited set for cycle protection.

    Constructed per CLI invocation with a snapshot of the local entity store;
    not shared across invocations. Caches resolved readiness within its own
    lifetime so the same blocker referenced N times costs one resolution.
    """

    def __init__(self, lookup: Callable[[str], Entity | None]):
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
- All other entities use the default.

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

Rationale: cross-project resolution is explicitly deferred per `docs/federation.md:99`. The current `_audit_reference` path (`science-tool/src/science_tool/graph/migrate.py:316`) is called without `allow_cross_project_address`, and the resolver (`science-tool/src/science_tool/graph/reference_resolution.py:30`) only knows aliases for loaded local entities. Designing cross-project blockers properly requires settling the cross-project address syntax, the resolver source (live entity-store sweep vs. federated graph snapshot), stale-graph behavior, and audit semantics — all of which belong to the federation workstream rather than this spec.

Cross-project blockers move to the trajectory section, conditional on cross-project entity resolution landing first.

---

## CLI & Display Surface

### Block command

`science-tool tasks block <task_id> --by <typed-ref>`:

- **Strict typing.** Rejects untyped strings: `--by some-string` → error `"blocker must be typed: <kind>:<local-id> (e.g. dataset:foo, task:t007)"`.
- **Strict resolution.** Validates the ref resolves to a known entity in the local project (cross-project refs are out of scope; see trajectory item 1). If not: error with create-stub hint: `"unknown entity dataset:foo. Create it first with: science-tool dataset create …"`.
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

`science-tool tasks blockers <task_id>`:

- Default: prints per-blocker readiness as a table.
- `--format=json`: machine-readable output, **always includes per-blocker readiness** (`ref`, `ready`, `state`, `detail`, `unresolved` flag). Useful for scripting and for the future auto-unblock sweep.

`science-tool tasks list --format=json` likewise includes a `blocked_by_readiness` array per blocked task with the same shape, so scripted callers don't have to issue per-task follow-up calls.

### Legacy migration command

`science-tool tasks fix-blockers`:

- Interactive sweep of all tasks with stored untyped blockers.
- For each, prompts the user to either retype (e.g., `cleanup-old-data` → `task:t017`) or `--force`-keep with a note.

---

## Validation Rules & Service Boundary

### Helper

A single task-layer helper owns ref validation; CLI `block`/`add`/`edit` all route through it:

```python
# science-tool/src/science_tool/tasks_blockers.py

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

`block_task`, `update_task`, and `create_task` (in `science-tool/src/science_tool/tasks.py`) gain a `project_root: Path` parameter so they can call `validate_blocker_refs`. The CLI commands already have `project_root` available; threading it down is a small change.

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

**Data.** No automatic rewrite of existing `tasks/active.md` files. Read-path warnings surface legacy untyped blockers; `science-tool tasks fix-blockers` provides an interactive retype flow.

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

### 2. `science-tool` task layer + resolver tests (`tests/test_tasks_blockers.py`, `tests/test_readiness_resolver.py`)

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
| `science-tool/src/science_tool/tasks.py` | Thread `project_root` into `block_task` / `update_task` / `create_task`; route blocker writes through `validate_blocker_refs`; add `parse_tasks_for_cli` wrapper. `parse_tasks` itself stays clean |
| `science-tool/src/science_tool/tasks_blockers.py` | New: `validate_blocker_refs`, `BlockerValidationError` |
| `science-tool/src/science_tool/tasks_readiness.py` | New: `ReadinessResolver` |
| `science-tool/src/science_tool/cli.py` | Repeatable `--by`, `--force`; new `tasks blockers` and `tasks fix-blockers` commands; CLI commands call `parse_tasks_for_cli` |
| `science-tool/src/science_tool/tasks_display.py` | Construct `ReadinessResolver`, resolve and render readiness, add nudge |
| `science-tool/tests/test_tasks_blockers.py` | New |
| `science-tool/tests/test_readiness_resolver.py` | New |
| `science-tool/tests/test_tasks_cli.py` | Extend |
| `science-tool/tests/test_tasks_display.py` | Extend |
| `commands/tasks.md` | Document typed-ref convention; mention `--force` and `fix-blockers` |
| `skills/science/tasks/SKILL.md` (or whichever path holds the active tasks skill) | Same |
| `templates/dataset.md` (if it exists) | Add `availability` field with default and HTML hint |

---

## Out of Scope (Trajectory)

These are named so the future direction is documented. **None are built in this spec.**

1. **Cross-project blockers.** A task in project A blocked by an entity in project B (sibling/parent/child). Requires settling: the cross-project address syntax, the resolver source (live entity-store sweep across federated peers vs. federated graph snapshot), stale-graph behavior, and audit semantics. Belongs to the federation workstream; lands when cross-project entity resolution lands. The single-project blocker design here generalizes naturally — `validate_blocker_refs` and `ReadinessResolver` both grow a project-scope parameter.
2. **Auto-unblock sweep.** A command that flips `status: blocked → active` for tasks whose blockers all report `ready`. Defer until manual workflow validates the readiness signal — premature automation here risks confusing flicker behavior.
3. **Generalized graph operations primitives** — subgraph extraction, fold/aggregate over a subgraph, registered per-entity properties. Extract when a second concrete consumer (uncertainty diffusion, dependency-graph planning, knowledge-gap detection) appears, not before.
4. **Graph substrate unification** — single conceptual schema with project-local lazy materialization plus explicit federated build. Significant design surface (especially the strict-vs-tolerant materialization-failure question). Justified when consumers beyond blockers (inquiries, knowledge-gap detection, uncertainty diffusion) accumulate.
5. **Typed cross-project edge vocabulary** — `depends-on`, `cites-as-context`, `conditions-on`, `boundary-condition`, `ambient-influence`. Blockers are the first concrete `depends-on` instance; the broader vocabulary lands when a second intent class needs to be expressed.
6. **Federation-status discovery tooling** — `science-tool federation status` showing parent/peer updates relative to local state.
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
- **Internal consistency.** `Readiness` shape (`bool + state + detail`) consistent across entity overrides, `ReadinessResolver`, CLI display, `tasks blockers --format=json`, and `tasks list --format=json`. `AccessBlock.availability` and `exception.mode` semantics match across the entity validator, dataset readiness override, display strings, and tests. `ReadinessResolver` is the single owner of cross-entity lookup, cycle protection, and per-invocation caching.
- **Scope.** Single-project, single-spec scope: data-model extension + readiness protocol/resolver + validation helper + CLI/display surface. Cross-project blockers, auto-unblock, and graph-substrate work are explicitly deferred. Sized for one implementation plan.
- **Service boundary.** `validate_blocker_refs` is the single owner of ref validation; `block_task` / `update_task` / `create_task` route through it. `ReadinessResolver` is the single owner of readiness resolution; entity `readiness()` methods are pure local logic plus optional resolver delegation. `parse_tasks` stays pure; `parse_tasks_for_cli` is the warning-surfacing wrapper.
- **Workflow-run rule.** Pinned to `status == "complete"` (matches the existing template vocabulary). No deferral.
- **Cross-project blockers.** Explicitly out of scope; promoted to trajectory item 1 with prerequisites named.
