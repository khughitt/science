# Convergence Phase 5 — Health Checks Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 16 inline health-check bodies out of `graph/health.py` (1,983 lines) into a `graph/health_checks/` package — one module per check — leaving `health.py` holding only the registry, selection, and report assembly, and land a structural guard that stops the checks from growing back inline.

**Architecture:** `graph/health_checks/base.py` holds the shared machinery (`HealthContext`, `HealthCheck`, `HealthTiming`, `context_sources`, and the one constant two checks share). Each of the 16 checks becomes `graph/health_checks/<name>.py` exporting a single `CHECK: HealthCheck` alongside its own helpers and result TypedDicts. `graph/health_checks/__init__.py` imports the 16 modules and assembles `HEALTH_CHECKS` as an explicit ordered tuple. `health.py` imports downward into the package and keeps `build_health_report`, `_select_health_checks`, `_run_health_checks`, `list_health_checks`, and the report-level types.

The import DAG is strictly one-way and acyclic:

```
base.py  <-  health_checks/<check>.py  <-  health_checks/__init__.py  <-  health.py  <-  health_cli.py
```

**Tech Stack:** Python 3.12+, click, pytest, uv. Mirrors the existing `validate/checks/` package convention (explicit module list, no filesystem discovery, shared context object defined outside the check bodies).

## REBASED ONTO MAIN — read this before anything else

This plan was first written against `5bc57f49` and executed to completion. While
it ran, `main` advanced 17 commits landing the **InstrumentResult convergence**
(merge `fe2fb83b`), which rewrote the body of **every one of the 16 health
collectors** in place so they return `InstrumentResult[Row]` instead of a bare
`list`/`dict`.

The two changes are conceptually orthogonal — that branch changed each
collector's *body*, this one changes its *home* — but they collide textually. A
naive merge was measured and produces a **duplicate of every collector**: main's
new body re-added to `health.py`, plus this branch's stale pre-InstrumentResult
copy in `health_checks/`, with the registry wired to the *stale* one. That is
precisely the duplicate-that-drifts defect this convergence program exists to
eliminate. So the extraction is being **re-run on top of main** instead.

The plan's architecture survives unchanged — main's `health.py` (now 2,129 lines)
still has the identical seams (`HealthContext`, `HealthCheck`, `HEALTH_CHECKS`,
`_select_health_checks`, `_empty_check_results`, `build_health_report`). The facts
below were **re-derived from main**, not carried over. Three things changed:

1. **Six new symbols**, zero removed. Two are shared across *three* checks each
   and therefore belong in `base.py` — reusing the old map would have duplicated
   them. See the Symbol ownership map.
2. **The collectors now return `InstrumentResult[...]`.** This changes nothing
   about the move: bodies still move VERBATIM. `InstrumentResult` is imported from
   `science_tool.instruments`, a separate module, so it introduces no new cycle.
3. **A new guard couples to file paths** (`tests/test_instrument_boundary.py`) and
   a new scope list (`instruments.py::INSTRUMENT_MODULES`) names `graph/health.py`.
   Both must be re-keyed as the collectors move, or the instrument guard silently
   stops covering them. This is a new task (Task 0) and it is load-bearing.

`_empty_check_results` on main is **still** a hard-coded 16-name list, so Task 2's
registry fold remains an unclaimed win.

The pre-rebase branch is preserved at `design/convergence-phase5-preinstrument`
(9 tasks, all reviews clean, guard proven) for reference.

## Global Constraints

Every task's requirements implicitly include this section.

- **`science health --format json` stdout must stay byte-identical** — measured
  against `main` (`fe2fb83b`), NOT against the old base. Run the snapshot suite
  (`uv run --frozen pytest -m snapshot`) at **each** commit, not just at the end.
- **Do not alter any collector's behavior or return type.** The InstrumentResult
  migration is main's work and is already landed. This branch only *moves* code.
  If you find yourself editing a collector body, stop — you are out of scope.
- **The instrument-boundary guard must not lose coverage.** `INSTRUMENT_MODULES`
  (`science/src/science_tool/instruments.py:41`) is the scope of
  `tests/test_instrument_boundary.py`. It currently lists `graph/health.py`. As the
  16 collectors move out, their new modules must ENTER that list, or the guard
  silently stops checking the very functions it was built to check. Coverage may
  never narrow.
- **No module under `graph/health_checks/` may import from `science_tool.graph.health`.** That is the circular import. Check modules import from `health_checks/base.py`. This is the single most important structural rule in this phase, and the Phase 4 guard exists because the same trap was hit there.
- **`HEALTH_CHECKS` order must be preserved exactly.** It drives check execution order and the order of the `_meta.timings` list. Reordering it is an observable change.
- **No compatibility or re-export shims.** When a symbol moves out of `health.py`, its consumers (tests, `health_cli.py`) import it from its new home. Do not re-export moved symbols from `health.py` to spare a caller an edit. (Project rule: no legacy/compatibility layers unless asked.)
- **No `Unified` prefix** on any new component name.
- Composition over inheritance; explicit over defensive; fail early instead of silent fallbacks.
- **No AI-attribution trailers** on commits (no `Co-Authored-By:`, no "Generated with Claude Code").
- `science_model` must never import `science_tool`.
- Run all commands from `science/` (there is no root `pyproject.toml`):
  - `cd science && uv run --frozen pytest`
  - `cd science && uv run ruff check && uv run pyright`
- **Never use `git stash`** (a prior session lost unrelated work to a silently-failing `git stash push` + `git stash pop`).
- **Never run pytest as a background job.** Run every verification command in the foreground and wait for it.

## Verification gate (run before every commit)

```bash
cd science
uv run --frozen pytest                    # full suite, foreground
uv run --frozen pytest -m snapshot        # byte-identity gate
uv run ruff check
uv run pyright
```

