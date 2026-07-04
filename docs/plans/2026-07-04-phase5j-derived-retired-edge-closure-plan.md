# Phase 5j Derived Retired Edge Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote lineage-backed retired DAG edge matches from generic skipped migration rows to a derived `closed` state, so applied Phase 5i work stops blocking the scaffold workflow.

**Architecture:** Closure remains a read-only derived view over live `PropositionEntity` records. The retired-edge migration planner builds a `(legacy_patch, legacy_edge_id)` closure index from relational propositions, classifies matching rows as `closed` or blocker-conflicted, and exposes stable JSON/table diagnostics. The scaffold writer treats `closed` as completed work, short-circuits all-closed DAGs as `complete`, and continues to fail on real blockers, evidence warnings, and non-closure skips.

**Tech Stack:** Python 3.11, Click CLI, Pydantic model entities from `science_model`, pytest, YAML fixtures, existing `science_tool.dag.retired_edge_migration` planner/scaffold module.

---

## File Structure

- Modify `science/src/science_tool/dag/retired_edge_migration.py`
  - Add derived closure dataclass/index helpers.
  - Extend `MigrationStatus`, row JSON, summary counts, and table rendering.
  - Reorder `_plan_edge(...)` around hard identity blockers, derived closure, and soft retired-state blockers.
  - Add `complete` scaffold status and all-closed short-circuit before output resolution and YAML rendering.
- Modify `science/tests/dag/test_retired_edge_migration.py`
  - Add lineage proposition fixture helpers.
  - Add planner tests for `closed`, duplicate lineage, subject/object mismatch, pair-only skipped behavior, closure winning soft retired-state blockers, and deleted/missing proposition resurface.
  - Add scaffold tests for all-closed `complete`, partial closed+ready output, and non-closure skipped rows still failing.
- Modify `science/tests/dag/test_cli.py`
  - Add CLI JSON/table coverage for `closed` planner rows and `complete` scaffold status.
- Optional modify `science/src/science_tool/dag/__init__.py`
  - Only if the implementation introduces public helper types that need package exports. Prefer not exporting internal closure helpers.

Run pytest, ruff, pyright, and `science` CLI commands from `science/`. Run all
`git` commands from the repository root, so paths beginning with `science/`
resolve correctly.

---

### Task 1: Add RED Planner Closure Tests

**Files:**
- Modify: `science/tests/dag/test_retired_edge_migration.py`

- [ ] **Step 1: Add a lineage proposition helper**

Add this helper near `_write_retired_edge_project(...)`:

```python
def _write_lineage_proposition(
    project: Path,
    *,
    slug: str = "a-affects-b",
    subject: str = "a",
    object_: str = "b",
    legacy_patch: str = "h1",
    legacy_edge_id: int = 1,
) -> None:
    prop_dir = project / "entities/propositions"
    prop_dir.mkdir(parents=True, exist_ok=True)
    (prop_dir / f"{slug}.md").write_text(
        f"""---
id: proposition:{slug}
type: proposition
title: {subject} affects {object_}
status: active
subject: {subject}
predicate: affects
object: {object_}
polarity: positive
claim_layer: causal_effect
identification_strength: observational
legacy_relation_label: biases
legacy_patch: {legacy_patch}
legacy_edge_id: {legacy_edge_id}
---

{subject} affects {object_}.
""",
        encoding="utf-8",
    )
```

- [ ] **Step 2: Add planner tests for derived closure and conflicts**

Append these tests near `test_plan_skips_matching_compiled_proposition(...)`:

