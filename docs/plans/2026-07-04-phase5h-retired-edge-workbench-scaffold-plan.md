# Phase 5h Retired Edge Workbench Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science dag scaffold-retired-edge-workbench`, a narrow file-write surface that turns one ready Phase 5g retired-edge migration plan into a strict, reviewable workbench YAML file.

**Architecture:** Reuse Phase 5g's `build_retired_edge_migration_plan(...)` and `migration_plan_to_workbench_yaml(...)` as the only source of migration semantics. Add a small scaffold API in `science_tool.dag.retired_edge_migration` for output-path validation, idempotent one-file writes, and summary reporting, then expose it through the flat DAG CLI. The command never compiles the workbench and never writes proposition, evidence-line, DOT, or retired `*.edges.yaml` files.

**Tech Stack:** Python 3.12, Click, Pydantic `WorkbenchFile`, PyYAML, pytest, existing `science_tool.dag` modules.

---

## File Structure

- Modify `science/src/science_tool/dag/retired_edge_migration.py`
  - Add `RetiredEdgeWorkbenchScaffoldResult`.
  - Add `scaffold_retired_edge_workbench(...)`.
  - Add output-path validation and scaffold table rendering helpers.
  - Keep all retired-edge migration semantics delegated to the existing Phase 5g planner.
- Modify `science/src/science_tool/dag/cli.py`
  - Add the flat command `dag scaffold-retired-edge-workbench`.
  - Wire `--project-root/--project`, `--dag`, `--focal-hypothesis`, `--output`, and `--format table|json`.
- Modify `science/src/science_tool/dag/__init__.py`
  - Export the new scaffold API only if the existing module export pattern requires it.
- Modify `science/tests/dag/test_retired_edge_migration.py`
  - Add API-level tests for write, no-op, blocked/skipped/evidence-warning failures, strict YAML, and path safety.
- Modify `science/tests/dag/test_cli.py`
  - Add CLI tests for table/json output and relative output resolution.
- Modify `science/tests/test_cli_surface_contract.py`
  - Classify the new command's `--project` alias in the existing allowlist.

No new module is needed. The feature is a thin write boundary around the existing migration planner.

---

### Task 1: Scaffold API Writes One Strict Workbench File

**Files:**
- Modify: `science/src/science_tool/dag/retired_edge_migration.py`
- Test: `science/tests/dag/test_retired_edge_migration.py`

- [ ] **Step 1: Add failing API tests for a successful scaffold write**

Append these tests after `test_workbench_yaml_is_strict_workbench_file_with_focal_hypothesis` in `science/tests/dag/test_retired_edge_migration.py`:

```python
def test_scaffold_retired_edge_workbench_writes_strict_yaml(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    output = project / "doc/figures/dags/h1.workbench.yaml"

    result = scaffold_retired_edge_workbench(
        project,
        dag="h1",
        focal_hypothesis="hypothesis:h1",
        output_path=output,
    )

    assert result.status == "written"
    assert result.written is True
    assert result.row_count == 1
    assert result.predicate_review_required == 1
    assert result.evidence_stub_count == 2
    assert result.output_path == "doc/figures/dags/h1.workbench.yaml"

    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    workbench = WorkbenchFile.model_validate(payload)
    assert workbench.focal_hypothesis == "hypothesis:h1"
    assert len(workbench.rows) == 1
    row = workbench.rows[0]
    assert row.subject == "a"
    assert row.predicate == "affects"
    assert row.object == "b"
    assert row.legacy_patch == "h1"
    assert row.legacy_edge_id == 1
    assert row.legacy_relation_label == "biases"
    assert row.discusses == ["hypothesis:h1"]
    assert payload["rows"][0]["evidence"] == [
        {
            "source": "task:t001",
            "evidence_type": "empirical_data",
            "stance": "supports",
        },
        {
            "source": "paper:Smith2020",
            "evidence_type": "literature",
            "stance": "supports",
        },
    ]
    assert not (project / "entities").exists()


def test_scaffold_retired_edge_workbench_relative_output_is_project_relative(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)

    result = scaffold_retired_edge_workbench(
        project,
        dag="h1",
        focal_hypothesis="hypothesis:h1",
        output_path=Path("doc/figures/dags/h1.workbench.yaml"),
    )

    assert result.status == "written"
    assert result.output_path == "doc/figures/dags/h1.workbench.yaml"
    assert (project / "doc/figures/dags/h1.workbench.yaml").exists()
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_writes_strict_yaml science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_relative_output_is_project_relative -q
```