Pyright must report **0 errors**. If the harness surfaces `reportMissingImports`
diagnostics, ignore them — they come from a pyright run without `science/.venv`.
`uv run pyright` from `science/` is the authoritative check.

---

## Deviations from the design doc (deliberate)

The design doc's Phase 5 section was written from a read of the file, not from a
call graph. Three of its statements do not survive contact with the code. These
deviations are intentional; do not "correct" them back.

1. **`HealthContext` and `HealthCheck` move to `health_checks/base.py`.** The doc
   says `health.py` retains them. It cannot: the check modules need
   `HealthContext` for their `run` signature, and `health.py` imports the check
   modules — that is an import cycle. This is precisely the trap Phase 4 hit, and
   the fix is the same one (`typed_entity_cli.py` there, `base.py` here): the
   shared support lands first, in a module both sides can import. This is also
   how `validate/` already does it — `ValidateContext` lives in
   `validate/context.py`, outside `validate/checks/`.

2. **"No check calls another" is false for one symbol.**
   `_IDENTITY_REFERENCE_FIELDS` is read by two checks. It goes to `base.py`.

3. **`HealthCheck` gains an `empty` field** (not in the doc). The doc did not
   notice `_empty_check_results`, a second hard-coded list of all 16 check names.
   Leaving it would mean a check module and a dict literal in `health.py` both
   have to know every check — exactly the half-applied-registry pattern this whole
   convergence program exists to remove.

## Facts established by audit (do not re-derive)

These were computed from the current tree with an AST call-graph pass. Trust them.

**Consumers of `health.py` are few.** In `src/`, exactly **one** module imports it:
`graph/health_cli.py:66` → `from science_tool.graph.health import archive_lag_total, build_health_report, list_health_checks`.
`build_health_report` and `list_health_checks` stay in `health.py`. **`archive_lag_total` moves** (Task 7), so that one import line must be split.

**Test white-box imports that will break as symbols move** (all others import
`build_health_report` / `HEALTH_CHECKS`, which stay put):

| Symbol | Moves to | Test sites |
|---|---|---|
| `collect_unresolved_refs` | `health_checks/unresolved_refs.py` | `test_health.py:262,290,305,321`; `test_identity_audit_entrypoints.py:5` |
| `collect_lingering_tags` | `health_checks/lingering_tags.py` | `test_health.py:341,364` |
| `collect_unregistered_ref_kinds` | `health_checks/unregistered_ref_kinds.py` | `test_health.py:982` |
| `check_dataset_anomalies` | `health_checks/dataset_anomalies.py` | `test_health.py:21` |
| `DATASET_ANOMALY_CODES` | `health_checks/dataset_anomalies.py` | `test_health.py:1768` |
| `collect_tooling_scaffold_findings` | `health_checks/tooling_scaffold.py` | `test_health.py:1625` |
| `collect_legacy_task_type` | `health_checks/legacy_task_type.py` | `test_health.py:1697` |
| `collect_invalid_entity_aspects` | `health_checks/invalid_entity_aspects.py` | `test_health.py:1713` |
| `archive_lag_total` | `health_checks/archive_lag.py` | `test_health.py:1079`; `graph/health_cli.py:66` |

**Line numbers above are re-derived from main and are still approximate — grep.**
Main shifted `test_health.py` (`collect_tooling_scaffold_findings` is now ~1662,
`collect_legacy_task_type` ~1734, `collect_invalid_entity_aspects` ~1750,
`DATASET_ANOMALY_CODES` ~1805).

**NEW consumer main added — `tests/test_health_preconditions.py:19`** imports TEN
collectors in one block:
`build_health_report`, `check_dataset_anomalies`, `collect_agent_context_findings`,
`collect_identity_policy_findings`, `collect_invalid_entity_aspects`,
`collect_legacy_task_type`, `collect_lingering_tags`,
`collect_tooling_scaffold_findings`, `collect_unregistered_ref_kinds`,
`collect_unresolved_refs`, `collect_validation_findings`.
All but `build_health_report` move. Split that import across the tasks that move
each collector — by Task 7 it should name only `build_health_report`.

`tests/test_cli_color_policy.py:149,163` monkeypatches
`health_module.build_health_report` — `build_health_report` stays in `health.py`, so
**that file needs no change.** Do not touch it.

**One constant is shared by two checks.** `_IDENTITY_REFERENCE_FIELDS`
(`health.py:1085`) is read by `_collect_entity_identity_findings` (the
`identity_policy` check) **and** by `collect_unregistered_ref_kinds` (the
`unregistered_ref_kinds` check). The design doc's claim that "no check calls
another" is wrong on exactly this one symbol. It goes in `base.py` as public
`IDENTITY_REFERENCE_FIELDS`. Do **not** duplicate it into two check modules.

**`_empty_check_results` is a third copy of the check-name list.**
`health.py:656` hard-codes all 16 names in a **different order** than
`HEALTH_CHECKS`. Its `check_results` dict is only an intermediate lookup — the
JSON key order comes from the explicit `report` dict literal at `health.py:819` —
so rebuilding `_empty_check_results` from the registry is **byte-safe**. Task 2
does this and deletes the duplicate list.

---

## Symbol ownership map

Every top-level symbol in `health.py`, and where it ends up. Derived from the call
graph; a symbol goes to the check that is its only caller.

**`health_checks/base.py`** (shared machinery — Task 1)
`HealthContext`, `HealthCheck`, `HealthTiming`, `_T`, `context_sources` (public
rename of `_context_sources`), `IDENTITY_REFERENCE_FIELDS` (public rename of
`_IDENTITY_REFERENCE_FIELDS`), and — **new on main** —
`PROJECT_SOURCES_EMPTY` (was `_PROJECT_SOURCES_EMPTY`) and
`NO_ENTITIES_REASON` (was `_NO_ENTITIES_REASON`).