```python
def test_plan_closes_matching_legacy_lineage_proposition(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["rows"] == 1
    assert payload["summary"]["closed"] == 1
    assert payload["summary"]["ready"] == 0
    assert payload["summary"]["blocked"] == 0
    assert payload["summary"]["skipped"] == 0
    row = payload["rows"][0]
    assert row["status"] == "closed"
    assert row["closed_by"] == ["proposition:a-affects-b"]
    assert row["closure_reason"] == "derived-legacy-edge-lineage"
    assert row["matching_propositions"] == []
    assert row["blockers"] == []
    assert row["proposed_row"] is None


def test_plan_blocks_duplicate_legacy_lineage_claims(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project, slug="a-affects-b")
    _write_lineage_proposition(project, slug="a-affects-b-copy")

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["blocked"] == 1
    assert payload["summary"]["closed"] == 0
    row = payload["rows"][0]
    assert row["status"] == "blocked"
    assert row["blockers"] == ["duplicate-legacy-edge-claim"]
    assert row["closed_by"] == []
    assert row["closure_conflicts"] == [
        {
            "proposition": "proposition:a-affects-b",
            "subject": "a",
            "object": "b",
            "file_path": "entities/propositions/a-affects-b.md",
        },
        {
            "proposition": "proposition:a-affects-b-copy",
            "subject": "a",
            "object": "b",
            "file_path": "entities/propositions/a-affects-b-copy.md",
        },
    ]


def test_plan_blocks_legacy_lineage_subject_object_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project, subject="a", object_="c")

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["blocked"] == 1
    assert payload["summary"]["closed"] == 0
    row = payload["rows"][0]
    assert row["status"] == "blocked"
    assert row["blockers"] == ["legacy-edge-claim-mismatch"]
    assert row["closure_conflicts"] == [
        {
            "proposition": "proposition:a-affects-b",
            "subject": "a",
            "object": "c",
            "file_path": "entities/propositions/a-affects-b.md",
        }
    ]
```

- [ ] **Step 3: Add tests for precedence and resurface behavior**

Append these tests below the conflict tests:

```python
def test_plan_closure_wins_soft_retired_state_blockers(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    (project / "doc/figures/dags/h1.dot").unlink()
    _write_lineage_proposition(project)

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["closed"] == 1
    row = payload["rows"][0]
    assert row["status"] == "closed"
    assert row["blockers"] == []
    assert row["closed_by"] == ["proposition:a-affects-b"]


def test_plan_pair_only_match_without_lineage_remains_skipped(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    prop_dir = project / "entities/propositions"
    prop_dir.mkdir(parents=True)
    (prop_dir / "a-affects-b.md").write_text(
        """---
id: proposition:a-affects-b
type: proposition
title: A affects B
status: active
subject: a
predicate: affects
object: b
polarity: positive
claim_layer: causal_effect
identification_strength: observational
---

A affects B.
""",
        encoding="utf-8",
    )

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["skipped"] == 1
    assert payload["summary"]["closed"] == 0
    row = payload["rows"][0]
    assert row["status"] == "skipped"
    assert row["blockers"] == ["matching-proposition-exists"]
    assert row["matching_propositions"] == ["proposition:a-affects-b"]
    assert row["closed_by"] == []


def test_plan_resurfaces_ready_when_closing_proposition_is_removed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    first = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()
    assert first["summary"]["closed"] == 1

    (project / "entities/propositions/a-affects-b.md").unlink()
    second = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert second["summary"]["closed"] == 0
    assert second["summary"]["ready"] == 1
    assert second["rows"][0]["status"] == "ready"
```

- [ ] **Step 4: Run planner tests and verify RED**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/dag/test_retired_edge_migration.py \
  -k 'closure or lineage or pair_only or resurfaces' -q
```

Expected: FAIL. Typical failures before implementation:

- `KeyError: 'closed'` for summary assertions;
- `AssertionError: assert 'skipped' == 'closed'`;
- no `closed_by`, `closure_reason`, or `closure_conflicts` keys.

- [ ] **Step 5: Commit RED tests**

```bash
rtk git add science/tests/dag/test_retired_edge_migration.py
rtk git commit -m "test(dag): specify derived retired edge closure"
```

---

### Task 2: Implement Planner Closure Classification

**Files:**
- Modify: `science/src/science_tool/dag/retired_edge_migration.py`
- Test: `science/tests/dag/test_retired_edge_migration.py`

- [ ] **Step 1: Extend row/status dataclasses**

In `retired_edge_migration.py`, update the status alias and add a closure claim dataclass near the existing dataclasses:

```python
MigrationStatus = Literal["ready", "blocked", "skipped", "closed"]