Expected: FAIL with `ImportError` or `AttributeError` because `scaffold_retired_edge_workbench` does not exist.

- [ ] **Step 3: Add the scaffold result dataclass and helper signatures**

In `science/src/science_tool/dag/retired_edge_migration.py`, add `Sequence` to the typing imports:

```python
from typing import Any, Literal, Sequence
```

Then add these definitions after `RetiredEdgeMigrationPlan`:

```python
ScaffoldStatus = Literal["written", "no-op"]


@dataclass(frozen=True)
class RetiredEdgeWorkbenchScaffoldResult:
    project_root: str
    dag: str
    focal_hypothesis: str
    output_path: str
    status: ScaffoldStatus
    row_count: int
    predicate_review_required: int
    evidence_stub_count: int
    bytes: int

    @property
    def written(self) -> bool:
        return self.status == "written"

    def to_json(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "dag": self.dag,
            "focal_hypothesis": self.focal_hypothesis,
            "output": self.output_path,
            "status": self.status,
            "written": self.written,
            "rows": self.row_count,
            "predicate_review_required": self.predicate_review_required,
            "evidence_stubs": self.evidence_stub_count,
            "bytes": self.bytes,
        }
```

- [ ] **Step 4: Implement output-path and result helpers**

In `science/src/science_tool/dag/retired_edge_migration.py`, add these helpers near `migration_plan_to_workbench_yaml(...)`:

```python
def _project_relative_or_absolute(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_scaffold_output_path(project_root: Path, output_path: Path) -> Path:
    candidate = output_path if output_path.is_absolute() else project_root / output_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"output path escapes project root: {output_path}") from exc
    if not resolved.parent.exists():
        raise ValueError(f"output parent directory does not exist: {resolved.parent}")
    if resolved.name.endswith(".edges.yaml"):
        raise ValueError("output path must not be a retired .edges.yaml file")
    if resolved.suffix == ".dot":
        raise ValueError("output path must not be a DOT file")
    return resolved


def _ready_scaffold_rows(plan: RetiredEdgeMigrationPlan) -> Sequence[RetiredEdgeMigrationRow]:
    return tuple(row for row in plan.rows if row.status == "ready" and row.proposed_row is not None)


def _evidence_stub_count(rows: Sequence[RetiredEdgeMigrationRow]) -> int:
    return sum(len(row.proposed_row.get("evidence", [])) for row in rows if row.proposed_row is not None)
```

- [ ] **Step 5: Implement scaffold validation and write behavior**

In `science/src/science_tool/dag/retired_edge_migration.py`, add this public function after the helpers from Step 4:

```python
def scaffold_retired_edge_workbench(
    project_root: Path,
    *,
    dag: str,
    focal_hypothesis: str,
    output_path: Path,
) -> RetiredEdgeWorkbenchScaffoldResult:
    project_root = project_root.resolve()
    if not dag.strip():
        raise ValueError("--dag is required")
    if not focal_hypothesis.strip():
        raise ValueError("--focal-hypothesis is required")

    resolved_output = _resolve_scaffold_output_path(project_root, output_path)
    plan = build_retired_edge_migration_plan(project_root, dag=dag, focal_hypothesis=focal_hypothesis)
    if not plan.rows:
        raise ValueError(f"retired DAG edge file for dag {dag!r} contains no migration rows")

    blocked = [row for row in plan.rows if row.status == "blocked"]
    skipped = [row for row in plan.rows if row.status == "skipped"]
    missing_rows = [row for row in plan.rows if row.status == "ready" and row.proposed_row is None]
    evidence_warnings = [warning for row in plan.rows for warning in row.evidence_warnings]
    if blocked:
        details = ", ".join(f"{row.dag}#{row.edge_id}: {'/'.join(row.blockers)}" for row in blocked)
        raise ValueError(f"cannot scaffold blocked retired edge rows: {details}")
    if skipped:
        details = ", ".join(f"{row.dag}#{row.edge_id}: {'/'.join(row.blockers or row.notes)}" for row in skipped)
        raise ValueError(f"cannot scaffold skipped retired edge rows: {details}")
    if missing_rows:
        details = ", ".join(f"{row.dag}#{row.edge_id}" for row in missing_rows)
        raise ValueError(f"ready retired edge rows lack proposed workbench rows: {details}")
    if evidence_warnings:
        raise ValueError(f"cannot scaffold rows with evidence warnings: {', '.join(sorted(evidence_warnings))}")

    ready_rows = _ready_scaffold_rows(plan)
    if not ready_rows:
        raise ValueError("no ready retired edge migration rows to scaffold")

    rendered = migration_plan_to_workbench_yaml(plan)
    WorkbenchFile.model_validate(yaml.safe_load(rendered) or {})
    rendered_bytes = len(rendered.encode("utf-8"))

    status: ScaffoldStatus = "written"
    if resolved_output.exists():
        current = resolved_output.read_text(encoding="utf-8")
        if current != rendered:
            raise ValueError(f"output path already exists with different content: {resolved_output}")
        status = "no-op"
    else:
        resolved_output.write_text(rendered, encoding="utf-8")

    return RetiredEdgeWorkbenchScaffoldResult(
        project_root=project_root.as_posix(),
        dag=dag,
        focal_hypothesis=focal_hypothesis,
        output_path=_project_relative_or_absolute(project_root, resolved_output),
        status=status,
        row_count=len(ready_rows),
        predicate_review_required=sum(1 for row in ready_rows if row.predicate_review_required),
        evidence_stub_count=_evidence_stub_count(ready_rows),
        bytes=rendered_bytes,
    )
```

- [ ] **Step 6: Run the API tests and verify GREEN**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_writes_strict_yaml science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_relative_output_is_project_relative -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
rtk git add science/src/science_tool/dag/retired_edge_migration.py science/tests/dag/test_retired_edge_migration.py
rtk git commit -m "feat: scaffold retired edge workbench files"
```

---

### Task 2: Idempotency and Fail-Loud API Boundaries

**Files:**
- Modify: `science/tests/dag/test_retired_edge_migration.py`
- Modify: `science/src/science_tool/dag/retired_edge_migration.py`

- [ ] **Step 1: Add failing tests for no-op and existing-file protection**

Append these tests to `science/tests/dag/test_retired_edge_migration.py`:

```python
def test_scaffold_retired_edge_workbench_identical_existing_file_is_noop(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    output = project / "doc/figures/dags/h1.workbench.yaml"

    first = scaffold_retired_edge_workbench(
        project,
        dag="h1",
        focal_hypothesis="hypothesis:h1",
        output_path=output,
    )
    second = scaffold_retired_edge_workbench(
        project,
        dag="h1",
        focal_hypothesis="hypothesis:h1",
        output_path=output,
    )

    assert first.status == "written"
    assert second.status == "no-op"
    assert second.written is False
    assert second.bytes == first.bytes


def test_scaffold_retired_edge_workbench_existing_different_file_fails(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    output = project / "doc/figures/dags/h1.workbench.yaml"
    output.write_text("manual edits\n", encoding="utf-8")

    with pytest.raises(ValueError, match="already exists with different content"):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=output,
        )

    assert output.read_text(encoding="utf-8") == "manual edits\n"
```

- [ ] **Step 2: Run the idempotency tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_identical_existing_file_is_noop science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_existing_different_file_fails -q
```

Expected: PASS if Task 1 was implemented exactly; otherwise fix `scaffold_retired_edge_workbench(...)` before continuing.

- [ ] **Step 3: Add failing tests for blocked, skipped, and evidence-warning rows**

Append these tests to `science/tests/dag/test_retired_edge_migration.py`:

```python
def test_scaffold_retired_edge_workbench_blocked_rows_fail_before_write(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    (project / "doc/figures/dags/h1.dot").unlink()
    output = project / "doc/figures/dags/h1.workbench.yaml"

    with pytest.raises(ValueError, match="blocked retired edge rows"):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=output,
        )

    assert not output.exists()


def test_scaffold_retired_edge_workbench_skipped_rows_fail_before_write(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

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
    output = project / "doc/figures/dags/h1.workbench.yaml"

    with pytest.raises(ValueError, match="skipped retired edge rows"):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=output,
        )

    assert not output.exists()


def test_scaffold_retired_edge_workbench_evidence_warnings_fail_before_write(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
source_dot: doc/figures/dags/h1.dot
edges:
  - id: 1
    source: a
    target: b
    relation: biases
    edge_status: supported
    identification: observational
    description: Retired claim with unmapped support.
    lit_support:
      - description: Missing paper ref.
""".strip(),
        encoding="utf-8",
    )
    output = project / "doc/figures/dags/h1.workbench.yaml"

    with pytest.raises(ValueError, match="evidence warnings"):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=output,
        )

    assert not output.exists()
```

- [ ] **Step 4: Run the fail-loud row-state tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_blocked_rows_fail_before_write science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_skipped_rows_fail_before_write science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_evidence_warnings_fail_before_write -q
```

Expected: PASS.

- [ ] **Step 5: Add failing tests for output path safety**

Append these tests to `science/tests/dag/test_retired_edge_migration.py`:

```python
def test_scaffold_retired_edge_workbench_output_escape_fails(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)

    with pytest.raises(ValueError, match="escapes project root"):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=tmp_path / "outside.workbench.yaml",
        )