Those last two are the InstrumentResult `unwired` code/reason pair, read by
**three** checks (`identity_policy`, `unregistered_ref_kinds`, `unresolved_refs`):

```python
return InstrumentResult.unwired(code=PROJECT_SOURCES_EMPTY, reason=NO_ENTITIES_REASON)
```

They are shared, so they live in `base.py` and are imported. **Do not copy them
into three check modules** — three copies of an error string is the exact defect
class this phase exists to remove, and they would drift the first time one is
reworded.

**Stays in `health.py`** (registry driver + report assembly)
`HealthReport`, `HealthMeta`, `SchemaInvalidFinding`, `LayeredClaimIssue`,
`RivalModelGap`, `CoverageMetric`, `LayeredClaimHealthReport`,
`AcceptedValidationFinding`, `_coverage_metric`,
`_partition_accepted_validation_findings`, `_accepted_validation_entries`,
`_accepts_validation_finding`, `_text_matches`, `_health_check_names`,
`list_health_checks`, `_select_health_checks`, `_run_health_checks`,
`_empty_check_results`, `build_health_report`, and — **new on main** —
`UnwiredCheck` (report-level TypedDict) and `_drain_instrument_results` (report
assembly; its only caller is `build_health_report`).

**Moves to `health_checks/<module>.py`** — the module owns its collector, its
private helpers, its regex/constant literals, and its result TypedDicts:

| Module | Symbols it takes from `health.py` |
|---|---|
| `unresolved_refs.py` | `collect_unresolved_refs`, `_classify`, `_HYPOTHESIS_ID_RE`, `_QUESTION_ID_RE`, `_TASK_ID_RE`, `UnresolvedRef` |
| `unregistered_ref_kinds.py` | `collect_unregistered_ref_kinds`, `_is_registered_peer_address`, `_string_refs`, `_BIBLIOGRAPHY_REFERENCE_FIELDS`, `UnregisteredRefKind`, `_UnregisteredRefKindAccumulator` |
| `lingering_tags.py` | `collect_lingering_tags`, `_extract_frontmatter_block`, `_parse_list_body`, `_FRONTMATTER_BLOCK_RE`, `_FRONTMATTER_TAGS_RE`, `_TASK_TAGS_RE`, `LingeringTagsRecord`, **`_LINGERING_TAGS_SCAN_DIRS`** (new on main) |
| `identity_policy.py` | `collect_identity_policy_findings`, `_collect_entity_identity_findings`, `_coerce_external_curie`, `IdentityPolicyFinding`, `_IDENTITY_REQUIRED_KINDS`, `_TAXON_REQUIRED_KINDS`, `_LOCAL_ID_RE` |
| `entity_identity.py` | `_collect_entity_identity`, `_entity_identity_finding`, `EntityIdentityFinding` |
| `dataset_anomalies.py` | `check_dataset_anomalies`, `_load_research_packages`, `_load_runtime_pkg`, `_load_workflow_runs`, `_passes_gate`, `DATASET_ANOMALY_CODES` |
| `agent_context.py` | `collect_agent_context_findings`, `_claude_md_is_minimal`, `AgentContextFinding`, `OVERVIEW_LINE_BUDGET`, `OVERVIEW_WORD_BUDGET`, **`_AGENT_CONTEXT_FILES`** (new on main) |
| `tooling_scaffold.py` | `collect_tooling_scaffold_findings`, `ToolingScaffoldFinding` |
| `validate.py` | `collect_validation_findings`, `_validation_health_severity`, `ValidationFinding` |
| `legacy_task_type.py` | `collect_legacy_task_type`, `LegacyTaskTypeFinding` |
| `invalid_entity_aspects.py` | `collect_invalid_entity_aspects`, `InvalidEntityAspectsFinding` |
| `archive_lag.py` | `_collect_archive_lag`, `archive_lag_total`, `TaskArchiveLag` |
| `managed_artifacts.py` | `_collect_managed_artifacts`, `_project_relative_sidecar` |
| `prose_epistemics.py` | `_collect_prose_epistemics`, `_empty_prose_epistemics` |
| `cross_paper_evidence.py` | `_collect_cross_paper_evidence`, `_cross_paper_empty_state`, `_empty_cross_paper_evidence_health`, `CrossPaperEvidenceFinding`, `CrossPaperEvidenceHealthReport` |
| `layered_claim_migration.py` | `_empty_layered_claim_migration_report` (the `run` is a thin wrapper over `build_layered_claim_migration_report`, imported from its existing module) |

Note `_project_relative_sidecar` is called by `_collect_cross_paper_evidence`, not
by `_collect_managed_artifacts` — it goes to `cross_paper_evidence.py`. (Corrected
from the naming coincidence; verify against the call graph if in doubt.)

**`AcceptedValidationFinding` subclasses `ValidationFinding`**, which moves to
`validate.py`. `health.py` keeps `AcceptedValidationFinding` and imports
`ValidationFinding` from `health_checks/validate.py`.

**`HealthReport` (staying in `health.py`) structurally references many per-check
TypedDicts.** After the move, `health.py` imports them from the check modules.
That is a downward import and is fine.

---

### Task 1: Shared machinery — `health_checks/base.py`

Land the package and its shared base **before** moving any check. This is the
move that makes the whole phase acyclic: without it, every check module would
have to import `HealthContext` from `health.py`, which imports the checks.

**Files:**
- Create: `science/src/science_tool/graph/health_checks/__init__.py`
- Create: `science/src/science_tool/graph/health_checks/base.py`
- Modify: `science/src/science_tool/graph/health.py`
- Test: `science/tests/test_health_checks_base.py`