@dataclass(frozen=True)
class LegacyEdgeClosureClaim:
    proposition: str
    subject: str
    object: str
    file_path: str

    def to_json(self) -> dict[str, str]:
        return {
            "proposition": self.proposition,
            "subject": self.subject,
            "object": self.object,
            "file_path": self.file_path,
        }
```

Then extend `RetiredEdgeMigrationRow`:

```python
    closed_by: tuple[str, ...] = field(default_factory=tuple)
    closure_reason: str = ""
    closure_conflicts: tuple[LegacyEdgeClosureClaim, ...] = field(default_factory=tuple)
```

Update `to_json()`:

```python
            "closed_by": list(self.closed_by),
            "closure_reason": self.closure_reason,
            "closure_conflicts": [claim.to_json() for claim in self.closure_conflicts],
```

Update `RetiredEdgeMigrationPlan.to_json()` summary:

```python
                "closed": counts["closed"],
```

- [ ] **Step 2: Add the closure index helper**

Add this helper after `_propositions_by_pair(...)`:

```python
def _closure_claims_by_legacy_edge(project_root: Path) -> dict[tuple[str, int], list[LegacyEdgeClosureClaim]]:
    result: dict[tuple[str, int], list[LegacyEdgeClosureClaim]] = {}
    for prop in load_relational_propositions(project_root):
        if prop.id is None or prop.legacy_patch is None or prop.legacy_edge_id is None:
            continue
        if prop.subject is None or prop.object is None:
            continue
        key = (prop.legacy_patch, prop.legacy_edge_id)
        result.setdefault(key, []).append(
            LegacyEdgeClosureClaim(
                proposition=prop.id,
                subject=prop.subject,
                object=prop.object,
                file_path=prop.file_path,
            )
        )
    for claims in result.values():
        claims.sort(key=lambda claim: claim.proposition)
    return result
```

- [ ] **Step 3: Thread closure claims through the planner**

In `build_retired_edge_migration_plan(...)`, compute the index beside `propositions_by_pair`:

```python
    propositions_by_pair = _propositions_by_pair(project_root)
    closure_claims_by_edge = _closure_claims_by_legacy_edge(project_root)
```

Add an argument to `_plan_edge(...)`:

```python
    closure_claims_by_edge: dict[tuple[str, int], list[LegacyEdgeClosureClaim]],
```

Pass it at the call site:

```python
                    closure_claims_by_edge=closure_claims_by_edge,
```

- [ ] **Step 4: Add closure classification helpers**

Add these helpers before `_plan_edge(...)`:

```python
def _blocked_row(
    *,
    rel_path: str,
    dag: str,
    edge: EdgeRecord,
    source: str,
    target: str,
    description: str,
    raw_support: tuple[dict[str, str], ...],
    blockers: tuple[str, ...],
    notes: tuple[str, ...] = (),
    closure_conflicts: tuple[LegacyEdgeClosureClaim, ...] = (),
) -> RetiredEdgeMigrationRow:
    return RetiredEdgeMigrationRow(
        path=rel_path,
        dag=dag,
        edge_id=edge.id,
        source=source,
        target=target,
        description=description,
        raw_support=raw_support,
        status="blocked",
        blockers=blockers,
        notes=notes,
        closure_conflicts=closure_conflicts,
    )


