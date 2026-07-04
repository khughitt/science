# Phase 5f DAG Edge Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish retiring `*.edges.yaml` from default DAG workflows by making compiled relational propositions the only normal semantic DAG edge source, while preserving one explicit retired-edge inspection surface for migration diagnostics.

**Architecture:** Add a narrow `dag retired-edges` report first so remaining YAML curation can be sized before defaults flip. Then change render/number/init/validate/audit/inventory to discover DOT/proposition-backed DAGs, never silently read or write retired YAML. Keep retired YAML parsing isolated behind the inspection command and schema migration surface.

**Tech Stack:** Python 3.13, Click, Pydantic, PyYAML, pytest, existing `science_tool.dag` modules, `science_model.propositions.PropositionEntity`.

**Execution environment (worktree):** This plan runs in a git worktree. Executors MUST `cd` into the worktree root and confirm the branch (`git branch --show-current` → `phase5f-dag-edge-retirement-design`) before any `git commit`, or commits leak to `main`. Prefix test/spike commands with `PYTHONPATH=src:model/src` so worktree-local `science_tool` (and `science_model`) edits are exercised instead of the editable install resolved from `main`. Phase 5f makes NO `science_model` changes — the `legacy_patch`/`legacy_edge_id`/`legacy_relation_label` fields already exist in the model — so the model-shadowing gotcha does not bite here, but the `PYTHONPATH` prefix keeps `science_tool` edits authoritative.

---

## File Structure

- Create `science/src/science_tool/dag/retired_edges.py`
  - Owns explicit retired YAML scanning and migration-summary reporting.
  - Reads raw `*.edges.yaml` files deliberately and quietly; no default command imports it except `dag retired-edges`.
- Modify `science/src/science_tool/dag/cli.py`
  - Add `retired-edges`.
  - Make `schema` explicitly retired.
  - Stop collapsing empty proposition edge lists into the YAML fallback sentinel.
  - Thread proposition edges into audit render path indirectly through `run_audit`.
- Modify `science/src/science_tool/dag/paths.py`
  - Add a `project_root` field to `DagPaths` (default `None`) so validation/audit can
    load compiled propositions without reverse-deriving the project root from
    `dag_dir` depth. `load_dag_paths` sets it; direct constructions may omit it and
    fall back to the default-layout heuristic.
- Modify `science/src/science_tool/dag/render.py`
  - Discover DOT slugs.
  - Remove implicit retired YAML fallback from default render.
  - Fail loudly when DOT edges have no compiled proposition edge.
  - Reuse `validate._parse_dot_topology` for the fail-loud preflight; do NOT add a
    second DOT-edge parser.
- Modify `science/src/science_tool/dag/number.py`
  - Discover DOT slugs.
  - Never write `*.edges.yaml`.
  - Make `force_stubs=True` fail loudly.
- Modify `science/src/science_tool/dag/init.py`
  - Create DOT only.
- Modify `science/src/science_tool/dag/proposition_edges.py`
  - Surface proposition ids and legacy DAG metadata on edge dicts.
  - Add a helper to load relational `PropositionEntity` objects for validation.
- Modify `science/src/science_tool/dag/validate.py`
  - Rebuild default validation around DOT topology plus proposition-backed edges.
  - Retire YAML shape/ref/posterior checks from default validation.
- Modify `science/src/science_tool/dag/audit.py`
  - Stop using YAML staleness: remove the `check_staleness` call from `run_audit`,
    drop the `staleness` field from `AuditReport`, and delete the now-dead
    YAML-drift mutation helpers.
  - Render from proposition edges (threaded in Task 4 so the suite stays green).
  - Keep audit read-only; `--fix` becomes a no-op (no proposition-backed mutation
    model is in Phase 5f scope).
- Modify `science/src/science_tool/dag/staleness.py`
  - Leave internals for historical imports, but CLI should stop using it as a default DAG command.
- Modify `science/src/science_tool/dag/inventory.py`
  - Stop emitting `dag-edge:` graph addresses from retired YAML.
- Modify docs:
  - `docs/user-guide/big-picture-synthesis.md`
  - downstream convention notes that still describe `.edges.yaml` as active input.
- Tests:
  - Create `science/tests/dag/test_retired_edges.py`
  - Update `science/tests/dag/test_render.py`
  - Update `science/tests/dag/test_validate.py`
  - Update `science/tests/dag/test_validate_cli.py`
  - Update `science/tests/dag/test_number.py`
  - Update `science/tests/dag/test_cli.py`
  - Update `science/tests/dag/test_audit.py`
  - Update `science/tests/dag/test_dag_inventory.py`
  - Update `science/tests/test_entities_inventory.py`
  - Append to `science/tests/test_edges_yaml_retired.py`
  - `science/tests/dag/test_staleness.py` — no change required (the `check_staleness`
    FUNCTION is retained; only the CLI surface retires), but re-run to confirm green.

---

## Existing Test Disposition

The new RED/GREEN tests in each task are ADDITIVE. Separately, **60 existing
`*.edges.yaml`-dependent tests across six files** exercise behavior this phase
retires and will fail once render/number/validate/audit stop reading YAML. Each
behavioral task below MUST migrate or delete its file's YAML-default tests in the
same commit, or the suite stays red until Task 10. Legend: **DEL** = delete
(coverage moves to the retired-inspection surface or to `test_schema.py`'s pydantic
unit tests); **DOT** = rewrite against DOT-only topology; **PROP** = rewrite against
a proposition-backed fixture.

Two mechanical reminders for every migrated/added test: (1) ensure the file
imports what the new blocks use (`from science_tool.dag.paths import DagPaths`,
`pytest`, `json`, `render_one`/`render_all`) — several appended blocks assume these.
(2) The `mm30`-fixture tests (`test_mm30_fixture_validates_*`,
`test_jsonschema_conformance_runs_on_mm30_fixture`,
`test_render_all_byte_identical_dot_vs_mm30_reference`, staleness
`test_mm30_fixture_runs_without_error`) default to **DELETE** unless the mm30 test
fixture actually ships compiled propositions; do not block on trying to PROP-migrate
them.

- `test_render.py` (7 → **Task 4**): `test_render_all_byte_identical_dot_vs_mm30_reference` DEL-or-PROP; `test_render_one_handles_eliminated_edge` PROP (eliminated now derives from the `refuted` channel); `test_render_one_uses_compact_inline_legend` PROP; `test_render_one_structural_invariants` PROP; `test_render_one_ignores_claim_only_yaml_edges` DEL (claim-only propositions are already skipped by `edges_from_propositions`); `test_render_discovers_slugs_when_whitelist_absent` DOT; `test_render_png_failure_is_non_fatal` PROP.
- `test_number.py` (5 → **Task 5**): `test_number_one_is_idempotent` DOT; `test_number_all_processes_multiple_slugs` DOT; `test_numbered_dot_has_edge_labels` DOT; `test_number_one_preserves_existing_curation` DEL; `test_number_one_force_stubs_resets_curation` DEL (replaced by `test_number_one_force_stubs_is_retired`).
- `test_validate.py` (20 → **Task 6**): posterior ×3 (`test_posterior_beta_must_be_finite`, `test_posterior_hdi_must_be_ordered`, `test_posterior_prob_sign_must_be_in_unit_interval`) DEL; jsonschema ×3 (`test_jsonschema_conformance_passes_on_clean`, `test_jsonschema_conformance_runs_on_mm30_fixture`, `test_jsonschema_conformance_catches_drift`) DEL; strict-curation ×2 (`test_strict_flags_missing_identification`, `test_strict_flags_empty_description`) DEL; yaml/dot reconciliation ×2 (`test_yaml_missing_edge_present_in_dot`, `test_yaml_edge_not_in_dot`) DEL (replaced by `test_validate_flags_dot_edge_without_matching_proposition`); topology ×5 (`test_clean_fixture_has_no_topology_findings`, `test_acyclicity_flags_cycle`, `test_acyclicity_passes_on_clean`, `test_strict_flags_orphan_dot_node`, `test_strict_flags_cross_dag_node_case_mismatch`) DOT; report-shape ×2 (`test_validation_report_ok_on_clean_fixture`, `test_validation_report_to_json_shape`) PROP; non-strict blocking (`test_non_strict_does_not_emit_strict_errors_as_blocking`) DOT; mm30 ×2 (`test_mm30_fixture_validates_non_strict`, `test_mm30_fixture_validates_strict`) DEL-or-PROP (only if mm30 has compiled propositions). `test_validation_finding_severity_literal` KEEP.
- `test_validate_cli.py` (7 → **Task 6**): `test_validate_clean_exits_zero` PROP; `test_validate_cyclic_exits_one` DOT; `test_validate_json_shape` PROP; `test_validate_dag_scope` PROP; `test_validate_missing_identification_non_strict_exits_zero` + `test_validate_missing_identification_strict_exits_one` DEL; `test_audit_json_includes_validation` PROP (audit JSON no longer has a `staleness` key — see Task 7). **KEEP but VERIFY:** `test_schema_stdout_is_valid_json` and `test_schema_write_to_file` stay green ONLY because Task 2 emits the retired banner to STDERR, keeping stdout/file pure JSON.
- `test_cli.py` (11 → **Tasks 4/5/7**): `test_cli_dag_render_writes_auto_artifacts` PROP (T4); `test_cli_dag_render_single_slug` PROP (T4); `test_dag_validate_accepts_format_json` PROP (T6); `test_cli_dag_number_is_idempotent` DOT (T5); `test_cli_dag_init_scaffolds_new_dag` rewritten in T5; `test_cli_dag_staleness_json_schema` + `test_dag_staleness_accepts_format_json` + `test_cli_dag_staleness_exit_code_on_clean_project` DEL (T7 — `dag staleness` now always raises, even on a clean project; replaced by `test_cli_dag_staleness_is_retired`); `test_dag_audit_accepts_format_json` PROP (fixture-migrated in T4, drop staleness key in T7); `test_cli_dag_audit_is_read_only_by_default` PROP (fixture-migrated in T4, finalized in T7); `test_cli_dag_audit_fix_mutates` DEL (T7 — `--fix` is now a no-op).
- Fully unaffected (no change): `test_refs_validation.py`, `test_schema.py`, `test_schema_artifact.py`, `test_dag_render_status_adapter.py`, `test_staleness.py` (function retained).

