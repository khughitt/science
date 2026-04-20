# DAG Rendering and Audit Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift mm30's three proven DAG-maintenance scripts (`_render_styled.py`, `_number_edges.py`, `_dag_staleness.py`) into `science-tool` as a `dag` subcommand group, with pinned contracts for `identification` axis defaulting to `none`, drift-based (not age-based) staleness, read-only-by-default `dag audit`, a tagged-ref schema validated via `science-tool refs check`, and `--json` machine-readable output in v1. Add a `/science:dag-audit` skill for cadenced maintenance. Amend the 2026-04-17 edge-status dashboard spec to recognize `eliminated` as a fifth enum value (graph-layer storage deferred to Phase 2).

**Architecture:** A new `science_tool.dag` package owns rendering, numbering, staleness, audit orchestration, schema validation, and path discovery. Path discovery reads a `dag:` block from `science.yaml` (dag_dir, tasks_dir, optional dags whitelist), falling back to `research`-profile defaults. Schema validation uses narrow Pydantic v2 models in `schema.py` (NOT a full JSON-schema — that's Phase 2). Ref-schema validation integrates with the existing `science_tool.refs.check_refs` API. The rendering module preserves the mm30 visual contract (two-axis styling, precedence matrix) and adds `eliminated` as a fifth edge status. The staleness module is a drift-based rewrite (not a direct lift) that reads `tasks/done/*.md` + `tasks/active.md` frontmatter and emits separate "evidence freshness" vs "curation freshness" sections. `dag audit` composes render + staleness read-only; `dag audit --fix` performs mutations (opens review tasks, proposes YAML edits). The `/science:dag-audit` skill runs read-only by default and prompts for `--fix` only on explicit user approval.

**Tech Stack:** Python 3.11+, pydantic v2 (existing `science-tool` pattern), click (existing CLI), PyYAML, graphviz (`dot` CLI, already in test environments), pytest. No new runtime dependencies.

**Spec:** `docs/specs/2026-04-19-dag-rendering-and-audit-pipeline-design.md`

**Depends on:**
- `docs/specs/2026-03-07-phase4b-causal-dag-design.md` (approved — provides `inquiry` abstraction)
- `docs/specs/2026-04-17-edge-status-dashboard-design.md` (proposed — this plan amends the enum to add `eliminated`)
- `docs/specs/2026-04-17-inquiry-edge-posterior-annotations-design.md` (proposed — posterior block consumed as-is)

**Prerequisite:** None (this plan stands alone; the two 2026-04-17 specs do not need to be landed first because this spec only amends their enum / annotation contract at the YAML layer; graph-layer storage for the amendments is deferred to Phase 2).

---

## File Structure

### New files

**Upstream — `science-tool/src/science_tool/dag/`:**

- `__init__.py` — module marker; re-exports public API (`render_all`, `check_staleness`, `DagError`, `SchemaError`).
- `cli.py` — registers `dag` click group and the `render` / `number` / `staleness` / `audit` / `init` subcommands.
- `paths.py` — `science.yaml → DagPaths` discovery. Loads `dag_dir`, `tasks_dir`, `dags` whitelist; falls back to research-profile defaults.
- `schema.py` — Pydantic v2 models (`EdgeRecord`, `PosteriorBlock`, `RefEntry`, `EdgesYamlFile`) + narrow `SchemaError` fail-fast validators.
- `refs.py` — `validate_ref_entry(entry, root)` — wraps `science_tool.refs.check_refs` for DAG-local use; resolves `task:`, `interpretation:`, `discussion:`, `proposition:`, `paper:`, `doi:`, `accession:`, `dataset:` tagged entries.
- `render.py` — lifted from mm30 `_render_styled.py` with precedence-matrix + `eliminated` support.
- `number.py` — lifted from mm30 `_number_edges.py`.
- `staleness.py` — drift-based staleness; emits `DriftReport` dataclass; JSON serialiser.
- `audit.py` — orchestrator: composes render + staleness; read-only by default; `--fix` mutation path.
- `init.py` — scaffolds new `<slug>.dot` + stub `<slug>.edges.yaml` for `dag init <slug>`.

**Upstream — tests:**

- `science-tool/tests/dag/__init__.py` — marker.
- `science-tool/tests/dag/test_schema.py` — unit tests for Pydantic models + ref-schema validation.
- `science-tool/tests/dag/test_paths.py` — `science.yaml → DagPaths` discovery.
- `science-tool/tests/dag/test_render.py` — byte-identical `.dot` + PNG structural-invariants + `eliminated` visual contract.
- `science-tool/tests/dag/test_staleness.py` — drift detection, `last_reviewed` reset, under-reviewed, unpropagated orphans.
- `science-tool/tests/dag/test_audit.py` — read-only default + `--fix` mutation path.
- `science-tool/tests/dag/test_cli.py` — click integration.
- `science-tool/tests/dag/fixtures/mm30/` — imported from mm30 as-of the commit that created this plan:
  - `h1-prognosis.dot`, `h1-prognosis.edges.yaml`
  - `h1-progression.dot`, `h1-progression.edges.yaml`
  - `h2-subtype-architecture.dot`, `h2-subtype-architecture.edges.yaml`
  - `h1-h2-bridge.dot`, `h1-h2-bridge.edges.yaml`
  - `h1-prognosis-auto.dot.reference` — expected output from the lifted renderer.
  - `tasks/active.md`, `tasks/done/2026-04.md` — subset sufficient for staleness cross-refs.
  - `science.yaml` — minimal research-profile config with the `dag:` block.
- `science-tool/tests/dag/fixtures/minimal/` — synthetic 2-edge DAG for unit tests that don't need mm30's breadth.

**Upstream — skills and references:**

- `/mnt/ssd/Dropbox/science/skills/dag-audit.md` — new `/science:dag-audit` skill.
- `/mnt/ssd/Dropbox/science/references/dag-two-axis-evidence-model.md` — explainer doc for the replication × identification axes.

### Modified files

- `science-tool/src/science_tool/cli.py` — register `dag_group` under `main`; add `from science_tool.dag.cli import dag_group` and `main.add_command(dag_group)`.
- `docs/specs/2026-04-17-edge-status-dashboard-design.md` — amend the enum table: add `eliminated`. Mark the amendment as "storage deferred to Phase 2 sync-dag."
- `commands/big-picture.md` — Phase 3 rollup adds a read-only call to `science-tool dag staleness --json` so the synthesis report includes DAG freshness without mutating.

### Modified files in mm30 (migration PR, separate from upstream PR)

- `science.yaml` — add 4-line `dag:` block.
- `doc/figures/dags/README.md` — replace `uv run python _render_styled.py` commands with `science-tool dag render` equivalents.
- `doc/figures/dags/h{1,2}-*.edges.yaml` — backfill explicit `identification: none` or the correct axis value where it was previously absent. Net effect on rendered output should be zero modulo the new field presence.
- `doc/figures/dags/_render_styled.py` — **delete**.
- `doc/figures/dags/_number_edges.py` — **delete**.
- `doc/figures/dags/_dag_staleness.py` — **delete**.

### Unchanged

- `science-tool/src/science_tool/refs.py` / `refs_cli.py` — consumed as-is via `check_refs()`.
- `science-tool/src/science_tool/causal/` — unrelated runtime-inference exports (chirho, pgmpy); untouched.
- `science-tool/src/science_tool/graph/` — triple-layer code; untouched in Phase 1.
- mm30's `.dot` + `.edges.yaml` content (topology + evidence); only the `identification` default backfill touches content, and only additively.

---

## Task 1: Scaffold `science_tool.dag` package with `DagPaths` discovery

**Files:**
- Create: `science-tool/src/science_tool/dag/__init__.py`, `science-tool/src/science_tool/dag/paths.py`
- Test: `science-tool/tests/dag/test_paths.py`
- Fixture: `science-tool/tests/dag/fixtures/minimal/science.yaml`

- [ ] **Step 1: Write the failing test**

```python
# test_paths.py
from pathlib import Path

import pytest

from science_tool.dag.paths import DagPaths, load_dag_paths


def test_load_dag_paths_reads_explicit_block(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "profile: research\n"
        "dag:\n"
        "  dag_dir: custom/dag\n"
        "  tasks_dir: backlog\n"
        "  dags:\n"
        "    - h1\n"
        "    - h2\n"
    )
    paths = load_dag_paths(tmp_path)
    assert paths.dag_dir == tmp_path / "custom/dag"
    assert paths.tasks_dir == tmp_path / "backlog"
    assert paths.dags == ("h1", "h2")


def test_load_dag_paths_research_profile_defaults(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("profile: research\n")
    paths = load_dag_paths(tmp_path)
    assert paths.dag_dir == tmp_path / "doc/figures/dags"
    assert paths.tasks_dir == tmp_path / "tasks"
    assert paths.dags is None  # auto-discover


def test_load_dag_paths_software_profile_without_block_errors(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("profile: software\n")
    with pytest.raises(FileNotFoundError, match="dag:"):
        load_dag_paths(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails** (`pytest tests/dag/test_paths.py`).

- [ ] **Step 3: Implement `paths.py`**

```python
# paths.py
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass(frozen=True)
class DagPaths:
    dag_dir: Path
    tasks_dir: Path
    dags: tuple[str, ...] | None   # None = auto-discover all <slug>.edges.yaml

def load_dag_paths(project_root: Path) -> DagPaths:
    cfg = yaml.safe_load((project_root / "science.yaml").read_text())
    profile = cfg.get("profile", "research")
    block = cfg.get("dag")
    if block is None and profile == "research":
        return DagPaths(
            dag_dir=project_root / "doc/figures/dags",
            tasks_dir=project_root / "tasks",
            dags=None,
        )
    if block is None:
        raise FileNotFoundError(
            f"'dag:' block required in science.yaml for profile={profile}"
        )
    return DagPaths(
        dag_dir=project_root / block.get("dag_dir", "doc/figures/dags"),
        tasks_dir=project_root / block.get("tasks_dir", "tasks"),
        dags=tuple(block["dags"]) if block.get("dags") else None,
    )
```

- [ ] **Step 4: Re-run tests to confirm green.**

- [ ] **Step 5: Commit.** `feat(dag): scaffold science_tool.dag package with DagPaths discovery`

---

## Task 2: Pydantic v2 schema models with fail-fast validators

**Files:**
- Create: `science-tool/src/science_tool/dag/schema.py`
- Test: `science-tool/tests/dag/test_schema.py`
- Fixture: `science-tool/tests/dag/fixtures/minimal/edges-valid.yaml`, `edges-invalid-*.yaml`

- [ ] **Step 1: Write failing tests for each fail-fast rule**

Cover the v1 invariants from the spec's Acceptance Criterion 7:
- Missing `id` → `SchemaError`.
- Duplicate `(source, target)` pair within one DAG → `SchemaError`.
- Illegal `edge_status` enum value (`foo`) → `SchemaError`.
- Illegal `identification` enum value (`guessed`) → `SchemaError`.
- Posterior block with `hdi_low`/`hdi_high` but no `beta` → `SchemaError`.
- `edge_status == eliminated` without `eliminated_by` → `SchemaError`.
- `edge_status != eliminated` with `eliminated_by` present → `SchemaError`.
- Missing `identification` → defaults to `"none"` (NOT `"observational"`); emits a `DeprecationWarning` so migrations can surface the implicit cases.
- Ref entry with zero tag keys → `SchemaError`.
- Ref entry with two tag keys (e.g. both `task:` and `doi:`) → `SchemaError`.

- [ ] **Step 2: Run tests to verify failure.**

- [ ] **Step 3: Implement `schema.py`** with Pydantic v2 models:

```python
# schema.py (sketch)
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

class EdgeStatus(str, Enum):
    supported = "supported"
    tentative = "tentative"
    structural = "structural"
    unknown = "unknown"
    eliminated = "eliminated"

class Identification(str, Enum):
    interventional = "interventional"
    longitudinal = "longitudinal"
    observational = "observational"
    structural = "structural"
    none = "none"

REF_KINDS = frozenset({
    "task", "interpretation", "discussion", "proposition",
    "paper", "doi", "accession", "dataset",
})

class RefEntry(BaseModel):
    # Exactly one of REF_KINDS as a key, plus required description.
    model_config = {"extra": "allow"}
    description: str

    @model_validator(mode="after")
    def _exactly_one_kind(self) -> "RefEntry":
        extra = {k: v for k, v in self.__pydantic_extra__.items() if k in REF_KINDS}
        if len(extra) != 1:
            raise SchemaError(f"ref entry must have exactly one kind tag; got {list(extra)}")
        return self

class PosteriorBlock(BaseModel):
    beta: float | None = None
    hdi_low: float | None = None
    hdi_high: float | None = None
    # ...

    @model_validator(mode="after")
    def _hdi_requires_beta(self) -> "PosteriorBlock":
        if (self.hdi_low is not None or self.hdi_high is not None) and self.beta is None:
            raise SchemaError("posterior HDI provided without beta")
        return self

class EdgeRecord(BaseModel):
    id: int
    source: str
    target: str
    edge_status: EdgeStatus = EdgeStatus.unknown
    identification: Identification = Identification.none
    description: str
    data_support: list[RefEntry] = Field(default_factory=list)
    lit_support: list[RefEntry] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    eliminated_by: list[RefEntry] | None = None
    posterior: PosteriorBlock | None = None

    @model_validator(mode="after")
    def _eliminated_requires_provenance(self) -> "EdgeRecord":
        is_eliminated = self.edge_status == EdgeStatus.eliminated
        has_provenance = bool(self.eliminated_by)
        if is_eliminated and not has_provenance:
            raise SchemaError("edge_status=eliminated requires eliminated_by provenance list")
        if not is_eliminated and self.eliminated_by:
            raise SchemaError("eliminated_by is only valid when edge_status=eliminated")
        return self

class SchemaError(ValueError):
    pass
```

- [ ] **Step 4: Confirm all fail-fast tests pass.**

- [ ] **Step 5: Commit.** `feat(dag): schema.py with EdgeRecord, PosteriorBlock, RefEntry + fail-fast validators`

---

## Task 3: Ref validation wrapper over `science_tool.refs.check_refs`

**Files:**
- Create: `science-tool/src/science_tool/dag/refs.py`
- Test: `science-tool/tests/dag/test_refs_validation.py`

- [ ] **Step 1: Write failing tests.**

```python
def test_validate_ref_entry_resolves_task(mm30_fixture_root: Path) -> None:
    entry = RefEntry(task="t204", description="verdict")
    # No exception expected; t204 exists in the fixture tasks/done/
    validate_ref_entry(entry, mm30_fixture_root)

def test_validate_ref_entry_unresolved_task_raises(mm30_fixture_root: Path) -> None:
    entry = RefEntry(task="t99999", description="nonexistent")
    with pytest.raises(RefResolutionError):
        validate_ref_entry(entry, mm30_fixture_root)

def test_validate_ref_entry_interpretation_resolves_by_path(mm30_fixture_root: Path) -> None:
    entry = RefEntry(
        interpretation="2026-04-18-t204-bulk-composition-beyond-pc-maturity-verdict",
        description="...",
    )
    validate_ref_entry(entry, mm30_fixture_root)

def test_validate_ref_entry_doi_warns_but_does_not_fail(mm30_fixture_root: Path, caplog) -> None:
    entry = RefEntry(doi="10.1234/nonexistent", description="...")
    validate_ref_entry(entry, mm30_fixture_root)
    assert "doi" in caplog.text.lower()  # warn-only per spec open question
```

- [ ] **Step 2: Run tests.**

- [ ] **Step 3: Implement `refs.py`**

```python
from pathlib import Path
from science_tool.refs import check_refs  # existing

def validate_ref_entry(entry: RefEntry, project_root: Path) -> None:
    kind = _single_kind(entry)
    value = _value_for(entry, kind)
    if kind == "task":
        if not _task_exists(value, project_root):
            raise RefResolutionError(f"task {value} not found in tasks/")
    elif kind in ("interpretation", "discussion"):
        path = project_root / f"doc/{kind}s/{value}.md"
        if not path.exists():
            raise RefResolutionError(f"{kind} {value} not found at {path}")
    elif kind == "proposition":
        if not (project_root / f"specs/propositions/{value}.md").exists():
            raise RefResolutionError(f"proposition {value} not found")
    elif kind == "paper":
        if not (project_root / f"doc/papers/{value}.md").exists():
            raise RefResolutionError(f"paper {value} not found")
    elif kind == "doi":
        if not _is_valid_doi_syntax(value):
            raise RefResolutionError(f"invalid DOI syntax: {value}")
        _warn_if_no_paper_file(value, project_root)  # warn-only
    # accession / dataset: regex validation only in v1
```

- [ ] **Step 4: Confirm green.**

- [ ] **Step 5: Commit.** `feat(dag): ref-schema validation wrapping science_tool.refs.check_refs`

---

## Task 4: Import mm30 DAG fixtures

**Files:**
- Copy: `doc/figures/dags/*.{dot,edges.yaml}` from mm30 → `science-tool/tests/dag/fixtures/mm30/`
- Copy: `tasks/active.md`, `tasks/done/2026-04.md` from mm30 → fixture (subset OK; strip tasks that don't appear in any edges.yaml or staleness test case).
- Create: `science-tool/tests/dag/fixtures/mm30/science.yaml` (minimal; just `profile: research`).
- Generate: `<slug>-auto.dot.reference` for all 4 DAGs by running the current mm30 `_render_styled.py` against the fixture.

- [ ] **Step 1: Identify the mm30 commit** from which fixtures are sourced. Record the commit SHA in `fixtures/mm30/SOURCE.md` for reproducibility.
- [ ] **Step 2: Copy `.dot` + `.edges.yaml` files** verbatim.
- [ ] **Step 3: Trim `tasks/active.md` + `done/2026-04.md`** to a minimal subset: all task IDs referenced by any edge in the 4 DAGs, plus every task ID the mm30 `_dag_staleness.py` currently surfaces as "unpropagated," plus 3–5 additional tasks to exercise the drift detection.
- [ ] **Step 4: Run the mm30 `_render_styled.py` against the fixtures** once to capture the reference `-auto.dot` outputs. Save as `<slug>-auto.dot.reference`.
- [ ] **Step 5: Commit.** `test(dag): import mm30 DAG fixtures (commit <sha>)`

---

## Task 5: Lift `render.py` with precedence matrix and `eliminated` support

**Files:**
- Create: `science-tool/src/science_tool/dag/render.py`
- Test: `science-tool/tests/dag/test_render.py`

- [ ] **Step 1: Write failing tests.**

```python
def test_render_byte_identical_dot_vs_mm30_reference(mm30_fixture_root: Path) -> None:
    paths = load_dag_paths(mm30_fixture_root)
    render_all(paths)
    for slug in ("h1-prognosis", "h1-progression", "h2-subtype-architecture", "h1-h2-bridge"):
        produced = (paths.dag_dir / f"{slug}-auto.dot").read_text()
        expected = (paths.dag_dir / f"{slug}-auto.dot.reference").read_text()
        assert produced == expected, f"{slug}: .dot drifted from mm30 reference"

def test_render_png_structural_invariants(mm30_fixture_root: Path) -> None:
    paths = load_dag_paths(mm30_fixture_root)
    render_all(paths)
    for slug in ("h1-prognosis", "h1-h2-bridge"):
        png = paths.dag_dir / f"{slug}-auto.png"
        assert png.exists() and png.stat().st_size > 0
        # Structural invariants via the intermediate .dot:
        dot = (paths.dag_dir / f"{slug}-auto.dot").read_text()
        yaml = yaml.safe_load((paths.dag_dir / f"{slug}.edges.yaml").read_text())
        assert _count_rendered_edges(dot) == len(yaml["edges"])
        for edge in yaml["edges"]:
            assert f'[{edge["id"]}]' in dot  # every edge id renders

def test_render_eliminated_visual_contract(mm30_fixture_root: Path) -> None:
    # Bridge DAG has 2 eliminated edges (state->rib, state->e2f).
    paths = load_dag_paths(mm30_fixture_root)
    render_all(paths)
    dot = (paths.dag_dir / "h1-h2-bridge-auto.dot").read_text()
    # Both eliminated edges must carry the #9e9e9e color and [✗] marker
    # regardless of any posterior they preserve.
    assert dot.count("#9e9e9e") >= 2
    assert dot.count("[✗]") >= 2
    # ...and their penwidth must be 1.0 (not posterior-scaled).
    for edge_line in _edge_lines_matching(dot, src="state"):
        assert 'penwidth=1.0' in edge_line

def test_precedence_eliminated_over_posterior(minimal_fixture: Path) -> None:
    # Fixture edge has edge_status=eliminated + posterior.beta=+0.8 → should NOT get penwidth=4.8.
    render_all(load_dag_paths(minimal_fixture))
    dot = (minimal_fixture / "doc/figures/dags/x-auto.dot").read_text()
    assert "penwidth=1.0" in dot
    assert "penwidth=4" not in dot
```

- [ ] **Step 2: Run tests to verify failure.**

- [ ] **Step 3: Lift `_render_styled.py`** from mm30 into `render.py`. Adapt:
  - `HERE = Path(__file__).parent` → take `DagPaths` as parameter.
  - Hard-coded `DAGS = [...]` → either use `paths.dags` or `glob("*.edges.yaml")` if None.
  - Preserve STATUS_STYLES / IDENT_MARKERS / identification_color / identification_arrowhead verbatim.
  - Preserve the `[✗]` marker and `eliminated` override (already in mm30 as of the spec's commit).
  - Add the precedence-matrix ordering check at the top of `style_for_edge`: eliminated → structural-structural → posterior → HDI-crosses-zero → default.

- [ ] **Step 4: Confirm byte-identity test passes.** If it doesn't, diff the produced `.dot` against the reference; the common failure modes are (a) YAML field ordering (use `yaml.safe_dump(..., sort_keys=False)` where applicable), (b) legend insertion ordering.

- [ ] **Step 5: Confirm structural-invariants + eliminated tests pass.**

- [ ] **Step 6: Commit.** `feat(dag): render.py with precedence matrix + eliminated support (byte-identical with mm30)`

---

## Task 6: Lift `number.py`

**Files:**
- Create: `science-tool/src/science_tool/dag/number.py`
- Test: `science-tool/tests/dag/test_number.py`

- [ ] **Step 1: Write tests** — idempotency, `--force-stubs` resets curation, EDGE_RE handling of multi-line attrs.

- [ ] **Step 2: Run tests.**

- [ ] **Step 3: Lift `_number_edges.py`** verbatim, adapting path discovery through `DagPaths`. No semantic changes.

- [ ] **Step 4: Confirm green.**

- [ ] **Step 5: Commit.** `feat(dag): number.py lifted from mm30`

---

## Task 7: Drift-based `staleness.py` with separate evidence/curation finding classes

**Files:**
- Create: `science-tool/src/science_tool/dag/staleness.py`
- Test: `science-tool/tests/dag/test_staleness.py`

> **Note:** This is a rewrite, not a lift. mm30's `_dag_staleness.py` uses the age-based rule (signal A) that the spec supersedes. Do NOT copy its `report_stale_edges` function.

- [ ] **Step 1: Define the output dataclasses.**

```python
@dataclass(frozen=True)
class DriftedEdge:
    dag: str
    id: int
    source: str
    target: str
    last_cited_date: date | None
    last_reviewed: date | None
    candidate_drift_tasks: tuple[CandidateTask, ...]

@dataclass(frozen=True)
class CandidateTask:
    id: str
    completed: date
    related: tuple[str, ...]
    title: str

@dataclass(frozen=True)
class UnderReviewedEdge:
    dag: str
    id: int
    last_reviewed: date | None
    age_days: int | None  # None if never reviewed

@dataclass(frozen=True)
class UnpropagatedTask:
    id: str
    completed: date
    related: tuple[str, ...]
    title: str

@dataclass(frozen=True)
class UnresolvedRef:
    dag: str
    edge_id: int
    kind: str
    value: str
    reason: str

@dataclass(frozen=True)
class StalenessReport:
    today: date
    recent_days: int
    drifted_edges: tuple[DriftedEdge, ...]
    under_reviewed_edges: tuple[UnderReviewedEdge, ...]
    unresolved_refs: tuple[UnresolvedRef, ...]
    unpropagated_tasks: tuple[UnpropagatedTask, ...]

    @property
    def has_findings(self) -> bool:
        return bool(self.drifted_edges) or bool(self.unpropagated_tasks) or bool(self.unresolved_refs)

    def to_json(self) -> dict: ...
```

- [ ] **Step 2: Write tests for drift detection.**

```python
def test_drift_flags_edge_with_newer_related_task(minimal_fixture: Path) -> None:
    # Fixture: edge cites t001 (completed 2026-01-01); t100 completed 2026-04-15
    # with related:[hypothesis:h1]. Edge belongs to h1 → should flag.
    report = check_staleness(load_dag_paths(minimal_fixture), today=date(2026, 4, 20))
    assert len(report.drifted_edges) == 1
    assert report.drifted_edges[0].id == 1
    assert any(c.id == "t100" for c in report.drifted_edges[0].candidate_drift_tasks)

def test_drift_immune_to_calendar_age(minimal_fixture_with_stable_edge: Path) -> None:
    # Edge cites t001 (2026-01-01); no new h1-related tasks; today=2026-07-01.
    # Must NOT flag despite 6-month-old citation.
    report = check_staleness(load_dag_paths(minimal_fixture_with_stable_edge), today=date(2026, 7, 1))
    assert report.drifted_edges == ()

def test_drift_respects_last_reviewed_reset(minimal_fixture_last_reviewed: Path) -> None:
    # Edge cites t001 (2026-01-01); t100 completed 2026-03-15 is candidate drift task;
    # edge.last_reviewed=2026-04-01 → anchor becomes 2026-04-01; no drift.
    report = check_staleness(load_dag_paths(minimal_fixture_last_reviewed), today=date(2026, 4, 20))
    assert report.drifted_edges == ()

def test_drift_matches_via_source_target_node(minimal_fixture: Path) -> None:
    # Task's related:[] does not name the hypothesis but does name the edge source "prc2".
    # Should still be flagged as drift candidate.
    ...

def test_eliminated_edges_are_frozen(mm30_fixture_root: Path) -> None:
    report = check_staleness(load_dag_paths(mm30_fixture_root), today=date(2026, 4, 20))
    # Bridge edges 1 & 2 are eliminated; no drift flags even if related tasks exist.
    assert not any(e.dag == "h1-h2-bridge" and e.id in (1, 2) for e in report.drifted_edges)
```

- [ ] **Step 3: Write tests for unpropagated orphans, unresolved refs, JSON schema.**

- [ ] **Step 4: Run all tests.**

- [ ] **Step 5: Implement `staleness.py`.** Parse tasks from `tasks/active.md` + `tasks/done/*.md` reusing the parsing pattern in mm30's current `_dag_staleness.py` (lines 37–65 of that file — `TASK_HEADER_RE`, `COMPLETED_RE`, `RELATED_RE`, `parse_task_block`). Re-use verbatim.

- [ ] **Step 6: JSON output contract** — match the spec's output-contract schema byte-for-byte. Include a `to_json` method on `StalenessReport`.

- [ ] **Step 7: Confirm all tests green.**

- [ ] **Step 8: Commit.** `feat(dag): staleness.py with drift detection + curation + orphans + --json`

---

## Task 8: Audit orchestrator with read-only default + `--fix` mutation path

**Files:**
- Create: `science-tool/src/science_tool/dag/audit.py`
- Test: `science-tool/tests/dag/test_audit.py`

- [ ] **Step 1: Write tests.**

```python
def test_audit_read_only_does_not_mutate(mm30_fixture_root: Path) -> None:
    before = _snapshot_dir(mm30_fixture_root)
    report = run_audit(load_dag_paths(mm30_fixture_root), fix=False)
    after = _snapshot_dir(mm30_fixture_root)
    # Rendering is idempotent → -auto.{dot,png} may be re-touched but byte-identical.
    _assert_no_content_changes_except_auto_artifacts(before, after)
    assert not report.mutations

def test_audit_fix_opens_review_tasks(mm30_fixture_root: Path, monkeypatch) -> None:
    # Simulate a drifted edge; audit --fix should call science-tool tasks add.
    calls = []
    monkeypatch.setattr("science_tool.dag.audit.tasks_add", lambda **kw: calls.append(kw))
    report = run_audit(load_dag_paths(mm30_fixture_root), fix=True)
    assert len(calls) == len(report.drifted_edges)
    for call, edge in zip(calls, report.drifted_edges):
        assert f"Review {edge.dag}#{edge.id}" in call["title"]
        assert call["priority"] == "P2"
```

- [ ] **Step 2: Run tests.**

- [ ] **Step 3: Implement `audit.py`.**

```python
def run_audit(paths: DagPaths, *, fix: bool = False) -> AuditReport:
    render_all(paths)                                    # always idempotent
    staleness = check_staleness(paths)
    if not fix:
        return AuditReport(staleness=staleness, mutations=())
    mutations = []
    for edge in staleness.drifted_edges:
        mutations.append(_open_review_task(edge))
    for task in staleness.unpropagated_tasks:
        mutations.append(_propose_citation(task))
    return AuditReport(staleness=staleness, mutations=tuple(mutations))
```

- [ ] **Step 4: Confirm green.**

- [ ] **Step 5: Commit.** `feat(dag): audit orchestrator — read-only default + --fix mutations`

---

## Task 9: CLI wiring — `science-tool dag {render,number,staleness,audit,init}`

**Files:**
- Create: `science-tool/src/science_tool/dag/cli.py`, `science-tool/src/science_tool/dag/init.py`
- Modify: `science-tool/src/science_tool/cli.py` (register `dag_group`)
- Test: `science-tool/tests/dag/test_cli.py`

- [ ] **Step 1: Write CLI integration tests** using `click.testing.CliRunner`:
  - `dag render` exits 0, writes `-auto.dot` + `-auto.png`.
  - `dag staleness --json` emits valid JSON matching the spec schema.
  - `dag staleness` on a clean fixture exits 0; on drifted fixture exits 1.
  - `dag audit` without `--fix` does not mutate; exit 0/1 mirrors staleness.
  - `dag audit --fix` opens tasks (mocked).
  - `dag init foo` scaffolds `foo.dot` + empty `foo.edges.yaml`.

- [ ] **Step 2: Run tests.**

- [ ] **Step 3: Implement `cli.py`** with click subcommands; register the `dag_group` in `science_tool/cli.py`.

- [ ] **Step 4: Implement `init.py`** — writes minimal `.dot` skeleton + empty `edges: []` YAML.

- [ ] **Step 5: Confirm green.**

- [ ] **Step 6: Commit.** `feat(dag): CLI wiring — render / number / staleness / audit / init`

---

## Task 10: Amend 2026-04-17 edge-status dashboard spec

**Files:**
- Modify: `docs/specs/2026-04-17-edge-status-dashboard-design.md`

- [ ] **Step 1: Edit the enum table** to add `eliminated` as a fifth value. Match the wording in the DAG rendering spec (§"Schema extensions").
- [ ] **Step 2: Add a "Scope clarification (2026-04-19 amendment)"** paragraph noting that graph-layer storage for `eliminated` (and for the `identification` sibling axis introduced by the DAG rendering spec) is deferred to Phase 2 `sync-dag`. The edge-status dashboard's `--edge-status-distribution` command may show 0 for `eliminated` on projects that haven't yet run `sync-dag`; this is expected.
- [ ] **Step 3: Link back** to `2026-04-19-dag-rendering-and-audit-pipeline-design.md`.
- [ ] **Step 4: Commit.** `docs(specs): amend edge-status dashboard for eliminated enum value`

---

## Task 11: `/science:dag-audit` skill

**Files:**
- Create: `/mnt/ssd/Dropbox/science/skills/dag-audit.md`

- [ ] **Step 1: Draft the skill frontmatter.**

```markdown
---
name: dag-audit
description: Audit causal DAG freshness — run drift detection read-only, surface stale edges + unpropagated tasks + broken refs, and apply fixes only on explicit user approval. Use on a 4-weekly cadence or after any major verdict interpretation.
---
```

- [ ] **Step 2: Write the skill body.** Model on the workflow in the spec's §`/science:dag-audit` skill section. Structure:
  - Step 1: run `science-tool dag audit --json`.
  - Step 2: present the four finding classes separately (drift / under-reviewed / unresolved refs / unpropagated).
  - Step 3: for each finding, propose a concrete action; do NOT call `--fix` without user approval.
  - Step 4: on approval, invoke `dag audit --fix` (or narrower `tasks add` / YAML edit sequences) and commit.

- [ ] **Step 3: Add the skill to `/mnt/ssd/Dropbox/science/commands/big-picture.md`** Phase 3 rollup — read-only invocation only, so the synthesis report automatically surfaces DAG freshness without mutation.

- [ ] **Step 4: Commit.** `feat(skills): /science:dag-audit — drift-based DAG audit with read-only default`

---

## Task 12: Reference doc — two-axis evidence model

**Files:**
- Create: `/mnt/ssd/Dropbox/science/references/dag-two-axis-evidence-model.md`

- [ ] **Step 1: Draft the explainer** covering:
  - Why replication (`edge_status`) and identification are orthogonal.
  - Examples of each combination (supported-observational, tentative-interventional, etc.) with interpretive guidance.
  - When to use `interventional` vs `longitudinal` vs `observational`.
  - How `eliminated` differs from `unknown` (retracted vs never-tested).
  - Why `identification` defaults to `none`, not `observational`.
  - Cross-references to the phase4b spec, the edge-status dashboard spec, and this plan's spec.

- [ ] **Step 2: Commit.** `docs(references): two-axis evidence model explainer`

---

## Task 13: Upstream PR (aggregated)

**Files:** all of Tasks 1–12.

- [ ] **Step 1: Open PR in science-tool repo** titled `feat: dag subcommand group + /science:dag-audit skill (Phase 1+3)`.
- [ ] **Step 2: Body references** `docs/specs/2026-04-19-dag-rendering-and-audit-pipeline-design.md` + this plan.
- [ ] **Step 3: CI green.**
- [ ] **Step 4: Reviewer sign-off.**
- [ ] **Step 5: Merge.**

---

## Task 14: mm30 migration PR

**Files in mm30:**
- Delete: `doc/figures/dags/_render_styled.py`
- Delete: `doc/figures/dags/_number_edges.py`
- Delete: `doc/figures/dags/_dag_staleness.py`
- Modify: `science.yaml` — add `dag:` block
- Modify: `doc/figures/dags/README.md` — swap script invocations for `science-tool dag …`
- Modify: `doc/figures/dags/*.edges.yaml` — backfill explicit `identification: none` on edges where absent (can be scripted via `science-tool dag render` + a one-line YAML sweep, but the file-level diff must be reviewed).

- [ ] **Step 1: Upgrade mm30's `science-tool` pin** to the version that landed Task 13.
- [ ] **Step 2: Run `science-tool dag render`** once on mm30; confirm the `-auto.dot` outputs are byte-identical to what's currently in `main`.
- [ ] **Step 3: Backfill `identification: none`** via a scripted pass (or PR reviewer confirms the defaults are already correct and no backfill is necessary). Visual output unchanged.
- [ ] **Step 4: Delete the three local scripts.**
- [ ] **Step 5: Update README** to reference `science-tool dag render` / `science-tool dag staleness` / `science-tool dag audit`.
- [ ] **Step 6: Update `science.yaml`** with the `dag:` block.
- [ ] **Step 7: Run `science-tool dag audit`** on mm30 — confirm findings match expectations (drift edges from recent t-IDs; unpropagated tasks list ≈ the 40 mm30 currently surfaces).
- [ ] **Step 8: Open mm30 PR** titled `chore: migrate doc/figures/dags/ scripts to science-tool dag subcommand`.
- [ ] **Step 9: Merge.**

---

## Self-Review

Before opening the upstream PR:

- [ ] `.dot` byte-identity test passes against all 4 mm30 fixtures.
- [ ] `.png` structural-invariants test passes; no reliance on raw PNG bytes.
- [ ] `dag audit` without `--fix` makes zero mutations (verified by content hash before/after).
- [ ] `dag audit --fix` only opens tasks / proposes YAML edits; never commits automatically.
- [ ] `identification` default is `none` in `schema.py` and in the test fixtures; grep confirms no lazy `observational` default anywhere.
- [ ] `--json` output for `dag staleness` and `dag audit` matches the spec's output contract byte-for-byte.
- [ ] Fail-fast tests exist for: missing id, duplicate edges, illegal enums, malformed posterior, eliminated without eliminated_by, zero-tag refs, multi-tag refs.
- [ ] `science-tool refs check` integration tested: task/interpretation/discussion/proposition/paper resolve; doi warns but doesn't fail.
- [ ] Precedence matrix tested: eliminated > structural-structural > posterior > HDI-crosses-zero > default.
- [ ] Spec open-question #3 (doi fail-fast vs warn) settled in code matches the doc's "lean warn-only" default.
- [ ] mm30 migration PR verified locally against the upstream HEAD before pushing.

## Out of scope (explicitly deferred)

- JSON-schema validation (`dag validate --strict`). Phase 2.
- `science-tool graph sync-dag` bidirectional bridge. Phase 2.
- HTML / pyvis / cytoscape.js interactive rendering. Phase 4.
- Mermaid / d2 alternative renderers. Phase 4.
- mm30 t254 visual extensions (arrow-head shape for identification, persistent footer legend). Phase 4.
- Graph-layer predicates for `eliminated_by` and `identification`. Phase 2.

## Risks and Mitigations

- **`.dot` byte-identity fails on Task 5.** Most likely cause: non-deterministic YAML iteration order or legend-insertion-ordering divergence. Mitigation: reuse the exact ordering from mm30's `_render_styled.py` line-by-line; if drift persists, pin the test to a structural-equivalence check (parse both `.dot` files into a canonical AST and compare) rather than byte-identity.
- **mm30 staleness report counts differ from the current local script's output.** Expected: the new drift-based rule will surface a smaller and different set. This is a CORRECT behavior change, not a regression. Migration PR description must call this out explicitly.
- **Ref validation requires `science-tool refs check` to be reliable across project layouts.** The existing `check_refs` is research-profile-focused; if mm30's fixtures exercise paths `check_refs` doesn't currently handle, lift only the specific resolvers we need into `dag/refs.py` rather than calling `check_refs` wholesale.
- **Task 10 (amend edge-status dashboard spec) touches a file owned by the 2026-04-17 spec author.** If that spec is still in active revision, coordinate the amendment through a PR comment rather than a direct edit.