**Interfaces:**
- Produces (all later tasks consume these):
  ```python
  # science_tool/graph/health_checks/base.py
  _T = TypeVar("_T")

  class HealthTiming(TypedDict):
      name: str
      duration_seconds: float

  @dataclass
  class HealthContext:
      project_root: Path
      collect_timings: bool = False
      sources: ProjectSources | None = None
      selected_checks: tuple[HealthCheck, ...] = ()
      timings: list[HealthTiming] = dataclass_field(default_factory=list)

      def run(self, name: str, fn: Callable[[], _T]) -> _T: ...

  @dataclass(frozen=True)
  class HealthCheck:
      name: str
      description: str
      requires_sources: bool
      run: Callable[[HealthContext], object]

  def context_sources(context: HealthContext) -> ProjectSources:
      """Raise if a check that requires sources ran without them."""

  IDENTITY_REFERENCE_FIELDS: tuple[str, ...]
  ```

- [ ] **Step 1: Write the failing test**

`science/tests/test_health_checks_base.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest


def test_context_sources_raises_without_sources() -> None:
    from science_tool.graph.health_checks.base import HealthContext, context_sources

    context = HealthContext(project_root=Path("/tmp"))
    with pytest.raises(RuntimeError, match="health check requires loaded project sources"):
        context_sources(context)


def test_health_module_reuses_the_base_types() -> None:
    """health.py must not define its own copies of the shared machinery."""
    from science_tool.graph import health
    from science_tool.graph.health_checks import base

    assert health.HealthContext is base.HealthContext
    assert health.HealthCheck is base.HealthCheck


def test_identity_reference_fields_is_shared() -> None:
    """Two checks read this constant; it lives in exactly one place."""
    from science_tool.graph.health_checks.base import IDENTITY_REFERENCE_FIELDS

    assert "related" in IDENTITY_REFERENCE_FIELDS
    assert "source_refs" in IDENTITY_REFERENCE_FIELDS
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd science && uv run --frozen pytest tests/test_health_checks_base.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.graph.health_checks'`.

- [ ] **Step 3: Create `base.py`**

Move — **verbatim, changing only names and imports** — these symbols out of
`health.py` into `graph/health_checks/base.py`: `_T`, `HealthTiming`,
`HealthContext`, `HealthCheck`, `_context_sources` (rename to public
`context_sources`), `_IDENTITY_REFERENCE_FIELDS` (rename to public
`IDENTITY_REFERENCE_FIELDS`). Keep the bodies byte-for-byte; do not "improve" them.

`base.py` imports `ProjectSources` from wherever `health.py` imports it today —
copy that import line exactly.

- [ ] **Step 4: Create `health_checks/__init__.py`**

For this task it only re-exports the base names. The `HEALTH_CHECKS` tuple arrives
in Task 8.

```python
"""Health checks, one module per check.

`HEALTH_CHECKS` is assembled by explicit import in this module — never by
filesystem discovery, which would make check order implicit.
"""

from __future__ import annotations

from science_tool.graph.health_checks.base import (
    HealthCheck,
    HealthContext,
    HealthTiming,
    context_sources,
)

__all__ = ["HealthCheck", "HealthContext", "HealthTiming", "context_sources"]
```

- [ ] **Step 5: Point `health.py` at the base**

Delete the six moved definitions from `health.py` and add:

```python
from science_tool.graph.health_checks.base import (
    HealthCheck,
    HealthContext,
    HealthTiming,
    IDENTITY_REFERENCE_FIELDS,
    context_sources,
)
```

Rewrite `health.py`'s internal uses: `_context_sources(` → `context_sources(`,
`_IDENTITY_REFERENCE_FIELDS` → `IDENTITY_REFERENCE_FIELDS`. There are 3 call
sites of the former (`_collect_cross_paper_evidence`, `_collect_entity_identity`,
`build_health_report`) plus 4 uses inside the `HEALTH_CHECKS` lambdas, and 2 of
the latter (`_collect_entity_identity_findings`, `collect_unregistered_ref_kinds`).
Grep to confirm you got them all — do not rely on this count.

- [ ] **Step 6: Run the gate**

Run the full verification gate from the top of this document. All four commands
must pass, pyright with 0 errors.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/health_checks/ science/src/science_tool/graph/health.py science/tests/test_health_checks_base.py
git commit -m "Add graph/health_checks/base.py with the shared health machinery (t-phase5)"
```

---

### Task 2: Fold check empty-state into the registry

`_empty_check_results` hard-codes all 16 check names a second time, in a different
order than `HEALTH_CHECKS`. Adding a check to the registry but forgetting this dict
makes `build_health_report` raise `KeyError`. Make the registry the single source.

**Files:**
- Modify: `science/src/science_tool/graph/health_checks/base.py`
- Modify: `science/src/science_tool/graph/health.py`
- Test: `science/tests/test_health_checks_base.py` (extend)

**Interfaces:**
- Consumes: `HealthCheck` from Task 1.
- Produces: `HealthCheck` gains a required field —
  ```python
  @dataclass(frozen=True)
  class HealthCheck:
      name: str
      description: str
      requires_sources: bool
      run: Callable[[HealthContext], object]
      empty: Callable[[Path], object]   # NEW: the check's zero-value result
  ```
  Every later task that creates a `CHECK` must supply `empty`.

- [ ] **Step 1: Write the failing tests**

Two tests, with distinct jobs. The **characterization test** is the important one:
it snapshots the exact empty payload *before* the refactor, so that if the
registry-derived version produces a different value for any check, it goes red.
That is what protects byte-identity here.

Do **not** write a test asserting `set(_empty_check_results(...)) == {check.name
for check in HEALTH_CHECKS}`. Once the function is a comprehension over
`HEALTH_CHECKS` that is tautologically true and can never fail.

Append to `science/tests/test_health_checks_base.py`:

```python
def test_every_check_supplies_an_empty_state() -> None:
    """The registry carries each check's zero-value, so it is the only name list."""
    from science_tool.graph.health import HEALTH_CHECKS

    for check in HEALTH_CHECKS:
        assert callable(check.empty), f"{check.name} has no empty-state callable"