---

## Task 1: Explicit Retired-Edge Inspection Report

**Files:**
- Create: `science/src/science_tool/dag/retired_edges.py`
- Test: `science/tests/dag/test_retired_edges.py`

- [ ] **Step 1: Write failing tests for retired YAML summary**

Create `science/tests/dag/test_retired_edges.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.dag.retired_edges import build_retired_edges_report


def _write_manifest(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")


def test_retired_edges_report_counts_status_refs_and_claim_text(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
source_dot: doc/figures/dags/h1.dot
edges:
  - id: 1
    source: a
    target: b
    edge_status: supported
    description: Curated description still needs migration.
    interpretation: Claim-bearing interpretation.
    data_support:
      - task: t001
        description: Completed task support.
    lit_support:
      - paper: Smith2020
        description: Literature support.
  - id: 2
    source: b
    target: c
    edge_status: eliminated
    eliminated_by:
      - task: t002
        description: Refutation support.
""".strip(),
        encoding="utf-8",
    )

    report = build_retired_edges_report(project)
    payload = report.to_json()

    assert payload["summary"] == {
        "files": 1,
        "edges": 2,
        "orphan_files": 0,
        "claim_text_edges": 1,
        "support_ref_edges": 2,
        "migration_worthy_edges": 2,
    }
    assert payload["files"][0]["dag"] == "h1"
    assert payload["files"][0]["edge_status_counts"] == {"eliminated": 1, "supported": 1}
    assert payload["files"][0]["edges"][0]["has_claim_text"] is True
    assert payload["files"][0]["edges"][0]["support_ref_count"] == 2


def test_retired_edges_report_flags_orphan_yaml_without_dot(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "orphan.edges.yaml").write_text(
        """
dag: orphan
edges:
  - id: 1
    source: a
    target: b
    edge_status: tentative
    description: No DOT sibling exists.
""".strip(),
        encoding="utf-8",
    )

    report = build_retired_edges_report(project)
    payload = report.to_json()

    assert payload["summary"]["orphan_files"] == 1
    assert payload["files"][0]["orphan_dot"] is True
    assert payload["files"][0]["dot_path"] is None


def test_retired_edges_report_scopes_to_single_dag(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    for slug in ("alpha", "beta"):
        (dag_dir / f"{slug}.dot").write_text(f"digraph {slug} {{\n  a -> b;\n}}\n", encoding="utf-8")
        (dag_dir / f"{slug}.edges.yaml").write_text(
            f"dag: {slug}\nedges:\n  - id: 1\n    source: a\n    target: b\n",
            encoding="utf-8",
        )

    report = build_retired_edges_report(project, dag="beta")

    assert [file["dag"] for file in report.to_json()["files"]] == ["beta"]
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_retired_edges.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.dag.retired_edges'`.

- [ ] **Step 3: Implement `retired_edges.py`**

Create `science/src/science_tool/dag/retired_edges.py`:

```python
"""Explicit inspection surface for retired ``*.edges.yaml`` files.

Default DAG commands must not import this module for semantic edges. This module
exists only to size migration debt and expose remaining retired curation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from science_tool.dag.proposition_edges import load_proposition_edges


_CLAIM_TEXT_KEYS = ("interpretation", "finding", "claim", "description")
_SUPPORT_REF_KEYS = ("data_support", "lit_support", "eliminated_by")


@dataclass(frozen=True)
class RetiredEdgeRow:
    dag: str
    edge_id: str | None
    source: str
    target: str
    edge_status: str | None
    has_claim_text: bool
    support_ref_count: int
    has_matching_proposition: bool

    @property
    def migration_worthy(self) -> bool:
        return (self.has_claim_text or self.support_ref_count > 0) and not self.has_matching_proposition

    def to_json(self) -> dict[str, Any]:
        return {
            "dag": self.dag,
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "edge_status": self.edge_status,
            "has_claim_text": self.has_claim_text,
            "support_ref_count": self.support_ref_count,
            "has_matching_proposition": self.has_matching_proposition,
            "migration_worthy": self.migration_worthy,
        }


@dataclass(frozen=True)
class RetiredEdgesFileReport:
    path: str
    dag: str
    dot_path: str | None
    orphan_dot: bool
    edges: tuple[RetiredEdgeRow, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        status_counts = Counter(row.edge_status or "<missing>" for row in self.edges)
        return {
            "path": self.path,
            "dag": self.dag,
            "dot_path": self.dot_path,
            "orphan_dot": self.orphan_dot,
            "edge_count": len(self.edges),
            "edge_status_counts": dict(sorted(status_counts.items())),
            "edges": [row.to_json() for row in self.edges],
        }


@dataclass(frozen=True)
class RetiredEdgesReport:
    project_root: str
    files: tuple[RetiredEdgesFileReport, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        rows = [row for file in self.files for row in file.edges]
        summary = {
            "files": len(self.files),
            "edges": len(rows),
            "orphan_files": sum(1 for file in self.files if file.orphan_dot),
            "claim_text_edges": sum(1 for row in rows if row.has_claim_text),
            "support_ref_edges": sum(1 for row in rows if row.support_ref_count > 0),
            "migration_worthy_edges": sum(1 for row in rows if row.migration_worthy),
        }
        return {
            "project_root": self.project_root,
            "summary": summary,
            "files": [file.to_json() for file in self.files],
        }


def build_retired_edges_report(project_root: Path, *, dag: str | None = None) -> RetiredEdgesReport:
    dag_dir = project_root / "doc/figures/dags"
    yaml_paths = [dag_dir / f"{dag}.edges.yaml"] if dag else sorted(dag_dir.glob("*.edges.yaml"))
    proposition_pairs = {
        (str(edge.get("source", "")), str(edge.get("target", "")))
        for edge in load_proposition_edges(project_root)
    }

    files: list[RetiredEdgesFileReport] = []
    for yaml_path in yaml_paths:
        if not yaml_path.exists():
            continue
        payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            payload = {}
        dag_slug = str(payload.get("dag") or yaml_path.name.removesuffix(".edges.yaml"))
        dot_path = _resolve_dot_path(project_root, yaml_path, payload, dag_slug)
        edges = tuple(
            _edge_row(dag_slug, edge, proposition_pairs)
            for edge in payload.get("edges") or []
            if isinstance(edge, dict)
        )
        files.append(
            RetiredEdgesFileReport(
                path=yaml_path.relative_to(project_root).as_posix(),
                dag=dag_slug,
                dot_path=dot_path.relative_to(project_root).as_posix() if dot_path and dot_path.exists() else None,
                orphan_dot=not bool(dot_path and dot_path.exists()),
                edges=edges,
            )
        )

    return RetiredEdgesReport(project_root=project_root.as_posix(), files=tuple(files))


def _resolve_dot_path(project_root: Path, yaml_path: Path, payload: dict[str, Any], dag_slug: str) -> Path | None:
    source_dot = payload.get("source_dot")
    if isinstance(source_dot, str) and source_dot.strip():
        candidate = project_root / source_dot
        return candidate if candidate.exists() else yaml_path.parent / source_dot
    return yaml_path.parent / f"{dag_slug}.dot"


def _edge_row(
    dag: str,
    edge: dict[str, Any],
    proposition_pairs: set[tuple[str, str]],
) -> RetiredEdgeRow:
    source = str(edge.get("source") or "")
    target = str(edge.get("target") or "")
    support_count = 0
    for key in _SUPPORT_REF_KEYS:
        value = edge.get(key)
        if isinstance(value, list):
            support_count += len(value)
    has_claim_text = any(isinstance(edge.get(key), str) and edge[key].strip() for key in _CLAIM_TEXT_KEYS)
    edge_id = edge.get("id")
    return RetiredEdgeRow(
        dag=dag,
        edge_id=str(edge_id).strip() if edge_id is not None else None,
        source=source,
        target=target,
        edge_status=str(edge.get("edge_status")).strip() if edge.get("edge_status") is not None else None,
        has_claim_text=has_claim_text,
        support_ref_count=support_count,
        has_matching_proposition=(source, target) in proposition_pairs,
    )
```

- [ ] **Step 4: Run GREEN tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_retired_edges.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
rtk git add science/src/science_tool/dag/retired_edges.py science/tests/dag/test_retired_edges.py
rtk git commit -m "feat: report retired DAG edge files"
```

Expected: commit succeeds.

---

## Task 2: Retired-Edges CLI And Retired Schema Surface

**Files:**
- Modify: `science/src/science_tool/dag/cli.py`
- Test: `science/tests/dag/test_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Append these tests to `science/tests/dag/test_cli.py`:

```python
def test_cli_dag_retired_edges_json_reports_migration_summary(tmp_path: Path) -> None:
    project = tmp_path / "project"
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
edges:
  - id: 1
    source: a
    target: b
    edge_status: supported
    description: Retired edge text.
""".strip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        ["dag", "retired-edges", "--project", str(project), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["summary"]["files"] == 1
    assert payload["summary"]["migration_worthy_edges"] == 1
    assert "RETIRED" not in result.stderr


def test_cli_dag_retired_edges_table_reports_orphans(tmp_path: Path) -> None:
    project = tmp_path / "project"
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    (dag_dir / "orphan.edges.yaml").write_text(
        "dag: orphan\nedges:\n  - id: 1\n    source: a\n    target: b\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, ["dag", "retired-edges", "--project", str(project)])

    assert result.exit_code == 0, result.output
    assert "orphan" in result.output
    assert "orphan-dot" in result.output


def test_cli_dag_schema_says_schema_is_retired(cli_project: Path) -> None:
    # Banner goes to STDERR so stdout stays pure JSON (see test_validate_cli.py
    # ::test_schema_stdout_is_valid_json). Use a runner that separates streams.
    result = CliRunner(mix_stderr=False).invoke(main, ["dag", "schema"])

    assert result.exit_code == 0
    assert "RETIRED" in result.stderr
    assert "edges.yaml" in result.stderr
    # stdout must remain parseable JSON.
    json.loads(result.stdout)
```

> Note: on Click ≥ 8.2 `CliRunner` no longer accepts `mix_stderr`; drop the kwarg
> and read `result.stderr` directly (streams are separated by default). Confirm
> which Click is pinned in `science` and use the matching form.