def _closure_row_or_blocker(
    *,
    rel_path: str,
    dag: str,
    edge: EdgeRecord,
    source: str,
    target: str,
    description: str,
    raw_support: tuple[dict[str, str], ...],
    notes: tuple[str, ...],
    claims: Sequence[LegacyEdgeClosureClaim],
) -> RetiredEdgeMigrationRow:
    claim_tuple = tuple(claims)
    if len(claim_tuple) > 1:
        return _blocked_row(
            rel_path=rel_path,
            dag=dag,
            edge=edge,
            source=source,
            target=target,
            description=description,
            raw_support=raw_support,
            blockers=("duplicate-legacy-edge-claim",),
            notes=notes,
            closure_conflicts=claim_tuple,
        )

    claim = claim_tuple[0]
    if claim.subject != source or claim.object != target:
        return _blocked_row(
            rel_path=rel_path,
            dag=dag,
            edge=edge,
            source=source,
            target=target,
            description=description,
            raw_support=raw_support,
            blockers=("legacy-edge-claim-mismatch",),
            notes=notes,
            closure_conflicts=claim_tuple,
        )

    return RetiredEdgeMigrationRow(
        path=rel_path,
        dag=dag,
        edge_id=edge.id,
        source=source,
        target=target,
        description=description,
        raw_support=raw_support,
        status="closed",
        notes=(*notes, "derived-closure"),
        closed_by=(claim.proposition,),
        closure_reason="derived-legacy-edge-lineage",
    )
```

- [ ] **Step 5: Reorder `_plan_edge(...)`**

Inside `_plan_edge(...)`, replace the initial blocker flow with this structure:

```python
    hard_blockers: list[str] = []
    if not source:
        hard_blockers.append("missing-source")
    if not target:
        hard_blockers.append("missing-target")
    if missing_identification:
        notes.append("missing-identification-defaulted-to-none")

    if hard_blockers:
        return _blocked_row(
            rel_path=rel_path,
            dag=dag,
            edge=edge,
            source=source,
            target=target,
            description=description,
            raw_support=raw_support,
            blockers=tuple(hard_blockers),
            notes=tuple(notes),
        )

    closure_claims = tuple(closure_claims_by_edge.get((dag, edge.id), ()))
    if closure_claims:
        return _closure_row_or_blocker(
            rel_path=rel_path,
            dag=dag,
            edge=edge,
            source=source,
            target=target,
            description=description,
            raw_support=raw_support,
            notes=tuple(notes),
            claims=closure_claims,
        )

    blockers: list[str] = []
    if not dot_exists:
        blockers.append("dot-missing")
    if edge.edge_status == EdgeStatus.eliminated:
        blockers.append("eliminated-edge")
```

Leave the no-claim skip, pair-only skip, membership blocker, and proposed row logic after this block. Remove the old early `blockers` list initialization to avoid duplicate variables.

- [ ] **Step 6: Update table rendering for closed rows**

In `render_migration_plan_table(...)`, include the `closed` count in the header and print the closing proposition id:

```python
        f"{payload['summary']['closed']} closed, "
```

Inside the row loop:

```python
        if row["status"] == "closed":
            closed_by = ",".join(row["closed_by"]) if row["closed_by"] else "-"
            lines.append(
                f"  {row['dag']}#{row['edge_id']}: {row['source']} -> {row['target']} "
                f"closed by {closed_by}"
            )
            continue
```

- [ ] **Step 7: Run focused planner tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/dag/test_retired_edge_migration.py \
  -k 'closure or lineage or pair_only or resurfaces or skips_matching' -q
```

Expected: PASS.