def test_scaffold_retired_edge_workbench_parent_must_exist(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)

    with pytest.raises(ValueError, match="parent directory does not exist"):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=Path("missing/h1.workbench.yaml"),
        )


def test_scaffold_retired_edge_workbench_refuses_retired_or_dot_outputs(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)

    with pytest.raises(ValueError, match=r"\.edges\.yaml"):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=Path("doc/figures/dags/h1.edges.yaml"),
        )

    with pytest.raises(ValueError, match="DOT file"):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=Path("doc/figures/dags/h1.dot"),
        )
```

- [ ] **Step 6: Run the path safety tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_output_escape_fails science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_parent_must_exist science/tests/dag/test_retired_edge_migration.py::test_scaffold_retired_edge_workbench_refuses_retired_or_dot_outputs -q
```

Expected: PASS.

- [ ] **Step 7: Run the full retired-edge migration test file**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_retired_edge_migration.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
rtk git add science/src/science_tool/dag/retired_edge_migration.py science/tests/dag/test_retired_edge_migration.py
rtk git commit -m "test: cover retired edge scaffold boundaries"
```

---

### Task 3: CLI Command for Scaffold Writes

**Files:**
- Modify: `science/src/science_tool/dag/cli.py`
- Modify: `science/tests/dag/test_cli.py`
- Modify: `science/tests/test_cli_surface_contract.py`

- [ ] **Step 1: Add CLI tests for writing and JSON no-op reporting**

Append these tests after `test_cli_dag_retired_edge_migration_plan_workbench_outputs_strict_yaml` in `science/tests/dag/test_cli.py`:

```python
def test_cli_dag_scaffold_retired_edge_workbench_writes_file(tmp_path: Path) -> None:
    from science_tool.dag.workbench import WorkbenchFile

    project = tmp_path / "project"
    _write_retired_migration_project(project)
    output = project / "doc/figures/dags/h1.workbench.yaml"

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
            "doc/figures/dags/h1.workbench.yaml",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "written" in result.output
    assert "doc/figures/dags/h1.workbench.yaml" in result.output
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    workbench = WorkbenchFile.model_validate(payload)
    assert workbench.focal_hypothesis == "hypothesis:h1"
    assert len(workbench.rows) == 1
    assert not (project / "entities").exists()