def test_empty_check_results_payload_is_unchanged() -> None:
    """Characterization: pins the exact empty report across the registry refactor.

    Values transcribed from health.py's `_empty_check_results` dict literal as it
    stood before Phase 5. A diff here is a `health --format json` byte change.
    """
    from science_tool.graph.health import _empty_check_results

    assert _empty_check_results(Path("/tmp/project")) == {
        "identity_policy": [],
        "entity_identity": [],
        "layered_claim_migration": {
            "project_root": "/tmp/project",
            "rows": [],
            "summary": {
                "proposition_count": 0,
                "authored_claim_layer_count": 0,
                "authored_identification_strength_count": 0,
                "warning_count": 0,
                "todo_count": 0,
            },
        },
        "cross_paper_evidence": {
            "status": "ok",
            "empty_state": "no_propositions",
            "summary": {
                "propositions": 0,
                "propositions_with_units": 0,
                "units": 0,
                "faults": 0,
                "faults_by_reason": {},
                "contested": 0,
            },
            "findings": [],
            "propositions": [],
        },
        "archive_lag": {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
        "managed_artifacts": [],
        "tooling_scaffold": [],
        "validate": [],
        "unresolved_refs": [],
        "unregistered_ref_kinds": [],
        "lingering_tags": [],
        "agent_context": [],
        "dataset_anomalies": [],
        "legacy_task_type": [],
        "invalid_entity_aspects": [],
        "prose_epistemics": _empty_prose_epistemics_expected(),
    }
```

`_empty_prose_epistemics_expected()` is a local helper in the test file returning
whatever `health._empty_prose_epistemics()` returns today — read that function and
transcribe its literal rather than calling the production function (calling it
would make the assertion circular).

- [ ] **Step 2: Run and watch the first fail, the second pass**

```bash
cd science && uv run --frozen pytest tests/test_health_checks_base.py -v
```
Expected:
- `test_every_check_supplies_an_empty_state` → **FAIL**, `AttributeError: 'HealthCheck' object has no attribute 'empty'`.
- `test_empty_check_results_payload_is_unchanged` → **PASS** already. That is
  correct and intended: it is a characterization test whose job is to stay green
  through Steps 3-5. If it goes red during this task, you changed the payload —
  stop and fix, do not update the expectation.

- [ ] **Step 3: Add the `empty` field to `HealthCheck`**

In `base.py`, add `empty: Callable[[Path], object]` as a required field.

- [ ] **Step 4: Supply `empty=` on all 16 registry entries**

In `health.py`'s `HEALTH_CHECKS` tuple, add `empty=` to each entry, taking the
value from the current `_empty_check_results` dict literal **exactly**:

- `identity_policy`, `entity_identity`, `managed_artifacts`, `tooling_scaffold`,
  `validate`, `unresolved_refs`, `unregistered_ref_kinds`, `lingering_tags`,
  `agent_context`, `dataset_anomalies`, `legacy_task_type`,
  `invalid_entity_aspects` → `empty=lambda _root: []`
- `archive_lag` → `empty=lambda _root: {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0}`
- `layered_claim_migration` → `empty=_empty_layered_claim_migration_report`
- `cross_paper_evidence` → `empty=lambda _root: _empty_cross_paper_evidence_health()`
- `prose_epistemics` → `empty=lambda _root: _empty_prose_epistemics()`

- [ ] **Step 5: Derive `_empty_check_results`**

Replace the whole 19-line dict literal with:

```python
def _empty_check_results(project_root: Path) -> dict[str, object]:
    return {check.name: check.empty(project_root) for check in HEALTH_CHECKS}
```

Delete nothing else — `_empty_layered_claim_migration_report`,
`_empty_cross_paper_evidence_health`, and `_empty_prose_epistemics` are still
referenced, now as the `empty` callables. They move to their check modules in
Tasks 6 and 7.

- [ ] **Step 6: Run the gate**

The full gate. The snapshot suite is the one that proves byte-identity here — if
`health --format json` changed, `-m snapshot` goes red.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/health.py science/src/science_tool/graph/health_checks/base.py science/tests/test_health_checks_base.py
git commit -m "Derive empty check results from the registry, killing the duplicate name list (t-phase5)"
```

---

## Tasks 3-7: move the 16 checks

**These five tasks share one procedure.** Read it once; each task below only names
its modules and its consumer edits.

For each check `<name>` in the task's batch:

1. Create `science/src/science_tool/graph/health_checks/<name>.py`.
2. **Move its symbols verbatim** from `health.py` (see the Symbol ownership map
   above). Change **only** the import lines — never a body. A pure code-move is
   the whole point; a "cleanup" while moving makes the diff unreviewable and puts
   byte-identity at risk.
3. The module imports what it needs from `base.py`
   (`HealthCheck`, `HealthContext`, `context_sources`, `IDENTITY_REFERENCE_FIELDS`)
   and **never** from `science_tool.graph.health`.
4. End the module with its registry entry, carrying the **exact** `name`,
   `description`, `requires_sources`, `run`, and `empty` from the current
   `HEALTH_CHECKS` entry:

   ```python
   CHECK = HealthCheck(
       name="unresolved_refs",
       description="Find project references that do not resolve to known entities.",
       requires_sources=True,
       run=lambda context: collect_unresolved_refs(
           context.project_root, sources=context_sources(context)
       ),
       empty=lambda _root: [],
   )
   ```

5. In `health.py`: delete the moved symbols, and import the module's `CHECK` plus
   any TypedDicts that `HealthReport` or `build_health_report` still reference:

   ```python
   from science_tool.graph.health_checks.unresolved_refs import CHECK as UNRESOLVED_REFS_CHECK
   from science_tool.graph.health_checks.unresolved_refs import UnresolvedRef
   ```

   Replace the corresponding inline `HealthCheck(...)` literal in `HEALTH_CHECKS`
   with the imported `UNRESOLVED_REFS_CHECK`. **Keep the tuple's order unchanged.**
6. Re-point any test/`health_cli.py` import of a moved symbol to its new module
   (the table in "Facts established by audit" lists every one). **Do not add a
   re-export to `health.py` to avoid the edit.**
7. **Keep the instrument guard's coverage.** Add the new module's path to
   `INSTRUMENT_MODULES` in `science/src/science_tool/instruments.py:41` —
   e.g. `"graph/health_checks/unresolved_refs.py"`. That tuple is the scope of
   `tests/test_instrument_boundary.py`; a collector that leaves `graph/health.py`
   without its new home entering the list stops being checked, and **nothing goes
   red** — the guard just quietly covers less. Coverage may never narrow.
   Do this in the SAME commit that creates the module, so there is no window where
   the collectors are unguarded.
   `graph/health.py` STAYS in the list (`list_health_checks` remains there).
8. Run the full verification gate. Commit.

Each of Tasks 3-7 ends with the suite green — a batch is never left half-moved.

---

### Task 3: Batch A — reference and tag checks

**Files:**
- Create: `graph/health_checks/unresolved_refs.py`, `unregistered_ref_kinds.py`, `lingering_tags.py`
- Modify: `graph/health.py`
- Modify: `science/tests/test_health.py`, `science/tests/test_identity_audit_entrypoints.py`

**Consumer edits:**
- `test_health.py:262,290,305,321` — `collect_unresolved_refs` → `from science_tool.graph.health_checks.unresolved_refs import collect_unresolved_refs`
- `test_health.py:341,364` — `collect_lingering_tags` → `...health_checks.lingering_tags import collect_lingering_tags`
- `test_health.py:982` — `collect_unregistered_ref_kinds` → `...health_checks.unregistered_ref_kinds import collect_unregistered_ref_kinds`
- `test_identity_audit_entrypoints.py:5` — split the import: `build_health_report` stays from `health`, `collect_unresolved_refs` comes from the new module.

`unregistered_ref_kinds.py` imports `IDENTITY_REFERENCE_FIELDS` from `base.py`.

- [ ] Follow the shared procedure above for the three modules.
- [ ] Run the full gate.
- [ ] Commit: `git commit -m "Extract unresolved_refs, unregistered_ref_kinds, lingering_tags health checks (t-phase5)"`

---

### Task 4: Batch B — identity checks

**Files:**
- Create: `graph/health_checks/identity_policy.py`, `entity_identity.py`
- Modify: `graph/health.py`

**Consumer edits:** none — no test imports these collectors directly (they go
through `build_health_report`). Confirm with
`grep -rn "collect_identity_policy_findings\|_collect_entity_identity" science/tests/`
before assuming; if a site exists, re-point it.

`identity_policy.py` imports `IDENTITY_REFERENCE_FIELDS` from `base.py`.
`health.py` keeps importing `EntityIdentityFinding` and `IdentityPolicyFinding`
for `HealthReport` / `build_health_report`'s casts.

- [ ] Follow the shared procedure for the two modules.
- [ ] Run the full gate.
- [ ] Commit: `git commit -m "Extract identity_policy and entity_identity health checks (t-phase5)"`

---

### Task 5: Batch C — dataset anomalies

The largest single check (`check_dataset_anomalies`, ~360 lines) plus its four
loaders. On its own so the diff stays reviewable.

**Files:**
- Create: `graph/health_checks/dataset_anomalies.py`
- Modify: `graph/health.py`
- Modify: `science/tests/test_health.py`

**Consumer edits:**
- `test_health.py:21` — `check_dataset_anomalies` → `from science_tool.graph.health_checks.dataset_anomalies import check_dataset_anomalies`
- `test_health.py:1768` — `DATASET_ANOMALY_CODES` → same module

`DATASET_ANOMALY_CODES` currently sits at `health.py:44` (module top, far from its
check). It moves into `dataset_anomalies.py`.

- [ ] Follow the shared procedure.
- [ ] Run the full gate.
- [ ] Commit: `git commit -m "Extract the dataset_anomalies health check (t-phase5)"`

---

### Task 6: Batch D — project scaffold and validation checks

**Files:**
- Create: `graph/health_checks/agent_context.py`, `tooling_scaffold.py`, `validate.py`, `legacy_task_type.py`, `invalid_entity_aspects.py`
- Modify: `graph/health.py`
- Modify: `science/tests/test_health.py`

**Consumer edits:**
- `test_health.py:1625` — `collect_tooling_scaffold_findings` → `...health_checks.tooling_scaffold import ...`
- `test_health.py:1697` — `collect_legacy_task_type` → `...health_checks.legacy_task_type import ...`
- `test_health.py:1713` — `collect_invalid_entity_aspects` → `...health_checks.invalid_entity_aspects import ...`

**Watch the name collision:** the new module is
`graph/health_checks/validate.py`, and there is an unrelated top-level
`science_tool/validate/` package. Inside `health_checks/validate.py`, import the
other one by absolute path (`from science_tool.validate... import ...`) — the
`from __future__ import annotations` + absolute-import convention already in use
makes this unambiguous, but be deliberate about it.

`health.py` keeps `AcceptedValidationFinding` (it subclasses the moved
`ValidationFinding`) and the `_partition_accepted_validation_findings` cluster —
those are report assembly, not the check.

- [ ] Follow the shared procedure for the five modules.
- [ ] Run the full gate.
- [ ] Commit: `git commit -m "Extract agent_context, tooling_scaffold, validate, legacy_task_type, invalid_entity_aspects health checks (t-phase5)"`

---

### Task 7: Batch E — task, artifact, and evidence checks

**Files:**
- Create: `graph/health_checks/archive_lag.py`, `managed_artifacts.py`, `prose_epistemics.py`, `cross_paper_evidence.py`, `layered_claim_migration.py`
- Modify: `graph/health.py`, `graph/health_cli.py`
- Modify: `science/tests/test_health.py`

**Consumer edits — this batch is the one that touches `src/`:**
- `graph/health_cli.py:66` currently reads
  `from science_tool.graph.health import archive_lag_total, build_health_report, list_health_checks`.
  Split it:
  ```python
  from science_tool.graph.health import build_health_report, list_health_checks
  from science_tool.graph.health_checks.archive_lag import archive_lag_total
  ```
- `test_health.py:1079` — `from science_tool.graph.health import archive_lag_total, build_health_report`
  splits the same way.

`health.py`'s `build_health_report` calls `archive_lag_total(archive_lag)` — it now
imports it from `health_checks/archive_lag.py`.

**Re-key the instrument-boundary allowlist.** `tests/test_instrument_boundary.py`
holds a `_NOT_INSTRUMENTS` frozenset of `(module_path, func_name)` pairs. One entry
is `("graph/health.py", "archive_lag_total")` — with a comment explaining it is pure
arithmetic over a caller-supplied dict, not an instrument. `archive_lag_total` is
moving, so that key becomes stale: change it to
`("graph/health_checks/archive_lag.py", "archive_lag_total")` and **carry the
comment across verbatim.** This is a RE-KEY, not a widening: do not add the new
entry while leaving the old one, and do not relax the assertion. The other health
entry, `("graph/health.py", "list_health_checks")`, is unchanged — that function
stays in `health.py`.

`layered_claim_migration.py` is thin: it holds
`_empty_layered_claim_migration_report` and a `CHECK` whose `run` calls
`build_layered_claim_migration_report` (imported from its existing home — copy
`health.py`'s import line).

`prose_epistemics.py` takes `_empty_prose_epistemics`, which is the `empty`
callable **and** used inside `_collect_prose_epistemics`. Both move together, so
it resolves cleanly.

- [ ] Follow the shared procedure for the five modules.
- [ ] Run the full gate.
- [ ] Commit: `git commit -m "Extract archive_lag, managed_artifacts, prose_epistemics, cross_paper_evidence, layered_claim_migration health checks (t-phase5)"`

---

### Task 8: Move `HEALTH_CHECKS` into the package

All 16 checks now live in `health_checks/`. The registry tuple can finally move
out of `health.py`, which completes the one-way DAG.

**Files:**
- Modify: `science/src/science_tool/graph/health_checks/__init__.py`
- Modify: `science/src/science_tool/graph/health.py`

- [ ] **Step 1: Assemble the registry in `__init__.py`**

```python
"""Health checks, one module per check.

`HEALTH_CHECKS` is assembled by explicit import below — never by filesystem
discovery, which would make check order implicit. The tuple's order is the
execution order and the order of `_meta.timings`; changing it is observable.
"""

from __future__ import annotations

from science_tool.graph.health_checks import (
    agent_context,
    archive_lag,
    cross_paper_evidence,
    dataset_anomalies,
    entity_identity,
    identity_policy,
    invalid_entity_aspects,
    layered_claim_migration,
    legacy_task_type,
    lingering_tags,
    managed_artifacts,
    prose_epistemics,
    tooling_scaffold,
    unregistered_ref_kinds,
    unresolved_refs,
    validate,
)
from science_tool.graph.health_checks.base import (
    HealthCheck,
    HealthContext,
    HealthTiming,
    context_sources,
)

HEALTH_CHECKS: tuple[HealthCheck, ...] = (
    identity_policy.CHECK,
    entity_identity.CHECK,
    layered_claim_migration.CHECK,
    cross_paper_evidence.CHECK,
    archive_lag.CHECK,
    managed_artifacts.CHECK,
    tooling_scaffold.CHECK,
    validate.CHECK,
    prose_epistemics.CHECK,
    agent_context.CHECK,
    unresolved_refs.CHECK,
    unregistered_ref_kinds.CHECK,
    lingering_tags.CHECK,
    dataset_anomalies.CHECK,
    legacy_task_type.CHECK,
    invalid_entity_aspects.CHECK,
)

__all__ = [
    "HEALTH_CHECKS",
    "HealthCheck",
    "HealthContext",
    "HealthTiming",
    "context_sources",
]
```

**That order is the current `HEALTH_CHECKS` order, transcribed from
`health.py:1884-1983`. Verify it against `git show HEAD~5:.../health.py` rather
than trusting this block** — an accidental reordering is the one silent behavior
change this phase can produce, and no existing test asserts the order directly.

- [ ] **Step 2: `health.py` imports the registry**

Delete the `HEALTH_CHECKS` tuple and the 16 `CHECK` imports from `health.py`;
replace with:

```python
from science_tool.graph.health_checks import HEALTH_CHECKS, HealthCheck, HealthContext, context_sources
```

Keep the per-check TypedDict imports — `HealthReport` still needs them.

- [ ] **Step 3: Pin the order with a test**

Add to `science/tests/test_health_checks_base.py`:

```python
def test_health_check_order_is_pinned() -> None:
    """Registry order is execution order and timings order. Changing it is observable."""
    from science_tool.graph.health_checks import HEALTH_CHECKS

    assert [check.name for check in HEALTH_CHECKS] == [
        "identity_policy",
        "entity_identity",
        "layered_claim_migration",
        "cross_paper_evidence",
        "archive_lag",
        "managed_artifacts",
        "tooling_scaffold",
        "validate",
        "prose_epistemics",
        "agent_context",
        "unresolved_refs",
        "unregistered_ref_kinds",
        "lingering_tags",
        "dataset_anomalies",
        "legacy_task_type",
        "invalid_entity_aspects",
    ]
```

- [ ] **Step 4: Run the gate, then commit**

```bash
git add science/src/science_tool/graph/ science/tests/test_health_checks_base.py
git commit -m "Assemble HEALTH_CHECKS in the health_checks package (t-phase5)"
```

---

### Task 9: The guard

**Write this last, against the migrated tree.** A guard authored from the design
doc rather than from the code out-scopes its migration and lands red.

**Files:**
- Create: `science/tests/test_health_checks_package.py`

The guard has three jobs, in priority order:

1. **Ban the circular import.** No module under `health_checks/` may import from
   `science_tool.graph.health`. This is the structural rule that keeps the package
   extractable; it is the one that would silently rot first.
2. **One check per module, all registered.** Every module under `health_checks/`
   other than `__init__.py` and `base.py` defines exactly one `CHECK`, and every
   one of them appears in `HEALTH_CHECKS`.
3. **`health.py` defines no check bodies.** Enforced with a line budget set from
   the real post-migration count — measure it, do not guess. Phase 4's plan
   carried a placeholder budget of 900 against a real 236; set this one from
   `wc -l` and add a small margin.

- [ ] **Step 1: Measure the real numbers first**

```bash
cd science
wc -l src/science_tool/graph/health.py
ls src/science_tool/graph/health_checks/
```
Use the measured `health.py` line count (rounded up with ~20% headroom) as the
budget in Step 2. Record the measured value in the test's failure message.

- [ ] **Step 2: Write the guard**

`science/tests/test_health_checks_package.py`:

```python
"""Structural guard: health checks live in health_checks/, one per module.

Phase 5 of the toolkit convergence work moved 16 inline check bodies out of
graph/health.py. This guard stops them growing back and — more importantly —
stops a check module importing from graph/health.py, which would reintroduce
the import cycle the package exists to break.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_GRAPH = Path(__file__).resolve().parents[1] / "src" / "science_tool" / "graph"
_HEALTH = _GRAPH / "health.py"
_CHECKS_DIR = _GRAPH / "health_checks"

# Set from the measured post-migration size of health.py (Step 1), plus headroom.
_HEALTH_LINE_BUDGET = <MEASURED>

_NON_CHECK_MODULES = {"__init__.py", "base.py"}


def _check_modules() -> list[Path]:
    return sorted(p for p in _CHECKS_DIR.glob("*.py") if p.name not in _NON_CHECK_MODULES)


def _imports_health(tree: ast.Module) -> bool:
    """True if the module imports from science_tool.graph.health (the cycle)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "science_tool.graph.health":
            return True
        if isinstance(node, ast.Import):
            if any(alias.name == "science_tool.graph.health" for alias in node.names):
                return True
    return False


@pytest.mark.parametrize("module", _check_modules(), ids=lambda p: p.name)
def test_check_module_does_not_import_health(module: Path) -> None:
    """The import DAG is one-way: base <- checks <- __init__ <- health."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    assert not _imports_health(tree), (
        f"{module.name} imports from science_tool.graph.health, which imports the "
        f"check modules back. Import shared machinery from health_checks/base.py."
    )


@pytest.mark.parametrize("module", _check_modules(), ids=lambda p: p.name)
def test_check_module_defines_exactly_one_check(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    assigned = [
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name) and target.id == "CHECK"
    ]
    assert len(assigned) == 1, f"{module.name} must define exactly one CHECK, found {len(assigned)}"


def test_every_check_module_is_registered() -> None:
    from science_tool.graph.health_checks import HEALTH_CHECKS

    registered = {check.name for check in HEALTH_CHECKS}
    on_disk = {module.stem for module in _check_modules()}
    assert on_disk == registered, (
        f"health_checks/ modules and HEALTH_CHECKS disagree: "
        f"on disk only={sorted(on_disk - registered)}, registered only={sorted(registered - on_disk)}"
    )


def test_health_defines_no_check_bodies() -> None:
    lines = len(_HEALTH.read_text(encoding="utf-8").splitlines())
    assert lines <= _HEALTH_LINE_BUDGET, (
        f"health.py is {lines} lines (budget {_HEALTH_LINE_BUDGET}); a health check "
        f"belongs in its own module under graph/health_checks/"
    )
```

Note `test_every_check_module_is_registered` relies on each module's **filename
matching its check name** — which the Symbol ownership map already arranges.

- [ ] **Step 3: Prove the guard bites**

Do all four, and paste the observed failure into the task report:

```bash
cd science
# 1. cycle detection
echo "from science_tool.graph.health import HealthReport" >> src/science_tool/graph/health_checks/archive_lag.py
uv run --frozen pytest tests/test_health_checks_package.py -k archive_lag -q   # expect FAIL
git checkout src/science_tool/graph/health_checks/archive_lag.py

# 2. unregistered module
printf 'CHECK = None\n' > src/science_tool/graph/health_checks/zzz_temp.py
uv run --frozen pytest tests/test_health_checks_package.py -q                  # expect FAIL
rm src/science_tool/graph/health_checks/zzz_temp.py

uv run --frozen pytest tests/test_health_checks_package.py -q                  # expect PASS
```

- [ ] **Step 4: Run the full gate, then commit**

```bash
git add science/tests/test_health_checks_package.py
git commit -m "Guard: health checks stay in health_checks/, one per module, no import cycle (t-phase5)"
```

---

## Done criteria

- `graph/health.py` holds the registry driver and report assembly only, within its
  measured line budget.
- 16 modules under `graph/health_checks/`, one per check, each exporting one `CHECK`.
- No module under `health_checks/` imports `science_tool.graph.health`.
- `HEALTH_CHECKS` order unchanged, pinned by test.
- `health --format json` byte-identical (`-m snapshot` green at every commit).
- Full suite green, ruff clean, pyright 0 errors.
- The design doc's two errors are corrected in the code:
  `IDENTITY_REFERENCE_FIELDS` is shared, not duplicated; the check-name list
  exists once, in the registry.