- [ ] **Step 8: Run all retired-edge migration tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/dag/test_retired_edge_migration.py -q
```

Expected: PASS, or failures only in scaffold complete behavior that Task 3 will implement.

- [ ] **Step 9: Commit planner implementation**

```bash
rtk git add science/src/science_tool/dag/retired_edge_migration.py science/tests/dag/test_retired_edge_migration.py
rtk git commit -m "feat(dag): derive retired edge closure from propositions"
```

---

### Task 3: Add Scaffold Complete Behavior

**Files:**
- Modify: `science/src/science_tool/dag/retired_edge_migration.py`
- Modify: `science/tests/dag/test_retired_edge_migration.py`

- [ ] **Step 1: Add RED scaffold tests**

Append these tests near the existing scaffold tests:

```python
def test_scaffold_retired_edge_workbench_all_closed_returns_complete_without_output_checks(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    result = scaffold_retired_edge_workbench(
        project,
        dag="h1",
        focal_hypothesis="hypothesis:h1",
        output_path=Path("missing-parent/h1.workbench.yaml"),
    )

    assert result.status == "complete"
    assert result.written is False
    assert result.row_count == 0
    assert result.total_row_count == 1
    assert result.closed_row_count == 1
    assert result.closed_by == ("proposition:a-affects-b",)
    assert not (project / "missing-parent").exists()


def test_scaffold_retired_edge_workbench_writes_remaining_ready_rows_when_some_closed(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    dag_file = project / "doc/figures/dags/h1.edges.yaml"
    dag_file.write_text(
        dag_file.read_text(encoding="utf-8")
        + """
  - id: 2
    source: c
    target: d
    relation: yields
    edge_status: supported
    identification: observational
    description: Another retired claim.
    lit_support:
      - paper: Jones2021
        description: Literature support.
""",
        encoding="utf-8",
    )
    (project / "doc/figures/dags/h1.dot").write_text(
        "digraph h1 {\n  a -> b;\n  c -> d;\n}\n",
        encoding="utf-8",
    )
    _write_lineage_proposition(project)
    output = project / "doc/figures/dags/h1.workbench.yaml"

    result = scaffold_retired_edge_workbench(
        project,
        dag="h1",
        focal_hypothesis="hypothesis:h1",
        output_path=output,
    )

    assert result.status == "written"
    assert result.row_count == 1
    assert result.total_row_count == 2
    assert result.closed_row_count == 1
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["legacy_edge_id"] == 2
    assert payload["rows"][0]["subject"] == "c"
    assert payload["rows"][0]["object"] == "d"
```

- [ ] **Step 2: Run scaffold tests and verify RED**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/dag/test_retired_edge_migration.py \
  -k 'scaffold_retired_edge_workbench_all_closed or scaffold_retired_edge_workbench_writes_remaining_ready' -q
```

Expected: FAIL because `ScaffoldStatus` has no `complete`, result fields are missing, and the function resolves/validates the output path before seeing all rows are closed.

- [ ] **Step 3: Extend scaffold result dataclass**

In `retired_edge_migration.py`, update the scaffold status alias:

```python
ScaffoldStatus = Literal["written", "no-op", "complete"]
```

Extend `RetiredEdgeWorkbenchScaffoldResult`:

```python
    total_row_count: int
    closed_row_count: int
    closed_by: tuple[str, ...] = field(default_factory=tuple)
```

Keep `row_count` as the count of rows written to the workbench. Update `to_json()`:

```python
            "rows": self.row_count,
            "written_rows": self.row_count,
            "total_rows": self.total_row_count,
            "closed_rows": self.closed_row_count,
            "closed_by": list(self.closed_by),
```

The existing `written` property remains correct:

```python
    @property
    def written(self) -> bool:
        return self.status == "written"
```

- [ ] **Step 4: Move output resolution after all-closed detection**

In `scaffold_retired_edge_workbench(...)`, move:

```python
    resolved_output = _resolve_scaffold_output_path(project_root, output_path)
```

from before `build_retired_edge_migration_plan(...)` to after blocked/skipped/evidence-warning checks and after the all-closed branch below.

Add local row groups after building the plan:

```python
    closed = [row for row in plan.rows if row.status == "closed"]
    blocked = [row for row in plan.rows if row.status == "blocked"]
    skipped = [row for row in plan.rows if row.status == "skipped"]
```

Add the all-closed complete branch before resolving the output path or calling `migration_plan_to_workbench_yaml(plan)`:

```python
    ready_rows = _ready_scaffold_rows(plan)
    ready_count = sum(1 for row in plan.rows if row.status == "ready")
    if len(ready_rows) != ready_count:
        raise AssertionError("Phase 5g invariant violated: ready row lacks proposed_row")

    if closed and not ready_rows:
        return RetiredEdgeWorkbenchScaffoldResult(
            project_root=project_root.as_posix(),
            dag=dag,
            focal_hypothesis=focal_hypothesis,
            output_path=_project_relative_or_absolute(project_root, project_root / output_path),
            status="complete",
            row_count=0,
            total_row_count=len(plan.rows),
            closed_row_count=len(closed),
            closed_by=tuple(closed_id for row in closed for closed_id in row.closed_by),
            predicate_review_required=0,
            evidence_stub_count=0,
            byte_count=0,
        )
```

Then resolve the output and proceed for ready rows:

```python
    resolved_output = _resolve_scaffold_output_path(project_root, output_path)
    if not ready_rows:
        raise ValueError("no ready retired edge migration rows to scaffold")
```

When returning written/no-op, pass the new fields:

```python
        row_count=len(ready_rows),
        total_row_count=len(plan.rows),
        closed_row_count=len(closed),
        closed_by=tuple(closed_id for row in closed for closed_id in row.closed_by),
```

- [ ] **Step 5: Update table renderer**

Update `render_retired_edge_workbench_scaffold_table(...)`:

```python
    if result.status == "complete":
        return (
            f"Retired edge workbench scaffold complete: {result.dag}\n"
            f"  status: complete\n"
            f"  focal_hypothesis: {result.focal_hypothesis}\n"
            f"  rows: {result.total_row_count}\n"
            f"  closed_rows: {result.closed_row_count}\n"
        )
```

Keep the existing written/no-op output for non-complete statuses, but add `total_rows` and `closed_rows` lines:

```python
        f"  rows: {result.row_count}\n"
        f"  total_rows: {result.total_row_count}\n"
        f"  closed_rows: {result.closed_row_count}\n"
```

- [ ] **Step 6: Update existing scaffold tests for new required fields**

Existing tests that instantiate/assert `RetiredEdgeWorkbenchScaffoldResult` through the function need only assertions, not constructor changes. Add these assertions to existing written/no-op tests:

```python
    assert result.total_row_count == 1
    assert result.closed_row_count == 0
    assert result.closed_by == ()
```

For JSON CLI tests in Task 4, assert both `rows` and `written_rows` remain `1` for ready-only scaffolds.

- [ ] **Step 7: Run scaffold tests**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/dag/test_retired_edge_migration.py \
  -k 'scaffold_retired_edge_workbench' -q
```

Expected: PASS.

- [ ] **Step 8: Commit scaffold behavior**

```bash
rtk git add science/src/science_tool/dag/retired_edge_migration.py science/tests/dag/test_retired_edge_migration.py
rtk git commit -m "feat(dag): complete closed retired edge scaffolds"
```

---

### Task 4: Add CLI Coverage And JSON Contract Tests

**Files:**
- Modify: `science/tests/dag/test_cli.py`
- Modify: `science/src/science_tool/dag/retired_edge_migration.py` only if CLI output needs small renderer fixes.

- [ ] **Step 1: Add a CLI lineage helper**

Add this helper after `_write_retired_migration_project(...)`:

```python
def _write_retired_migration_lineage_proposition(project: Path) -> None:
    prop_dir = project / "entities/propositions"
    prop_dir.mkdir(parents=True, exist_ok=True)
    (prop_dir / "a-affects-b.md").write_text(
        """---
id: proposition:a-affects-b
type: proposition
title: A affects B
status: active
subject: a
predicate: affects
object: b
polarity: positive
claim_layer: causal_effect
identification_strength: observational
legacy_relation_label: biases
legacy_patch: h1
legacy_edge_id: 1
---

A affects B.
""",
        encoding="utf-8",
    )
```

- [ ] **Step 2: Add CLI planner JSON and table tests**

Add these tests near the existing retired-edge migration plan CLI tests:

```python
def test_cli_dag_retired_edge_migration_plan_json_reports_closed_rows(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    _write_retired_migration_lineage_proposition(project)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "retired-edge-migration-plan",
            "--project",
            str(project),
            "--dag",
            "h1",
            "--focal-hypothesis",
            "hypothesis:h1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["summary"]["closed"] == 1
    assert payload["summary"]["ready"] == 0
    row = payload["rows"][0]
    assert row["status"] == "closed"
    assert row["closed_by"] == ["proposition:a-affects-b"]
    assert row["closure_reason"] == "derived-legacy-edge-lineage"


def test_cli_dag_retired_edge_migration_plan_table_reports_closed_rows(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    _write_retired_migration_lineage_proposition(project)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "retired-edge-migration-plan",
            "--project",
            str(project),
            "--dag",
            "h1",
            "--focal-hypothesis",
            "hypothesis:h1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "1 closed" in result.output
    assert "closed by proposition:a-affects-b" in result.output
```

- [ ] **Step 3: Add CLI scaffold complete JSON/table tests**

Add these tests near the existing scaffold CLI tests:

```python
def test_cli_dag_scaffold_retired_edge_workbench_json_reports_complete(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    _write_retired_migration_lineage_proposition(project)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "scaffold-retired-edge-workbench",
            "--project",
            str(project),
            "--dag",
            "h1",
            "--focal-hypothesis",
            "hypothesis:h1",
            "--output",
            "missing-parent/h1.workbench.yaml",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "complete"
    assert payload["written"] is False
    assert payload["rows"] == 0
    assert payload["written_rows"] == 0
    assert payload["total_rows"] == 1
    assert payload["closed_rows"] == 1
    assert payload["closed_by"] == ["proposition:a-affects-b"]
    assert not (project / "missing-parent").exists()


def test_cli_dag_scaffold_retired_edge_workbench_table_reports_complete(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    _write_retired_migration_lineage_proposition(project)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "scaffold-retired-edge-workbench",
            "--project",
            str(project),
            "--dag",
            "h1",
            "--focal-hypothesis",
            "hypothesis:h1",
            "--output",
            "missing-parent/h1.workbench.yaml",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "status: complete" in result.output
    assert "closed_rows: 1" in result.output
    assert not (project / "missing-parent").exists()
```

- [ ] **Step 4: Update existing CLI JSON no-op test**

In `test_cli_dag_scaffold_retired_edge_workbench_json_reports_noop(...)`, add:

```python
    assert first_payload["written_rows"] == 1
    assert first_payload["total_rows"] == 1
    assert first_payload["closed_rows"] == 0
    assert second_payload["written_rows"] == 1
    assert second_payload["total_rows"] == 1
    assert second_payload["closed_rows"] == 0
```

- [ ] **Step 5: Run CLI tests and verify PASS**

Run:

```bash
cd science && rtk uv run --frozen pytest tests/dag/test_cli.py \
  -k 'retired_edge_migration_plan or scaffold_retired_edge_workbench' -q
```

Expected: PASS.

- [ ] **Step 6: Commit CLI coverage**

```bash
rtk git add science/tests/dag/test_cli.py science/src/science_tool/dag/retired_edge_migration.py
rtk git commit -m "test(dag): cover retired edge closure CLI"
```

---

### Task 5: Real Project Smoke And Final Verification

**Files:**
- No code changes expected.
- May amend tests/code only if this task reveals a Phase 5j implementation bug.

- [ ] **Step 1: Run focused test modules**

Run:

```bash
cd science && rtk uv run --frozen pytest \
  tests/dag/test_retired_edge_migration.py \
  tests/dag/test_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run lint/type checks for touched files**

Run:

```bash
cd science && rtk uv run --frozen ruff check \
  src/science_tool/dag/retired_edge_migration.py \
  tests/dag/test_retired_edge_migration.py \
  tests/dag/test_cli.py
```

Expected: `All checks passed!`

Run:

```bash
cd science && rtk uv run --frozen pyright src/science_tool/dag/retired_edge_migration.py
```

Expected: `0 errors, 0 warnings, 0 informations`

- [ ] **Step 3: Run the protein-landscape planner smoke**

Run from `science/`:

```bash
rtk uv run --frozen science dag retired-edge-migration-plan \
  --project ~/d/protein-landscape \
  --dag h01-multi-manifold-protein-universe \
  --focal-hypothesis hypothesis:h01-multi-manifold-protein-universe \
  --format json
```

Expected facts in output:

```json
{
  "summary": {
    "rows": 6,
    "closed": 6,
    "ready": 0,
    "blocked": 0,
    "skipped": 0
  }
}
```

Also inspect that each row has `status: "closed"` and a `closed_by` proposition id.

- [ ] **Step 4: Run the protein-landscape scaffold complete smoke**

Run from `science/`:

```bash
rtk uv run --frozen science dag scaffold-retired-edge-workbench \
  --project ~/d/protein-landscape \
  --dag h01-multi-manifold-protein-universe \
  --focal-hypothesis hypothesis:h01-multi-manifold-protein-universe \
  --output missing-parent/should-not-be-written.workbench.yaml \
  --format json
```

Expected facts in output:

```json
{
  "status": "complete",
  "written": false,
  "rows": 0,
  "written_rows": 0,
  "total_rows": 6,
  "closed_rows": 6
}
```

Confirm `~/d/protein-landscape/missing-parent/` does not exist after the command.

- [ ] **Step 5: Confirm no protein-landscape edits**

Run:

```bash
rtk git -C ~/d/protein-landscape status --short --branch
```

Expected: clean worktree.

- [ ] **Step 6: Run full touched suite**

Run:

```bash
cd science && rtk uv run --frozen pytest \
  tests/dag/test_retired_edge_migration.py \
  tests/dag/test_cli.py \
  tests/test_cli_surface_contract.py \
  -q
```

Expected: PASS.

- [ ] **Step 7: Commit any smoke-driven fixes**

If Task 5 required changes:

```bash
rtk git add science/src/science_tool/dag/retired_edge_migration.py science/tests/dag/test_retired_edge_migration.py science/tests/dag/test_cli.py
rtk git commit -m "fix(dag): align retired edge closure smoke behavior"
```

If no changes were required, do not create an empty commit.

- [ ] **Step 8: Final status**

Run:

```bash
rtk git status --short --branch
```

Expected: clean worktree on `phase5j-derived-retired-edge-closure`.

---

## Acceptance Checklist

- [ ] Planner JSON summary includes `closed`.
- [ ] Lineage-backed migrated retired rows classify as `closed`, not `skipped`.
- [ ] Pair-only matches without `legacy_patch` / `legacy_edge_id` remain skipped with the existing diagnostic.
- [ ] Duplicate `(legacy_patch, legacy_edge_id)` claims block the retired row.
- [ ] Subject/object mismatch for a lineage claim blocks the retired row.
- [ ] Soft retired-state blockers such as `dot-missing` do not prevent closure when trusted live proposition lineage exists.
- [ ] Scaffold all-closed DAGs return `complete` and do not inspect/write the output path.
- [ ] Scaffold mixed closed+ready DAGs write only remaining ready rows.
- [ ] Protein-landscape six-row fixture reports `closed: 6` and scaffold `complete`.