def test_cli_dag_scaffold_retired_edge_workbench_json_reports_noop(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    args = [
        "dag",
        "scaffold-retired-edge-workbench",
        "--project",
        str(project),
        "--dag",
        "h1",
        "--focal-hypothesis",
        "hypothesis:h1",
        "--output",
        "doc/figures/dags/h1.workbench.yaml",
        "--format",
        "json",
    ]

    first = CliRunner().invoke(main, args)
    second = CliRunner().invoke(main, args)

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)
    assert first_payload["status"] == "written"
    assert first_payload["written"] is True
    assert second_payload["status"] == "no-op"
    assert second_payload["written"] is False
    assert second_payload["output"] == "doc/figures/dags/h1.workbench.yaml"
    assert second_payload["rows"] == 1
```

- [ ] **Step 2: Run CLI tests and verify RED**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_cli.py::test_cli_dag_scaffold_retired_edge_workbench_writes_file science/tests/dag/test_cli.py::test_cli_dag_scaffold_retired_edge_workbench_json_reports_noop -q
```

Expected: FAIL because the Click command does not exist.

- [ ] **Step 3: Add the command implementation**

In `science/src/science_tool/dag/cli.py`, add this command after `retired_edge_migration_plan_cmd(...)` and before the `schema` section:

```python
@dag_group.command("scaffold-retired-edge-workbench")
@click.option(
    "--dag",
    "slug",
    required=True,
    help="Retired DAG slug to scaffold into one workbench file.",
)
@click.option(
    "--focal-hypothesis",
    required=True,
    help="Hypothesis ref to use as file-level workbench membership for migrated rows.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Workbench YAML path to write. Relative paths resolve against the project root.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def scaffold_retired_edge_workbench_cmd(
    slug: str,
    focal_hypothesis: str,
    output_path: Path,
    output_format: str,
    project_path: Path | None,
) -> None:
    """Write a reviewable workbench YAML scaffold from retired DAG edge rows."""
    from science_tool.dag.retired_edge_migration import (
        render_retired_edge_workbench_scaffold_table,
        scaffold_retired_edge_workbench,
    )

    project = (project_path or Path.cwd()).resolve()
    try:
        result = scaffold_retired_edge_workbench(
            project,
            dag=slug,
            focal_hypothesis=focal_hypothesis,
            output_path=output_path,
        )
        if output_format == "json":
            click.echo(json.dumps(result.to_json(), indent=2, sort_keys=True))
            return
        click.echo(render_retired_edge_workbench_scaffold_table(result), nl=False)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
```

- [ ] **Step 4: Add the table renderer**

In `science/src/science_tool/dag/retired_edge_migration.py`, add this function near `render_migration_plan_table(...)`:

```python
def render_retired_edge_workbench_scaffold_table(result: RetiredEdgeWorkbenchScaffoldResult) -> str:
    action = "Wrote" if result.written else "No-op"
    return (
        f"{action} retired edge workbench scaffold: {result.output_path}\n"
        f"  dag: {result.dag}\n"
        f"  focal_hypothesis: {result.focal_hypothesis}\n"
        f"  rows: {result.row_count}\n"
        f"  predicate_review_required: {result.predicate_review_required}\n"
        f"  evidence_stubs: {result.evidence_stub_count}\n"
    )
```

- [ ] **Step 5: Update CLI surface contract allowlist**

In `science/tests/test_cli_surface_contract.py`, add the new command to `_PROJECT_OPTION_ALLOWLIST`:

```python
    "dag scaffold-retired-edge-workbench": (
        "older DAG filesystem-root flag for explicit retired YAML workbench scaffolding",
        "project root",
    ),
```

Also add it to `_PROJECT_ROOT_ALIAS_COMMANDS`:

```python
    "dag scaffold-retired-edge-workbench",
```

- [ ] **Step 6: Run the new CLI tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_cli.py::test_cli_dag_scaffold_retired_edge_workbench_writes_file science/tests/dag/test_cli.py::test_cli_dag_scaffold_retired_edge_workbench_json_reports_noop -q
```

Expected: PASS.

- [ ] **Step 7: Run the CLI surface contract tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_cli_surface_contract.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
rtk git add science/src/science_tool/dag/cli.py science/src/science_tool/dag/retired_edge_migration.py science/tests/dag/test_cli.py science/tests/test_cli_surface_contract.py
rtk git commit -m "feat: add retired edge workbench scaffold command"
```

---