- [ ] **Step 2: Run RED tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_cli.py::test_cli_dag_retired_edges_json_reports_migration_summary science/tests/dag/test_cli.py::test_cli_dag_retired_edges_table_reports_orphans science/tests/dag/test_cli.py::test_cli_dag_schema_says_schema_is_retired -q
```

Expected: FAIL because `retired-edges` is not registered and `dag schema` emits only JSON.

- [ ] **Step 3: Implement CLI command**

In `science/src/science_tool/dag/cli.py`, import nothing at module import time. Add this command near the other DAG commands:

```python
@dag_group.command("retired-edges")
@click.option(
    "--dag",
    "slug",
    default=None,
    help="Inspect one retired DAG edge file. Defaults to every *.edges.yaml file.",
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
def retired_edges_cmd(slug: str | None, output_format: str, project_path: Path | None) -> None:
    """Inspect retired *.edges.yaml files for migration diagnostics."""
    from science_tool.dag.retired_edges import build_retired_edges_report

    project = (project_path or Path.cwd()).resolve()
    report = build_retired_edges_report(project, dag=slug)
    payload = report.to_json()
    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = payload["summary"]
    click.echo(
        "Retired DAG edges: "
        f"{summary['files']} file(s), {summary['edges']} edge(s), "
        f"{summary['migration_worthy_edges']} migration-worthy edge(s)."
    )
    for file in payload["files"]:
        flags = []
        if file["orphan_dot"]:
            flags.append("orphan-dot")
        flag_text = f" [{' '.join(flags)}]" if flags else ""
        click.echo(f"  {file['dag']}: {file['edge_count']} edge(s){flag_text}")
```

- [ ] **Step 4: Make `dag schema` self-identify as retired**

In `schema_cmd`, when printing to stdout, wrap the JSON with a short retired banner. When writing to a file, keep the file as pure JSON but update the terminal message:

```python
def schema_cmd(output_path: Path | None) -> None:
    """Emit the JSON Schema for retired edges.yaml migration inspection."""
    schema = EdgesYamlFile.model_json_schema()
    canonical = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    banner = (
        "RETIRED: this schema describes the retired *.edges.yaml migration surface, "
        "not an active DAG authoring input.\n"
    )
    # Banner ALWAYS to stderr so stdout / the written file stay pure JSON. This
    # keeps test_validate_cli.py::{test_schema_stdout_is_valid_json,
    # test_schema_write_to_file} and the test_schema_artifact.py drift guard green.
    click.echo(banner, nl=False, err=True)
    if output_path is None:
        click.echo(canonical, nl=False)
    else:
        output_path.write_text(canonical, encoding="utf-8")
        click.echo(f"Wrote retired edges.yaml schema to {output_path}")
```

- [ ] **Step 5: Run GREEN tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_retired_edges.py science/tests/dag/test_cli.py::test_cli_dag_retired_edges_json_reports_migration_summary science/tests/dag/test_cli.py::test_cli_dag_retired_edges_table_reports_orphans science/tests/dag/test_cli.py::test_cli_dag_schema_says_schema_is_retired -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
rtk git add science/src/science_tool/dag/cli.py science/tests/dag/test_cli.py
rtk git commit -m "feat: expose retired DAG edge inspection"
```

Expected: commit succeeds.

---

## Task 3: Proposition Edge Loading Carries Identity Metadata

**Files:**
- Modify: `science/src/science_tool/dag/proposition_edges.py`
- Test: `science/tests/test_edges_yaml_retired.py`

- [ ] **Step 1: Add failing metadata projection test**

Append to `science/tests/test_edges_yaml_retired.py`:

```python
def test_proposition_edge_carries_identity_and_legacy_dag_metadata() -> None:
    prop = PropositionEntity(
        id="proposition:edge-one",
        subject="a",
        object="b",
        predicate="affects",
        polarity="positive",
        legacy_patch="h1",
        legacy_edge_id=7,
    )

    edge = edges_from_propositions([prop])[0]

    assert edge["proposition_id"] == "proposition:edge-one"
    assert edge["legacy_patch"] == "h1"
    assert edge["legacy_edge_id"] == 7
```

- [ ] **Step 2: Run RED test**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_edges_yaml_retired.py::test_proposition_edge_carries_identity_and_legacy_dag_metadata -q
```

Expected: FAIL with `KeyError: 'proposition_id'`.

- [ ] **Step 3: Implement projection metadata and relational loader**

Note: `original_label` and `belief_magnitude="speculative"` (plus `refuted`,
`has_grounding_evidence`) ALREADY exist in the current `proposition_to_edge`
(this worktree already carries earlier Task 5f work). This step is a THREE-key
addition — `proposition_id`, `legacy_patch`, `legacy_edge_id` — not a rewrite.
Diff the current file first and add only the missing keys; the block below shows
the full intended dict for reference.

In `science/src/science_tool/dag/proposition_edges.py`, update `proposition_to_edge`:

```python
    edge: dict = {
        "proposition_id": prop.id,
        "source": prop.subject,
        "target": prop.object,
        "legacy_patch": prop.legacy_patch,
        "legacy_edge_id": prop.legacy_edge_id,
        "polarity": polarity,
        "claim_layer": claim_layer,
        "identification": identification,
        "belief_magnitude": "speculative",
        "refuted": False,
        "has_grounding_evidence": False,
        "original_label": prop.legacy_relation_label
        or (prop.predicate.value if prop.predicate is not None else ""),
    }
```

Also add:

```python
def load_relational_propositions(project_root: Path) -> list[PropositionEntity]:
    """Load compiled relational propositions that can back DOT DAG edges."""
    from science_tool.entities import load_local_entity_index

    index = load_local_entity_index(project_root)
    return [
        entity
        for entity in index.values()
        if isinstance(entity, PropositionEntity)
        and entity.subject is not None
        and entity.object is not None
    ]
```

Then update `load_proposition_edges` to use the helper:

```python
def load_proposition_edges(project_root: Path) -> list[dict]:
    return edges_from_propositions(load_relational_propositions(project_root))
```

- [ ] **Step 4: Run GREEN test**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_edges_yaml_retired.py::test_proposition_edge_carries_identity_and_legacy_dag_metadata science/tests/test_edges_yaml_retired.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
rtk git add science/src/science_tool/dag/proposition_edges.py science/tests/test_edges_yaml_retired.py
rtk git commit -m "feat: carry DAG proposition edge metadata"
```

Expected: commit succeeds.

---

## Task 4: DOT Discovery And Fail-Loud Render Defaults

> **Ordering note:** This task makes `proposition_edges` a REQUIRED kwarg on
> `render_all`/`render_one` AND makes render fail loudly on any DOT edge with no
> matching proposition. Two knock-on effects on `run_audit` (the only other
> caller, `render_all(paths)` at `audit.py:226`):
> 1. *Signature:* the missing kwarg would `TypeError`. This task threads
>    proposition edges into `run_audit`'s render call (Step 5c) to fix it.
> 2. *Behavior:* audit-composing tests built on `.edges.yaml` fixtures (which have
>    no compiled propositions) would now make render RAISE. So this task also
>    migrates `test_audit.py` and the audit CLI tests to proposition-backed,
>    NO-`.edges.yaml` fixtures (Step 5d). Such a fixture stays green across the
>    whole sequence: new render is satisfied by the matching proposition; the
>    still-YAML validate (until Task 6) and still-composed staleness (until Task 7)
>    both find no `.edges.yaml` and return clean/empty. Task 7 then drops the
>    `staleness` key from these tests' assertions.
> Skipping either leaves `tests/dag/test_audit.py` and the full suite red from
> Task 4 through Task 7.

**Files:**
- Modify: `science/src/science_tool/dag/paths.py` (add `DagPaths.project_root`)
- Modify: `science/src/science_tool/dag/render.py`
- Modify: `science/src/science_tool/dag/audit.py` (thread proposition edges into render)
- Modify: `science/src/science_tool/dag/cli.py`
- Test: `science/tests/dag/test_render.py` (append new tests + migrate the 7 YAML-default tests per Existing Test Disposition)
- Test: `science/tests/dag/test_cli.py` (append + migrate `test_cli_dag_render_*`)
- Test: `science/tests/dag/test_audit.py` (migrate audit-composing tests to proposition-backed, no-YAML fixtures so render's fail-loud doesn't break them; Task 7 finalizes)

- [ ] **Step 1: Add failing render tests**

Append to `science/tests/dag/test_render.py`:

```python
def test_render_discovers_dot_slugs_without_edges_yaml(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "claim.dot").write_text("digraph claim {\n  a -> b;\n}\n", encoding="utf-8")

    paths = DagPaths(dag_dir=dag_dir, tasks_dir=tmp_path / "tasks", dags=None)
    render_all(
        paths,
        proposition_edges=[
            {
                "source": "a",
                "target": "b",
                "polarity": "positive",
                "belief_magnitude": "speculative",
                "claim_layer": "causal_effect",
                "refuted": False,
                "has_grounding_evidence": False,
                "identification": "observational",
                "original_label": "affects",
            }
        ],
    )

    assert (dag_dir / "claim-auto.dot").exists()


def test_render_refuses_yaml_only_fallback(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "claim.dot").write_text("digraph claim {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "claim.edges.yaml").write_text(
        "dag: claim\nedges:\n  - id: 1\n    source: a\n    target: b\n    edge_status: supported\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no compiled proposition edge"):
        render_one(dag_dir, "claim", proposition_edges=[])


def test_render_fails_before_partial_write_when_dot_edge_unbacked(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "claim.dot").write_text("digraph claim {\n  a -> b;\n  b -> c;\n}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="b -> c"):
        render_one(
            dag_dir,
            "claim",
            proposition_edges=[
                {
                    "source": "a",
                    "target": "b",
                    "polarity": "positive",
                    "belief_magnitude": "speculative",
                    "claim_layer": "causal_effect",
                    "refuted": False,
                    "has_grounding_evidence": False,
                    "identification": "observational",
                }
            ],
        )
    assert not (dag_dir / "claim-auto.dot").exists()
```

- [ ] **Step 2: Add failing CLI empty-proposition sentinel test**

Append to `science/tests/dag/test_cli.py`:

```python
def test_cli_dag_render_zero_propositions_does_not_fallback_to_yaml(tmp_path: Path) -> None:
    project = tmp_path / "project"
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        "dag: h1\nedges:\n  - id: 1\n    source: a\n    target: b\n    edge_status: supported\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, ["dag", "render", "--project", str(project)])

    assert result.exit_code != 0
    assert "no compiled proposition edge" in result.output.lower()
    assert not (dag_dir / "h1-auto.dot").exists()
```

- [ ] **Step 3: Run RED tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_render.py::test_render_discovers_dot_slugs_without_edges_yaml science/tests/dag/test_render.py::test_render_refuses_yaml_only_fallback science/tests/dag/test_render.py::test_render_fails_before_partial_write_when_dot_edge_unbacked science/tests/dag/test_cli.py::test_cli_dag_render_zero_propositions_does_not_fallback_to_yaml -q
```

Expected: FAIL because render still discovers YAML slugs and treats `None` as the fallback signal.

- [ ] **Step 4: Implement DOT discovery and preflight**

In `science/src/science_tool/dag/render.py`, change discovery and render signatures:

```python
def _discover_slugs(dag_dir: Path) -> list[str]:
    """Find every <slug>.dot source file, excluding generated variants."""
    slugs: list[str] = []
    for path in sorted(dag_dir.glob("*.dot")):
        if path.name.endswith(("-auto.dot", "-numbered.dot", ".reference")):
            continue
        slugs.append(path.stem)
    return slugs
```

Add a DOT-edge preflight. Do NOT write a second DOT parser — reuse
`validate._parse_dot_topology`, which already returns `(nodes, edges)` and is the
same set `dag validate` checks against, so render's fail-loud and validate's
`proposition_edge_missing` stay in lockstep. `render` does not import `validate`
today and `validate` does not import `render` (verified acyclic), so this import
is safe:

```python
from science_tool.dag.validate import _parse_dot_topology


def _assert_dot_edges_backed(slug: str, dot_path: Path, edges: list[dict]) -> None:
    available = {(str(edge.get("source")), str(edge.get("target"))) for edge in edges}
    _, dot_edges = _parse_dot_topology(dot_path)
    missing = [(src, tgt) for src, tgt in sorted(dot_edges) if (src, tgt) not in available]
    if missing:
        rendered = ", ".join(f"{src} -> {tgt}" for src, tgt in missing)
        raise ValueError(
            f"DAG {slug!r} has DOT edge(s) with no compiled proposition edge: {rendered}. "
            "Compile workbench rows for these edges or run `science dag retired-edges` "
            "to inspect retired YAML migration content."
        )
```

Update `render_one`:

```python
def render_one(
    dag_dir: Path,
    slug: str,
    *,
    proposition_edges: list[dict],
) -> None:
    dot_path = dag_dir / f"{slug}.dot"
    edges = proposition_edges
    _assert_dot_edges_backed(slug, dot_path, edges)
    out_dot = dag_dir / f"{slug}-auto.dot"
    out_png = dag_dir / f"{slug}-auto.png"
    emit_styled_dot(dot_path, edges, out_dot)
    render_png(out_dot, out_png)
```

Update `render_all` so `proposition_edges` is required:

```python
def render_all(
    paths: DagPaths,
    *,
    proposition_edges: list[dict],
) -> None:
    slugs = list(paths.dags) if paths.dags else _discover_slugs(paths.dag_dir)
    for slug in slugs:
        render_one(paths.dag_dir, slug, proposition_edges=proposition_edges)
```

Leave `_load_legacy_edges` in place for now only if still used by retired tests; default render must not call it.

- [ ] **Step 5: Stop CLI from collapsing empty edge lists**

In `science/src/science_tool/dag/cli.py`, change `_source_proposition_edges`:

```python
def _source_proposition_edges(project: Path) -> list[dict]:
    """Source channel-mode edges from compiled propositions.

    Empty list is meaningful: it means no relational propositions are compiled.
    It must not collapse to None because None used to select retired YAML
    fallback.
    """
    from science_tool.dag.proposition_edges import load_proposition_edges

    return load_proposition_edges(project)
```

The existing `render_cmd` call sites can continue passing `proposition_edges=proposition_edges`.

- [ ] **Step 5b: Add `project_root` to `DagPaths`**

In `science/src/science_tool/dag/paths.py`, add a `project_root` field so
validation/audit can load compiled propositions without reverse-deriving the root
from `dag_dir` depth (which breaks under a configured non-default `dag_dir`):

```python
@dataclass(frozen=True)
class DagPaths:
    dag_dir: Path
    tasks_dir: Path
    dags: tuple[str, ...] | None  # None = auto-discover all <slug>.dot files
    project_root: Path | None = None  # set by load_dag_paths; None => derive from dag_dir
```

Set it in BOTH `load_dag_paths` return branches (`project_root=project_root`).
Then update the `--dag` scoping rebuild in `cli.py` (`validate_cmd`, ~line 393) to
PRESERVE it: `DagPaths(dag_dir=paths.dag_dir, tasks_dir=paths.tasks_dir,
dags=(slug,), project_root=paths.project_root)`. Consumers derive the root as
`paths.project_root or paths.dag_dir.parents[2]` — the fallback is a default-layout
heuristic for directly-constructed `DagPaths` in tests; real runs always go through
`load_dag_paths`, which sets it explicitly.

- [ ] **Step 5c: Thread proposition edges through `run_audit`'s render (ordering)**

In `science/src/science_tool/dag/audit.py`, so the required-kwarg change does not
break audit. Add `from science_tool.dag.proposition_edges import load_proposition_edges`
and change the render call in `run_audit`:

```python
    project_root = paths.project_root or paths.dag_dir.parents[2]
    render_all(paths, proposition_edges=load_proposition_edges(project_root))
```

Leave `check_staleness` and `AuditReport.staleness` alone for now — Task 7 removes
them. This step is purely to keep the suite green across the required-kwarg change.

- [ ] **Step 5d: Migrate the existing render AND audit-composing tests**

Per the Existing Test Disposition section, migrate/delete the 7 YAML-default
`test_render.py` tests and the two `test_cli_dag_render_*` tests in this commit.
The new `render_all`/`render_one` signature is required-kwarg, so any test calling
them without `proposition_edges=` must be updated or removed here — not left for
Task 10. ALSO migrate the audit-composing tests (`test_audit.py`, and the audit
CLI tests `test_dag_audit_accepts_format_json` / `test_cli_dag_audit_is_read_only_by_default`)
to proposition-backed, no-`.edges.yaml` fixtures so render's new fail-loud does not
raise inside `run_audit` (they keep asserting the still-present `staleness` key
until Task 7 removes it; delete `test_cli_dag_audit_fix_mutates` in Task 7). Note the new render tests exercise the real `render_png` (shells out to
graphviz `dot`); they inherit whatever graphviz assumption the existing passing
render tests already rely on. If graphviz is unavailable in the runner, prefer
asserting on the emitted `<slug>-auto.dot` and reuse the existing
`test_render_png_failure_is_non_fatal` pattern rather than asserting on the PNG.

- [ ] **Step 6: Run GREEN render tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_render.py science/tests/dag/test_audit.py science/tests/dag/test_cli.py::test_cli_dag_render_zero_propositions_does_not_fallback_to_yaml -q
```

Expected: PASS — the new fail-loud tests AND the migrated `test_render.py` /
`test_audit.py` tests. Running the whole `test_render.py` + `test_audit.py` files
(not just the new nodes) confirms no migrated test was left calling the old
signature.

- [ ] **Step 7: Commit Task 4**

Run:

```bash
rtk git add science/src/science_tool/dag/render.py science/src/science_tool/dag/paths.py science/src/science_tool/dag/audit.py science/src/science_tool/dag/cli.py science/tests/dag/test_render.py science/tests/dag/test_cli.py science/tests/dag/test_audit.py
rtk git commit -m "feat: render DAGs from proposition edges only"
```

Expected: commit succeeds.

---

## Task 5: Number And Init Stop Writing Retired YAML

**Files:**
- Modify: `science/src/science_tool/dag/number.py`
- Modify: `science/src/science_tool/dag/init.py`
- Modify: `science/src/science_tool/dag/cli.py`
- Test: `science/tests/dag/test_number.py`
- Test: `science/tests/dag/test_cli.py`

- [ ] **Step 1: Update failing number/init tests**

In `science/tests/dag/test_number.py`, add:

```python
def test_number_one_does_not_create_edges_yaml_for_new_dot(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "new.dot").write_text("digraph new {\n  a -> b;\n}\n", encoding="utf-8")

    number_one(dag_dir, "new", proposition_edges=[])

    assert (dag_dir / "new-numbered.dot").exists()
    assert not (dag_dir / "new.edges.yaml").exists()


def test_number_one_force_stubs_is_retired(number_workspace: Path) -> None:
    with pytest.raises(ValueError, match="retired"):
        number_one(number_workspace, "h1-progression", force_stubs=True, proposition_edges=[])
```

Migrate the existing `test_number.py` tests per the Existing Test Disposition
section, in this commit: DELETE `test_number_one_preserves_existing_curation` and
`test_number_one_force_stubs_resets_curation` (both assert retired `.edges.yaml`
curation; the latter is replaced by `test_number_one_force_stubs_is_retired`);
rewrite `test_number_one_is_idempotent`, `test_number_all_processes_multiple_slugs`,
and `test_numbered_dot_has_edge_labels` to DOT-only fixtures (no `.edges.yaml`
sibling). Also rewrite `test_cli_dag_number_is_idempotent` in `test_cli.py` to a
DOT-only fixture — it is YAML-default today and the Step 5 GREEN run below exercises
it. `number` now discovers via the DOT-based `_discover_slugs` inherited from
render (Task 4), so number fixtures need a `<slug>.dot` present.

In `science/tests/dag/test_cli.py`, update `test_cli_dag_init_scaffolds_new_dag`:

```python
def test_cli_dag_init_scaffolds_new_dag(cli_project: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["dag", "init", "h3-new-hypothesis", "--label", "H3 New", "--project", str(cli_project)]
    )
    assert result.exit_code == 0, result.output
    dot = cli_project / "doc/figures/dags/h3-new-hypothesis.dot"
    yaml_file = cli_project / "doc/figures/dags/h3-new-hypothesis.edges.yaml"
    assert dot.exists()
    assert not yaml_file.exists()
    assert "workbench" in result.output.lower() or "proposition" in result.output.lower()
```

Add CLI force-stubs test:

```python
def test_cli_dag_number_force_stubs_is_retired(cli_project: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["dag", "number", "--force-stubs", "--project", str(cli_project)],
    )

    assert result.exit_code != 0
    assert "retired" in result.output.lower()
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_number.py::test_number_one_does_not_create_edges_yaml_for_new_dot science/tests/dag/test_number.py::test_number_one_force_stubs_is_retired science/tests/dag/test_cli.py::test_cli_dag_init_scaffolds_new_dag science/tests/dag/test_cli.py::test_cli_dag_number_force_stubs_is_retired -q
```

Expected: FAIL because number/init still create retired YAML and force-stubs still resets curation.

- [ ] **Step 3: Implement number-only DOT behavior**

In `science/src/science_tool/dag/number.py`, update `number_one`:

```python
def number_one(
    dag_dir: Path,
    slug: str,
    *,
    force_stubs: bool = False,
    proposition_edges: list[dict] | None = None,
) -> None:
    """Number edges in one DAG's .dot without writing retired edges.yaml."""
    if force_stubs:
        raise ValueError(
            "`science dag number --force-stubs` is retired: *.edges.yaml is no longer "
            "a DAG authoring surface. Author relational propositions through workbench rows."
        )
    dot_path = dag_dir / f"{slug}.dot"
    parsed = _parse_dag(dot_path)
    _emit_numbered_dot(dot_path, parsed, dag_dir / f"{slug}-numbered.dot")
```

No `_discover_slugs` change is needed in `number.py`: it already imports
`_discover_slugs` from `render.py`, so `number_all` automatically inherits the
DOT-based discovery introduced in Task 4. `number_all` also still accepts and
forwards `force_stubs`/`proposition_edges` to `number_one`, so the CLI
`--force-stubs` path reaches the new hard error unchanged.

- [ ] **Step 4: Implement DOT-only init**

In `science/src/science_tool/dag/init.py`, remove YAML writing:

```python
def init_dag(dag_dir: Path, slug: str, label: str | None = None) -> None:
    dot_path = dag_dir / f"{slug}.dot"
    if dot_path.exists():
        raise FileExistsError(f"{dot_path} already exists; refusing to overwrite.")

    effective_label = label if label is not None else slug
    graph_name = slug.replace("-", "_")
    dot_content = f"""\
// {slug} — {effective_label}
digraph {graph_name} {{
  rankdir=TB;
  labelloc="t";
  label=<<b>{effective_label}</b>>;
  node [shape=box, style="rounded,filled", fillcolor="#f0f0f0", fontsize=10];
  edge [fontsize=9];

  // Add nodes and edges here.
}}
"""
    dot_path.write_text(dot_content, encoding="utf-8")
```

Remove the unused `yaml` import.

In `science/src/science_tool/dag/cli.py`, update `init_cmd` output:

```python
    dot_path = paths.dag_dir / f"{slug}.dot"
    click.echo(f"Created {dot_path.relative_to(project)}")
    click.echo("")
    click.echo("Next steps: add DOT topology, then author matching relational proposition rows in a workbench.")
    click.echo(f"  science dag number --dag {slug}")
    click.echo(f"  science dag render --dag {slug}")
```

- [ ] **Step 5: Run GREEN number/init tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_number.py science/tests/dag/test_cli.py::test_cli_dag_init_scaffolds_new_dag science/tests/dag/test_cli.py::test_cli_dag_number_force_stubs_is_retired science/tests/dag/test_cli.py::test_cli_dag_number_is_idempotent -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
rtk git add science/src/science_tool/dag/number.py science/src/science_tool/dag/init.py science/src/science_tool/dag/cli.py science/tests/dag/test_number.py science/tests/dag/test_cli.py
rtk git commit -m "feat: stop writing retired DAG edge YAML"
```

Expected: commit succeeds.

---

## Task 6: Proposition-Backed DAG Validation

**Files:**
- Modify: `science/src/science_tool/dag/validate.py`
- Test: `science/tests/dag/test_validate.py` (append new tests + migrate the 20 YAML-default tests per Existing Test Disposition)
- Test: `science/tests/dag/test_validate_cli.py` (migrate the 7 YAML-default tests; verify the 2 schema tests stay green with the stderr banner)

> `DagPaths.project_root` was added in Task 4 (Step 5b). This task consumes it;
> `paths.py` needs no further change here.

> Fixture note (verified): a hand-written `entities/propositions/<slug>.md` with
> minimal frontmatter (`kind/id/type/subject/predicate/object/polarity/claim_layer/
> identification_strength`, no `title`) IS loaded by `load_local_entity_index` and
> materializes as a `PropositionEntity` with those fields populated. The Task 6
> `_write_proposition` helper is sound as written.

- [ ] **Step 1: Add failing validation tests**

Append to `science/tests/dag/test_validate.py`:

```python
def _write_project_manifest(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / "science.yaml").write_text(
        "name: dag-validation-test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _write_proposition(project: Path, slug: str, subject: str, obj: str, *, legacy_patch: str | None = None, legacy_edge_id: int | None = None) -> None:
    prop = project / "entities/propositions" / f"{slug}.md"
    prop.parent.mkdir(parents=True, exist_ok=True)  # exist_ok: tests may write >1 proposition
    extra = ""
    if legacy_patch is not None:
        extra += f"legacy_patch: {legacy_patch}\n"
    if legacy_edge_id is not None:
        extra += f"legacy_edge_id: {legacy_edge_id}\n"
    prop.write_text(
        f"""---
kind: proposition
id: proposition:{slug}
type: proposition
subject: {subject}
predicate: affects
object: {obj}
polarity: positive
claim_layer: causal_effect
identification_strength: observational
{extra}---

Body.
""",
        encoding="utf-8",
    )


def test_validate_flags_dot_edge_without_matching_proposition(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")

    report = validate_project(load_dag_paths(project))

    assert not report.ok
    finding = next(f for f in report.findings if f.rule == "proposition_edge_missing")
    assert finding.dag == "h1"
    assert "a -> b" in finding.message


def test_validate_ignores_malformed_edges_yaml_when_dot_and_proposition_are_valid(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text("not: [valid", encoding="utf-8")
    _write_proposition(project, "a-affects-b", "a", "b")

    report = validate_project(load_dag_paths(project))

    assert report.ok, report.findings


def test_validate_legacy_patch_edge_mismatch_when_referenced_dot_exists(tmp_path: Path) -> None:
    # h2.dot EXISTS but does not contain the proposition's a -> b edge → error.
    project = tmp_path / "project"
    _write_project_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "h2.dot").write_text("digraph h2 {\n  x -> y;\n}\n", encoding="utf-8")
    # Back h2's own DOT edge so proposition_edge_missing does not fire for x -> y.
    _write_proposition(project, "x-affects-y", "x", "y")
    # This proposition claims legacy identity in h2 but its edge is not in h2.dot.
    _write_proposition(project, "a-affects-b", "a", "b", legacy_patch="h2", legacy_edge_id=1)

    report = validate_project(load_dag_paths(project))

    assert not report.ok
    finding = next(f for f in report.findings if f.rule == "legacy_dag_edge_unresolved")
    assert "h2#1" in finding.message


def test_validate_legacy_patch_skipped_when_referenced_dot_absent(tmp_path: Path) -> None:
    # legacy_patch names a DAG with NO .dot in this project → design says skip, no error.
    # (Migrated propositions routinely carry legacy_patch provenance for DAGs that are
    # not currently rendered; that must not fail validation.)
    project = tmp_path / "project"
    _write_project_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    _write_proposition(project, "a-affects-b", "a", "b", legacy_patch="h2", legacy_edge_id=1)

    report = validate_project(load_dag_paths(project))

    assert report.ok, report.findings
    assert not any(f.rule == "legacy_dag_edge_unresolved" for f in report.findings)
```

- [ ] **Step 2: Run RED validation tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_validate.py::test_validate_flags_dot_edge_without_matching_proposition science/tests/dag/test_validate.py::test_validate_ignores_malformed_edges_yaml_when_dot_and_proposition_are_valid science/tests/dag/test_validate.py::test_validate_legacy_patch_edge_mismatch_when_referenced_dot_exists science/tests/dag/test_validate.py::test_validate_legacy_patch_skipped_when_referenced_dot_absent -q
```

Expected: FAIL because validation still reads YAML and does not check proposition backing.

- [ ] **Step 3: Update `DagPaths` documentation**

The `project_root` field and both `load_dag_paths` branches were added in Task 4
(Step 5b). Here, only refresh the `paths.py` wording so it no longer describes
`*.edges.yaml` as the discovery surface:

```python
    dags: tuple[str, ...] | None  # None = auto-discover all <slug>.dot files
```

```python
    Falls back to defaults when the ``dag:`` block is absent. A project with
    no ``dag:`` block and no ``*.dot`` DAG files is a valid empty state:
    auto-discover yields zero slugs and audit/validate return clean results.
```

- [ ] **Step 4: Replace default validation with DOT/proposition checks**

In `science/src/science_tool/dag/validate.py`, keep `ValidationFinding`, `ValidationReport`, `_parse_dot_topology`, `_find_cycle`, `_check_cross_dag_node_consistency`, and `validate_project`. Remove default use of `EdgesYamlFile`, YAML shape checks, JSON schema checks, ref checks, posterior checks, and identification/description checks.

Add helpers:

```python
from science_tool.dag.proposition_edges import load_relational_propositions
```

```python
def _discover_dot_files(paths: DagPaths) -> list[Path]:
    if paths.dags is not None:
        return [paths.dag_dir / f"{slug}.dot" for slug in paths.dags]
    return sorted(
        path
        for path in paths.dag_dir.glob("*.dot")
        if not path.name.endswith(("-auto.dot", "-numbered.dot", ".reference"))
    )


def _project_root_from_paths(paths: DagPaths) -> Path:
    # load_dag_paths sets project_root explicitly; the parents[2] fallback is only
    # for directly-constructed DagPaths in tests using the default doc/figures/dags
    # layout. Do NOT rely on parents[2] alone — it breaks under a configured dag_dir.
    return paths.project_root or paths.dag_dir.parents[2]
```

Then rewrite `validate_project`:

```python
def validate_project(
    paths: DagPaths,
    *,
    strict: bool = False,
    today: date | None = None,
) -> ValidationReport:
    if today is None:
        today = date.today()
    project_root = _project_root_from_paths(paths)
    findings: list[ValidationFinding] = []
    per_dag_nodes: dict[str, frozenset[str]] = {}
    per_dag_edges: dict[str, frozenset[tuple[str, str]]] = {}

    dot_files = _discover_dot_files(paths)
    propositions = load_relational_propositions(project_root)
    proposition_pairs = {(prop.subject, prop.object) for prop in propositions}

    for dot_path in dot_files:
        dag = dot_path.stem
        if not dot_path.exists():
            findings.append(
                ValidationFinding(
                    dag=dag,
                    edge_id=None,
                    rule="source_dot_missing",
                    severity="error",
                    message=f"source .dot file not found: {dot_path}",
                    location=dot_path.name,
                )
            )
            continue
        dot_nodes, dot_edges = _parse_dot_topology(dot_path)
        per_dag_nodes[dag] = dot_nodes
        per_dag_edges[dag] = dot_edges
        findings.extend(_check_acyclicity_for_dot(dag, dot_edges, dot_path))
        if strict:
            findings.extend(_check_orphan_dot_nodes_for_dot(dag, dot_nodes, dot_edges, dot_path))
        for src, tgt in sorted(dot_edges):
            if (src, tgt) not in proposition_pairs:
                findings.append(
                    ValidationFinding(
                        dag=dag,
                        edge_id=None,
                        rule="proposition_edge_missing",
                        severity="error",
                        message=(
                            f"DOT edge {src!r} -> {tgt!r} has no compiled relational proposition. "
                            "Author or compile a matching workbench row."
                        ),
                        location=dot_path.name,
                    )
                )

    findings.extend(_check_legacy_dag_metadata(propositions, per_dag_edges))
    if strict:
        findings.extend(_check_cross_dag_node_consistency(per_dag_nodes))
    return ValidationReport(today=today, strict=strict, findings=tuple(findings))
```

Add DOT-specific wrappers:

```python
def _check_acyclicity_for_dot(
    dag: str,
    dot_edges: frozenset[tuple[str, str]],
    dot_path: Path,
) -> list[ValidationFinding]:
    cycle = _find_cycle(dot_edges)
    if cycle is None:
        return []
    return [
        ValidationFinding(
            dag=dag,
            edge_id=None,
            rule="acyclicity",
            severity="error",
            message=f"cycle detected in .dot topology: {' -> '.join(cycle)}",
            location=dot_path.name,
        )
    ]


def _check_orphan_dot_nodes_for_dot(
    dag: str,
    dot_nodes: frozenset[str],
    dot_edges: frozenset[tuple[str, str]],
    dot_path: Path,
) -> list[ValidationFinding]:
    connected = {node for edge in dot_edges for node in edge}
    orphans = sorted(dot_nodes - connected)
    if not orphans:
        return []
    return [
        ValidationFinding(
            dag=dag,
            edge_id=None,
            rule="dot_nodes_unused",
            severity="strict_error",
            message=f"orphan .dot node(s): {orphans}",
            location=dot_path.name,
        )
    ]
```

Add legacy metadata validation:

```python
def _check_legacy_dag_metadata(
    propositions: list,
    per_dag_edges: dict[str, frozenset[tuple[str, str]]],
) -> list[ValidationFinding]:
    """Validate a proposition's claimed legacy DAG identity ONLY when the
    referenced DOT exists in this project.

    Design contract: a proposition that claims a migrated DAG identity via
    ``legacy_patch``/``legacy_edge_id`` "must resolve to a real DOT edge IF the
    referenced DOT exists." Migrated propositions routinely carry ``legacy_patch``
    provenance for DAGs that are no longer rendered as ``.dot`` files — those MUST
    be skipped, not flagged, or ``dag validate`` fails on every mid-migration
    project. So: no ``legacy_patch`` → skip; ``legacy_patch`` names no known DOT →
    skip; DOT exists but the proposition's ``(subject, object)`` is not one of its
    edges → error.
    """
    findings: list[ValidationFinding] = []
    for prop in propositions:
        patch = getattr(prop, "legacy_patch", None)
        if patch is None or patch not in per_dag_edges:
            continue  # no claimed identity, or the referenced DOT does not exist here
        edge_id = getattr(prop, "legacy_edge_id", None)
        if (prop.subject, prop.object) not in per_dag_edges[patch]:
            findings.append(
                ValidationFinding(
                    dag=patch,
                    edge_id=edge_id if isinstance(edge_id, int) else None,
                    rule="legacy_dag_edge_unresolved",
                    severity="error",
                    message=(
                        f"proposition {prop.id} claims legacy DAG identity {patch}#{edge_id} "
                        f"but its edge {prop.subject!r} -> {prop.object!r} is not in {patch}.dot"
                    ),
                    location=None,
                )
            )
    return findings
```

> Note: `legacy_edge_id` is carried into the message for traceability but is NOT
> used to resolve the edge — resolution is by `(subject, object)` against the DOT
> topology, matching how `proposition_edge_missing` matches. A proposition with a
> `legacy_patch` whose DOT exists but no `legacy_edge_id` is still checked by edge
> membership; the design does not require erroring on missing `legacy_edge_id`
> alone.

- [ ] **Step 5: Run GREEN validation tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_validate.py science/tests/dag/test_validate_cli.py -q
```

Expected: PASS after migrating the 20 `test_validate.py` + 7 `test_validate_cli.py` YAML-default tests (per Existing Test Disposition) to DOT/proposition assertions. Keep these old YAML behaviors only in retired-surface tests: schema emission belongs to `test_cli.py::test_cli_dag_schema_says_schema_is_retired`; retired YAML content scanning belongs to `test_retired_edges.py`; default `validate_project()` must not parse malformed YAML.

- [ ] **Step 6: Commit Task 6**

Run:

```bash
rtk git add science/src/science_tool/dag/validate.py science/src/science_tool/dag/paths.py science/tests/dag/test_validate.py science/tests/dag/test_validate_cli.py
rtk git commit -m "feat: validate DAGs from proposition edges"
```

Expected: commit succeeds.

---

## Task 7: Audit And Staleness Retire YAML Drift

> **This is the load-bearing task for the design goal.** After Phase 5f, `dag
> audit` must NOT read retired YAML at all. Today `run_audit` calls
> `check_staleness` (`audit.py:229`), which reads `*.edges.yaml`, and
> `AuditReport` carries a required `staleness` field consumed by `to_json`,
> `has_findings`, and the CLI. Threading proposition edges into render (Task 4) is
> necessary but NOT sufficient — this task must also REMOVE the staleness
> composition from `run_audit`/`AuditReport`/`audit_cmd`, or audit still reads
> retired YAML and the acceptance criteria fail. The `check_staleness` FUNCTION
> stays in `staleness.py` (its unit tests in `test_staleness.py` remain green); only
> its use as a default audit/CLI surface is retired.

**Files:**
- Modify: `science/src/science_tool/dag/audit.py` (drop staleness from `run_audit` + `AuditReport`; delete dead YAML-drift helpers)
- Modify: `science/src/science_tool/dag/cli.py` (retire `staleness_cmd`; drop `--recent-days` + `_print_staleness_summary` from `audit_cmd`; delete the now-dead `_print_staleness_summary`)
- Test: `science/tests/dag/test_cli.py` (staleness-retired test + migrate `test_dag_audit_accepts_format_json`, `test_cli_dag_audit_is_read_only_by_default`; delete `test_cli_dag_audit_fix_mutates`, `test_cli_dag_staleness_json_schema`, `test_dag_staleness_accepts_format_json`)
- Test: `science/tests/dag/test_audit.py` (assert audit renders from propositions AND composes no staleness)

- [ ] **Step 1: Add failing CLI staleness retirement test**

In `science/tests/dag/test_cli.py`, replace the current staleness JSON expectations with:

```python
def test_cli_dag_staleness_is_retired(cli_project: Path) -> None:
    result = CliRunner().invoke(main, ["dag", "staleness", "--project", str(cli_project)])

    assert result.exit_code != 0
    assert "retired" in result.output.lower()
    assert "retired-edges" in result.output
```

Remove or rewrite `test_cli_dag_staleness_json_schema`, `test_dag_staleness_accepts_format_json`, and `test_cli_dag_staleness_exit_code_on_clean_project`; default staleness no longer returns the old YAML report.

- [ ] **Step 2: Add audit render-threading + no-staleness regression test**

In `science/tests/dag/test_audit.py`, add. This asserts both halves of the design
goal: audit renders from proposition edges AND composes no YAML staleness. Do NOT
monkeypatch `check_staleness` — after this task `run_audit` must not call it, and
`AuditReport` must not carry a `staleness` field.

```python
def test_audit_renders_from_propositions_and_composes_no_staleness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.dag import audit as audit_mod
    from science_tool.dag.paths import DagPaths

    project = tmp_path / "project"
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    tasks_dir = project / "tasks"
    tasks_dir.mkdir()
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    # A stray retired YAML must be ignored by audit entirely.
    (dag_dir / "h1.edges.yaml").write_text(
        "dag: h1\nedges:\n  - id: 1\n    source: a\n    target: b\n    edge_status: supported\n",
        encoding="utf-8",
    )

    seen = {}

    def fake_render_all(paths, *, proposition_edges):
        seen["edges"] = proposition_edges

    monkeypatch.setattr(audit_mod, "render_all", fake_render_all)
    monkeypatch.setattr(
        audit_mod, "load_proposition_edges", lambda _project: [{"source": "a", "target": "b"}]
    )
    # check_staleness must no longer be imported/called by audit; guard against it.
    assert not hasattr(audit_mod, "check_staleness")

    report = audit_mod.run_audit(
        DagPaths(dag_dir=dag_dir, tasks_dir=tasks_dir, dags=None, project_root=project)
    )

    assert seen["edges"] == [{"source": "a", "target": "b"}]
    assert not hasattr(report, "staleness")
    assert "staleness" not in report.to_json()
```

- [ ] **Step 3: Run RED tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_cli.py::test_cli_dag_staleness_is_retired science/tests/dag/test_audit.py::test_audit_renders_from_propositions_and_composes_no_staleness -q
```

Expected: FAIL because `staleness_cmd` still runs the YAML report, and `run_audit`
still imports/calls `check_staleness` and returns an `AuditReport` with a
`staleness` field (so the `not hasattr(...)` / `"staleness" not in to_json()`
assertions fail).

- [ ] **Step 4: Retire staleness CLI**

In `science/src/science_tool/dag/cli.py`, replace `staleness_cmd` body after path loading with:

```python
    raise click.ClickException(
        "DAG staleness over *.edges.yaml is retired. Run `science dag retired-edges` "
        "to inspect remaining YAML migration content. Proposition-backed freshness "
        "will be designed separately."
    )
```

Keep the command registered so existing callers get an actionable failure instead of "unknown command."

- [ ] **Step 5: Remove YAML staleness composition from audit**

The render-threading was already added in Task 4 (Step 5c). This step removes the
staleness composition so audit stops reading retired YAML.

In `science/src/science_tool/dag/audit.py`:

1. Drop the staleness import. Change
   `from science_tool.dag.staleness import (DriftedEdge, StalenessReport, UnpropagatedTask, check_staleness)`
   to remove `StalenessReport` and `check_staleness` (and `DriftedEdge` /
   `UnpropagatedTask` once their only users — the mutation helpers below — are
   gone). After this, `hasattr(audit_mod, "check_staleness")` is False (the Step 2
   guard).
2. Remove the `staleness` field from `AuditReport`; make `has_findings` return
   `not self.validation.ok`; drop the `"staleness"` key from `to_json`.
3. In `run_audit`, delete the `check_staleness(...)` call and the entire `fix=True`
   mutation block (it consumed `staleness.drifted_edges` / `unpropagated_tasks`).
   Drop the now-unused `recent_days` and `include_curation_freshness` params.
   `run_audit` becomes:

```python
def run_audit(paths, *, today=None, fix=False, strict=False) -> AuditReport:
    if today is None:
        today = date.today()
    validation = validate_project(paths, strict=strict, today=today)
    if fix and not validation.ok:
        blocking = [f for f in validation.findings if validation._blocks(f)]
        raise RuntimeError(
            "dag audit --fix refused: validation failed with "
            f"{len(blocking)} blocking finding(s). Run `science dag validate` first."
        )
    project_root = paths.project_root or paths.dag_dir.parents[2]
    render_all(paths, proposition_edges=load_proposition_edges(project_root))
    # --fix is a no-op in Phase 5f: no proposition-backed mutation model exists yet.
    return AuditReport(validation=validation, mutations=())
```

4. Delete the now-dead helpers `_build_drift_mutation`, `_build_unpropagated_mutation`,
   `_open_review_task`, and `_write_unpropagated_log` (verify no other module
   imports them), plus any now-unused imports (`_tasks_mod`, `UnpropagatedTask`,
   `DriftedEdge`).

- [ ] **Step 5b: Drop staleness from the audit CLI**

`staleness_cmd` was already retired in Step 4. Additionally, in
`science/src/science_tool/dag/cli.py`:

1. In `audit_cmd`, remove the `_print_staleness_summary(audit.staleness)` call
   (~line 271) and remove the `--recent-days` option and its `recent_days`
   parameter (staleness is gone; update the `run_audit(...)` call to drop it). The
   audit docstring/help should no longer mention staleness.
2. Delete the now-dead `_print_staleness_summary` helper (~line 495); its only two
   callers (`staleness_cmd`, `audit_cmd`) no longer reference it.

- [ ] **Step 6: Run GREEN audit/staleness tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_audit.py science/tests/dag/test_cli.py science/tests/dag/test_staleness.py -q
```

Expected: PASS after (a) migrating the `test_cli.py` audit/staleness tests per the
Existing Test Disposition section (delete `test_cli_dag_audit_fix_mutates`,
`test_cli_dag_staleness_json_schema`, `test_dag_staleness_accepts_format_json`;
rewrite `test_dag_audit_accepts_format_json` and
`test_cli_dag_audit_is_read_only_by_default` without a `staleness` key), and (b)
confirming `test_staleness.py` is still GREEN unchanged — the `check_staleness`
function is retained, only its default surface retired.

- [ ] **Step 7: Commit Task 7**

Run:

```bash
rtk git add science/src/science_tool/dag/audit.py science/src/science_tool/dag/cli.py science/tests/dag/test_cli.py science/tests/dag/test_audit.py
rtk git commit -m "feat: retire YAML DAG staleness defaults"
```

Expected: commit succeeds.

---

## Task 8: Inventory Stops Emitting Retired DAG Edge Addresses

**Files:**
- Modify: `science/src/science_tool/dag/inventory.py`
- Modify: `science/src/science_tool/entities_inventory.py` only if the empty DAG records path needs simplification.
- Test: `science/tests/dag/test_dag_inventory.py`
- Test: `science/tests/test_entities_inventory.py`

- [ ] **Step 1: Update failing inventory tests**

Replace `science/tests/dag/test_dag_inventory.py` expectations with one explicit no-op test:

```python
def test_dag_inventory_ignores_retired_edges_yaml(tmp_path) -> None:
    project = tmp_path / "project"
    dag_path = project / "doc" / "figures" / "dags" / "h4.edges.yaml"
    dag_path.parent.mkdir(parents=True)
    dag_path.write_text(
        """
edges:
  - id: e001
    source: landscape
    target: attractor
    relation: converges_to
    interpretation: Retired YAML must not produce inventory candidates.
""".strip(),
        encoding="utf-8",
    )

    records = load_dag_inventory_records(project)

    assert records.graph_addresses == []
    assert records.finding_candidates == []
    assert records.warnings == []
```

In `science/tests/test_entities_inventory.py`, update `test_build_inventory_includes_entities_aliases_dag_candidates_and_watch_paths` to remove the YAML file setup and these assertions:

```python
    assert inventory.graph_addresses == []
    assert inventory.finding_candidates == []
```

Keep the entity, alias, and watch path assertions.

- [ ] **Step 2: Run RED inventory tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_dag_inventory.py science/tests/test_entities_inventory.py::test_build_inventory_includes_entities_aliases_dag_candidates_and_watch_paths -q
```

Expected: FAIL until inventory stops scanning retired YAML.

- [ ] **Step 3: Implement no-op DAG inventory**

In `science/src/science_tool/dag/inventory.py`, make the default loader explicit:

```python
def load_dag_inventory_records(project_root: Path) -> DagInventoryRecords:
    """Return no graph addresses from retired DAG edge YAML.

    DAG semantic edges are compiled propositions and are already represented in
    entity inventory. Retired ``*.edges.yaml`` files are visible only through
    ``science dag retired-edges``.
    """
    return DagInventoryRecords()
```

Remove unused imports from this module.

- [ ] **Step 4: Run GREEN inventory tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_dag_inventory.py science/tests/test_entities_inventory.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 8**

Run:

```bash
rtk git add science/src/science_tool/dag/inventory.py science/tests/dag/test_dag_inventory.py science/tests/test_entities_inventory.py
rtk git commit -m "feat: remove retired DAG edges from inventory"
```

Expected: commit succeeds.

---

## Task 9: Documentation And Command Help Refresh

**Files:**
- Modify: `docs/user-guide/big-picture-synthesis.md`
- Modify: `docs/audits/downstream-project-conventions/projects/mm30.md`
- Modify: `docs/audits/downstream-project-conventions/projects/protein-landscape.md`
- Modify: `science/src/science_tool/dag/cli.py` command docstrings/help text if not fully updated in earlier tasks.

- [ ] **Step 1: Update docs wording**

In `docs/user-guide/big-picture-synthesis.md`, replace the line that lists structured DAG edge files as an active surface:

```markdown
2. Relational propositions compiled from patch workbenches; DAG DOT files are
   view topology only.
```

In the downstream convention notes, reword `.edges.yaml` sections to say they are retired migration inputs. Use `~/d/` style for any example local paths, not `/home/keith/d/` or `/mnt/ssd/Dropbox/`.

- [ ] **Step 2: Update CLI help text**

In `science/src/science_tool/dag/cli.py`:

- `render_cmd` help should say it renders from compiled relational propositions.
- `number_cmd` help should say it writes numbered DOT only.
- `init_cmd` help should say it scaffolds DOT topology only.
- `validate_cmd` help should say it validates DOT topology against compiled propositions.
- `staleness_cmd` help should say the old YAML staleness surface is retired.
- `audit_cmd` help should not promise YAML staleness or edge-review task mutation.

- [ ] **Step 3: Run doc/help grep**

Run:

```bash
rtk rg -n "structured DAG edge files|active DAG convention|edge_status: supported|dag schema.*active|edges.yaml.*source-of-truth|\\.edges\\.yaml.*normal|\\.edges\\.yaml.*active" docs science/src/science_tool/dag/cli.py
```

Expected: no hits that describe `*.edges.yaml` as an active/normal/default DAG source. Hits that explicitly say retired are acceptable.

- [ ] **Step 4: Commit Task 9**

Run:

```bash
rtk git add docs/user-guide/big-picture-synthesis.md docs/audits/downstream-project-conventions/projects/mm30.md docs/audits/downstream-project-conventions/projects/protein-landscape.md science/src/science_tool/dag/cli.py
rtk git commit -m "docs: document DAG edge YAML retirement"
```

Expected: commit succeeds.

---

## Task 10: Focused And Full Verification

**Files:**
- No planned source changes unless verification exposes defects.

- [ ] **Step 1: Run focused DAG suite**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_edges_yaml_retired.py \
  science/tests/test_epistemic_edges_e2e.py \
  science/tests/dag/test_retired_edges.py \
  science/tests/dag/test_render.py \
  science/tests/dag/test_validate.py \
  science/tests/dag/test_validate_cli.py \
  science/tests/dag/test_number.py \
  science/tests/dag/test_cli.py \
  science/tests/dag/test_audit.py \
  science/tests/dag/test_staleness.py \
  science/tests/dag/test_dag_inventory.py \
  science/tests/test_entities_inventory.py \
  -q
```

Expected: PASS. Default render/validate/number/init/inventory tests should not emit retirement warnings. Tests that deliberately inspect retired YAML may still exercise retired YAML parsing.

- [ ] **Step 2: Run lint and type checks**

Run:

```bash
rtk uv run --frozen --project science ruff check \
  science/src/science_tool/dag \
  science/tests/dag \
  science/tests/test_edges_yaml_retired.py \
  science/tests/test_entities_inventory.py
rtk uv run --frozen --project science pyright \
  science/src/science_tool/dag \
  science/tests/dag \
  science/tests/test_edges_yaml_retired.py \
  science/tests/test_entities_inventory.py
```

Expected: both commands pass.

- [ ] **Step 3: Run full test suite**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests -q
```

Expected: PASS.

- [ ] **Step 4: Real-project retired-edge smoke**

Run the new migration report on the current repo project and any checked-out downstream fixtures available in the workspace:

```bash
rtk uv run --frozen --project science science dag retired-edges --project . --format json
```

Expected: command exits 0 and reports any remaining retired YAML without affecting default DAG command behavior. Treat counts as observational, not hard-coded invariants.

- [ ] **Step 5: Real default-command smoke**

Run:

```bash
rtk uv run --frozen --project science science dag validate --project . --format json
```

Expected: If the current project has DOT edges without compiled proposition backing, command exits nonzero with `proposition_edge_missing` findings. That is acceptable under Phase 5f; inspect the JSON to ensure it fails for the new explicit reason, not because it tried to parse retired YAML.

- [ ] **Step 6: Commit verification fixes**

If verification required source or test fixes, inspect and commit the known Phase 5f paths:

```bash
rtk git status --short
rtk git add \
  science/src/science_tool/dag \
  science/tests/dag \
  science/tests/test_edges_yaml_retired.py \
  science/tests/test_entities_inventory.py \
  docs/user-guide/big-picture-synthesis.md \
  docs/audits/downstream-project-conventions/projects/mm30.md \
  docs/audits/downstream-project-conventions/projects/protein-landscape.md
rtk git commit -m "test: stabilize DAG edge retirement verification"
```

Expected: commit succeeds when verification produced changes. If `rtk git status --short` prints `ok` before `git add`, skip this step.

- [ ] **Step 7: Final status**

Run:

```bash
rtk git status --short
rtk git log --oneline -6
```

Expected: status clean; recent commits correspond to Tasks 1-9 plus optional verification fix.

---

## Self-Review Notes

- The plan implements the spec's sequencing requirement by adding `retired-edges` before flipping render/validate/audit defaults.
- The plan removes the empty-list-to-`None` sentinel so zero compiled propositions fails loudly instead of selecting retired YAML.
- `dag audit` is fully de-YAML'd: Task 4 threads proposition edges into its render, and Task 7 REMOVES the `check_staleness` composition and the `AuditReport.staleness` field so audit no longer reads retired YAML. `--fix` becomes a no-op. The `check_staleness` function is retained for its own unit tests only.
- `dag schema` is not deleted; its JSON output stays pure (banner to stderr) so the schema-drift guard and `test_validate_cli.py` schema tests stay green, while the terminal message states the schema is retired.
- Ordering is explicit: making `proposition_edges` required (Task 4) is paired with threading it into `run_audit` in the SAME task, so no commit leaves the suite red between Task 4 and Task 7.
- Project root is threaded via `DagPaths.project_root` (set by `load_dag_paths`) rather than reverse-derived from `dag_dir` depth, which would break under a configured `dag_dir`.
- Render's fail-loud preflight reuses `validate._parse_dot_topology`; there is exactly one DOT-edge parser, so render and validate agree on "what is a DOT edge."
- The 59 existing YAML-default tests are not blindly deleted: the Existing Test Disposition section assigns each a fate (DEL / DOT / PROP) inside the owning task's commit, and the two previously-missed files (`test_validate_cli.py`, `test_staleness.py`) are now in scope.
- The `entities/propositions/*.md` fixture assumption in Task 6 was verified live against `load_local_entity_index` before relying on it (both a `profile: research` and a `knowledge_profiles` manifest load cleanly, returning an empty index rather than raising).
- Legacy-metadata validation honors the design's "if the referenced DOT exists" guard: `_check_legacy_dag_metadata` SKIPS a proposition whose `legacy_patch` names no current `.dot` (the common mid-migration provenance case) and errors only on a genuine edge mismatch when the DOT is present. Two tests lock both branches. The `_write_proposition` helper uses `exist_ok=True` so a test can write more than one proposition.