### Task 4: CLI Failure Modes and No-Write Guarantees

**Files:**
- Modify: `science/tests/dag/test_cli.py`
- Modify: `science/src/science_tool/dag/cli.py`
- Modify: `science/src/science_tool/dag/retired_edge_migration.py`

- [ ] **Step 1: Add CLI tests for required focal hypothesis and blocked rows**

Append these tests to `science/tests/dag/test_cli.py` near the scaffold command tests:

```python
def test_cli_dag_scaffold_retired_edge_workbench_requires_focal_hypothesis(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "scaffold-retired-edge-workbench",
            "--project",
            str(project),
            "--dag",
            "h1",
            "--output",
            "doc/figures/dags/h1.workbench.yaml",
        ],
    )

    assert result.exit_code != 0
    assert "Missing option '--focal-hypothesis'" in result.output
    assert not (project / "doc/figures/dags/h1.workbench.yaml").exists()


def test_cli_dag_scaffold_retired_edge_workbench_blocked_plan_fails_before_write(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    (project / "doc/figures/dags/h1.dot").unlink()

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
            "doc/figures/dags/h1.workbench.yaml",
        ],
    )

    assert result.exit_code != 0
    assert "blocked retired edge rows" in result.output
    assert "dot-missing" in result.output
    assert not (project / "doc/figures/dags/h1.workbench.yaml").exists()
```

- [ ] **Step 2: Add CLI tests for output protection**

Append these tests to `science/tests/dag/test_cli.py`:

```python
def test_cli_dag_scaffold_retired_edge_workbench_existing_different_file_fails(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    output = project / "doc/figures/dags/h1.workbench.yaml"
    output.write_text("reviewed content\n", encoding="utf-8")

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
            "doc/figures/dags/h1.workbench.yaml",
        ],
    )

    assert result.exit_code != 0
    assert "already exists with different content" in result.output
    assert output.read_text(encoding="utf-8") == "reviewed content\n"


def test_cli_dag_scaffold_retired_edge_workbench_output_escape_fails(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)

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
            str(tmp_path / "outside.workbench.yaml"),
        ],
    )

    assert result.exit_code != 0
    assert "escapes project root" in result.output
    assert not (tmp_path / "outside.workbench.yaml").exists()
```

- [ ] **Step 3: Run CLI failure tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_cli.py::test_cli_dag_scaffold_retired_edge_workbench_requires_focal_hypothesis science/tests/dag/test_cli.py::test_cli_dag_scaffold_retired_edge_workbench_blocked_plan_fails_before_write science/tests/dag/test_cli.py::test_cli_dag_scaffold_retired_edge_workbench_existing_different_file_fails science/tests/dag/test_cli.py::test_cli_dag_scaffold_retired_edge_workbench_output_escape_fails -q
```

Expected: PASS.

- [ ] **Step 4: Run the full DAG CLI test file**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
rtk git add science/tests/dag/test_cli.py science/src/science_tool/dag/cli.py science/src/science_tool/dag/retired_edge_migration.py
rtk git commit -m "test: cover retired edge scaffold cli failures"
```

---

### Task 5: Exports, Formatting, and Regression Suite

**Files:**
- Modify: `science/src/science_tool/dag/__init__.py`
- Modify: `science/src/science_tool/dag/retired_edge_migration.py`
- Modify: `science/src/science_tool/dag/cli.py`
- Modify: `science/tests/dag/test_retired_edge_migration.py`
- Modify: `science/tests/dag/test_cli.py`
- Modify: `science/tests/test_cli_surface_contract.py`

- [ ] **Step 1: Export the scaffold API from the DAG package**

In `science/src/science_tool/dag/__init__.py`, add imports beside the existing retired-edge migration exports:

```python
    RetiredEdgeWorkbenchScaffoldResult,
    render_retired_edge_workbench_scaffold_table,
    scaffold_retired_edge_workbench,
```

Add the same names to `__all__`:

```python
    "RetiredEdgeWorkbenchScaffoldResult",
    "render_retired_edge_workbench_scaffold_table",
    "scaffold_retired_edge_workbench",
```

- [ ] **Step 2: Run format**

Run:

```bash
rtk uv run --frozen ruff format science/src/science_tool/dag/retired_edge_migration.py science/src/science_tool/dag/cli.py science/src/science_tool/dag/__init__.py science/tests/dag/test_retired_edge_migration.py science/tests/dag/test_cli.py science/tests/test_cli_surface_contract.py
```

Expected: PASS and files may be reformatted.

- [ ] **Step 3: Run lint on touched files**

Run:

```bash
rtk uv run --frozen ruff check science/src/science_tool/dag/retired_edge_migration.py science/src/science_tool/dag/cli.py science/src/science_tool/dag/__init__.py science/tests/dag/test_retired_edge_migration.py science/tests/dag/test_cli.py science/tests/test_cli_surface_contract.py
```

Expected: PASS. Fix any unused imports or line-length issues without changing behavior.

- [ ] **Step 4: Run targeted tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_retired_edge_migration.py science/tests/dag/test_cli.py science/tests/test_cli_surface_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Run a dogfood command against a disposable copy if `~/d/protein-landscape` is present**

Run:

```bash
tmp_project="$(mktemp -d /tmp/phase5h-protein-landscape.XXXXXX)"
rtk cp -a ~/d/protein-landscape/. "$tmp_project/"
rtk uv run --frozen science dag scaffold-retired-edge-workbench \
  --project "$tmp_project" \
  --dag h01-multi-manifold-protein-universe \
  --focal-hypothesis hypothesis:h01-multi-manifold-protein-universe \
  --output doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml \
  --format json
```

Expected if the real project is available and unchanged: exit 0, JSON status `written`, `rows` equal to `6`, and output path `doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml`. If `rows` differs, inspect the changed live retired-edge corpus before changing code. Do not write into `~/d/protein-landscape` directly during this smoke.

- [ ] **Step 6: Run workbench parse/check smoke on the disposable output**

Run:

```bash
rtk uv run --frozen science dag workbench --check "$tmp_project/doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml"
```

Expected: command parses and reaches the workbench check path. Non-zero canonical diff is acceptable because inline evidence stubs normally normalize before a workbench reaches fixpoint. A schema/parse error is a Phase 5h bug.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
rtk git add science/src/science_tool/dag/__init__.py science/src/science_tool/dag/retired_edge_migration.py science/src/science_tool/dag/cli.py science/tests/dag/test_retired_edge_migration.py science/tests/dag/test_cli.py science/tests/test_cli_surface_contract.py
rtk git commit -m "chore: verify retired edge workbench scaffold"
```

---

### Task 6: Final Verification

**Files:**
- No planned edits unless verification reveals a defect.

- [ ] **Step 1: Check worktree status**

Run:

```bash
rtk git status --short --branch
```

Expected: clean worktree on `phase5h-retired-edge-workbench-scaffold`.

- [ ] **Step 2: Run full focused verification**

Run:

```bash
rtk uv run --frozen pytest science/tests/dag/test_retired_edge_migration.py science/tests/dag/test_cli.py science/tests/test_cli_surface_contract.py -q
rtk uv run --frozen ruff check science/src/science_tool/dag/retired_edge_migration.py science/src/science_tool/dag/cli.py science/src/science_tool/dag/__init__.py science/tests/dag/test_retired_edge_migration.py science/tests/dag/test_cli.py science/tests/test_cli_surface_contract.py
```

Expected: PASS.

- [ ] **Step 3: Inspect commit stack**

Run:

```bash
rtk git log --oneline main..HEAD
```

Expected: the design commit plus implementation commits for Tasks 1 through 5.

- [ ] **Step 4: Final self-review**

Check these acceptance points manually:

- `science dag retired-edge-migration-plan` still only writes stdout.
- `science dag scaffold-retired-edge-workbench` writes only the requested `.workbench.yaml` file.
- Existing reviewed workbenches are not overwritten.
- `WorkbenchFile.model_validate(...)` accepts the written YAML.
- Blocked/skipped/evidence-warning rows fail before writing.
- No proposition, evidence-line, DOT, or retired `*.edges.yaml` file is written.

If all pass, the implementation is ready for code review and merge.
