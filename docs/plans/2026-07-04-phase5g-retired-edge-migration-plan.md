# Phase 5g Retired DAG Edge Migration Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only `science dag retired-edge-migration-plan` surface that turns retired `*.edges.yaml` rows into deterministic migration diagnostics and optional strict workbench YAML drafts.

**Architecture:** Keep default DAG commands isolated from retired YAML. Add a new focused planner module that shares retired-file discovery with `retired-edges`, but validates each migratable row through the stricter `EdgeRecord` schema because migration planning needs rich row fields. Add a flat Click command that renders JSON, table, or workbench YAML without writing or compiling anything.

**Tech Stack:** Python 3.13, dataclasses, Click, Pydantic v2 models, PyYAML, existing DAG `EdgeRecord` / `WorkbenchFile` / proposition-edge helpers, pytest, ruff, pyright.

---

## File Structure

- Create: `science/src/science_tool/dag/retired_edge_migration.py`
  - Owns all Phase 5g planning data structures and pure functions.
  - Reads retired YAML only through explicit planner calls.
  - Produces JSON-ready payloads, table text, and strict `WorkbenchFile` YAML text.
- Modify: `science/src/science_tool/dag/cli.py`
  - Adds the flat `dag retired-edge-migration-plan` command.
  - Delegates all business logic to `retired_edge_migration.py`.
- Modify: `science/src/science_tool/dag/__init__.py`
  - Optionally exports planner functions after the module exists. Keep exports minimal.
- Create: `science/tests/dag/test_retired_edge_migration.py`
  - Core planner tests: classification, mapping, strict parsing, workbench rendering.
- Modify: `science/tests/dag/test_cli.py`
  - CLI tests for JSON, table, and workbench output.

Do not modify default render/validate/audit/number/init/inventory paths. Phase 5g is an additive explicit migration planner.

---

### Task 1: Core Planner With Classification And JSON Payload

**Files:**
- Create: `science/src/science_tool/dag/retired_edge_migration.py`
- Create: `science/tests/dag/test_retired_edge_migration.py`

- [ ] **Step 1: Add failing core planner tests**

Create `science/tests/dag/test_retired_edge_migration.py` with this content:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.dag.retired_edge_migration import build_retired_edge_migration_plan


def _write_manifest(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")


def _dag_dir(project: Path) -> Path:
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True, exist_ok=True)
    return dag_dir


def _write_retired_edge_project(project: Path) -> None:
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
    original_label: biases
    edge_status: supported
    identification: observational
    description: A retired claim that should become a reviewed migration row.
    data_support:
      - task: t001
        description: Completed task support.
    lit_support:
      - paper: Smith2020
        description: Literature support.
""".strip(),
        encoding="utf-8",
    )


def test_plan_blocks_migrated_row_without_focal_hypothesis(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)

    plan = build_retired_edge_migration_plan(project)
    payload = plan.to_json()

    assert payload["summary"] == {
        "files": 1,
        "rows": 1,
        "ready": 0,
        "blocked": 1,
        "skipped": 0,
        "predicate_review_required": 1,
        "membership_required": 1,
        "evidence_warnings": 0,
    }
    row = payload["rows"][0]
    assert row["status"] == "blocked"
    assert row["blockers"] == ["membership-required"]
    assert row["membership_required"] is True
    assert row["predicate_review_required"] is True
    assert row["proposed_row"]["subject"] == "a"
    assert row["proposed_row"]["predicate"] == "affects"
    assert row["proposed_row"]["object"] == "b"
    assert row["proposed_row"]["legacy_relation_label"] == "biases"
    assert row["proposed_row"]["legacy_patch"] == "h1"
    assert row["proposed_row"]["legacy_edge_id"] == 1


def test_plan_ready_with_focal_hypothesis(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)

    plan = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1")
    payload = plan.to_json()

    assert payload["summary"]["ready"] == 1
    assert payload["summary"]["blocked"] == 0
    row = payload["rows"][0]
    assert row["status"] == "ready"
    assert row["blockers"] == []
    assert row["proposed_row"]["claim_layer"] == "causal_effect"
    assert row["proposed_row"]["identification_strength"] == "observational"
    assert row["proposed_row"]["polarity"] == "positive"
    assert row["proposed_row"]["evidence"] == [
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


def test_plan_skips_matching_compiled_proposition(tmp_path: Path) -> None:
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
    row = payload["rows"][0]
    assert row["status"] == "skipped"
    assert row["blockers"] == ["matching-proposition-exists"]
    assert row["matching_propositions"] == ["proposition:a-affects-b"]
    assert row["notes"] == ["matching proposition lacks legacy_patch/legacy_edge_id"]


def test_plan_blocks_orphan_dot(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "orphan.edges.yaml").write_text(
        """
dag: orphan
edges:
  - id: 1
    source: a
    target: b
    edge_status: supported
    identification: observational
    description: This row has no DOT sibling.
""".strip(),
        encoding="utf-8",
    )

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["blocked"] == 1
    assert payload["rows"][0]["blockers"] == ["dot-missing"]


def test_plan_blocks_eliminated_edge(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
edges:
  - id: 1
    source: a
    target: b
    edge_status: eliminated
    identification: observational
    description: Refuted legacy edge.
    eliminated_by:
      - task: t002
        description: Refutation.
""".strip(),
        encoding="utf-8",
    )

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["blocked"] == 1
    assert payload["rows"][0]["blockers"] == ["eliminated-edge"]


def test_plan_parses_with_schema_and_fails_loud_on_invalid_refs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
edges:
  - id: 1
    source: a
    target: b
    edge_status: supported
    identification: observational
    description: Invalid support ref should fail strict planner parsing.
    data_support:
      - description: Missing kind tag.
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid retired DAG edge file"):
        build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1")
```

- [ ] **Step 2: Run the tests and verify they fail because the module is missing**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_retired_edge_migration.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'science_tool.dag.retired_edge_migration'`.

- [ ] **Step 3: Implement the core planner module**

Create `science/src/science_tool/dag/retired_edge_migration.py` with this content:

```python
"""Read-only migration planning for retired ``*.edges.yaml`` DAG rows.

This module is the explicit Phase 5g migration surface. Default DAG render,
validate, audit, number, init, and inventory code must not import it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
import warnings

import yaml
from pydantic import ValidationError

from science_model.propositions import PropositionEntity
from science_tool.dag.paths import load_dag_paths
from science_tool.dag.schema import EdgeRecord, EdgeStatus, Identification, SchemaError
from science_tool.dag.workbench import WorkbenchFile
from science_tool.dag.proposition_edges import load_relational_propositions


MigrationStatus = Literal["ready", "blocked", "skipped"]


@dataclass(frozen=True)
class RetiredEdgeMigrationRow:
    path: str
    dag: str
    edge_id: int | None
    source: str
    target: str
    status: MigrationStatus
    blockers: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
    predicate_review_required: bool = False
    membership_required: bool = False
    evidence_warnings: tuple[str, ...] = field(default_factory=tuple)
    matching_propositions: tuple[str, ...] = field(default_factory=tuple)
    proposed_row: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "dag": self.dag,
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "status": self.status,
            "blockers": list(self.blockers),
            "notes": list(self.notes),
            "predicate_review_required": self.predicate_review_required,
            "membership_required": self.membership_required,
            "evidence_warnings": list(self.evidence_warnings),
            "matching_propositions": list(self.matching_propositions),
            "proposed_row": self.proposed_row,
        }


@dataclass(frozen=True)
class RetiredEdgeMigrationPlan:
    project_root: str
    focal_hypothesis: str | None
    rows: tuple[RetiredEdgeMigrationRow, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        counts = Counter(row.status for row in self.rows)
        return {
            "project_root": self.project_root,
            "focal_hypothesis": self.focal_hypothesis,
            "summary": {
                "files": len({row.path for row in self.rows}),
                "rows": len(self.rows),
                "ready": counts["ready"],
                "blocked": counts["blocked"],
                "skipped": counts["skipped"],
                "predicate_review_required": sum(1 for row in self.rows if row.predicate_review_required),
                "membership_required": sum(1 for row in self.rows if row.membership_required),
                "evidence_warnings": sum(len(row.evidence_warnings) for row in self.rows),
            },
            "rows": [row.to_json() for row in self.rows],
        }


def build_retired_edge_migration_plan(
    project_root: Path,
    *,
    dag: str | None = None,
    focal_hypothesis: str | None = None,
) -> RetiredEdgeMigrationPlan:
    project_root = project_root.resolve()
    dag_dir = load_dag_paths(project_root).dag_dir
    yaml_paths = [dag_dir / f"{dag}.edges.yaml"] if dag else sorted(dag_dir.glob("*.edges.yaml"))

    if dag is not None and not yaml_paths[0].exists():
        raise ValueError(f"retired DAG edge file does not exist for dag {dag!r}: {yaml_paths[0]}")

    propositions_by_pair = _propositions_by_pair(project_root)
    rows: list[RetiredEdgeMigrationRow] = []
    for yaml_path in yaml_paths:
        if not yaml_path.exists():
            continue
        payload = _load_edges_yaml_payload(yaml_path)
        dag_slug = str(payload.get("dag") or yaml_path.name.removesuffix(".edges.yaml"))
        dot_path = _resolve_dot_path(project_root, yaml_path, payload, dag_slug)
        dot_exists = bool(dot_path and dot_path.exists())
        rel_path = yaml_path.relative_to(project_root).as_posix()
        raw_edges = payload.get("edges") or []
        if not isinstance(raw_edges, list):
            raise ValueError(f"invalid retired DAG edge file {yaml_path}: edges must be a list")
        for index, raw_edge in enumerate(raw_edges, start=1):
            if not isinstance(raw_edge, dict):
                raise ValueError(f"invalid retired DAG edge file {yaml_path}: edge {index} must be a mapping")
            rows.append(
                _plan_raw_edge(
                    project_root=project_root,
                    rel_path=rel_path,
                    dag=dag_slug,
                    raw_edge=raw_edge,
                    row_index=index,
                    dot_exists=dot_exists,
                    focal_hypothesis=focal_hypothesis,
                    propositions_by_pair=propositions_by_pair,
                )
            )

    return RetiredEdgeMigrationPlan(
        project_root=project_root.as_posix(),
        focal_hypothesis=focal_hypothesis,
        rows=tuple(rows),
    )


def _load_edges_yaml_payload(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError("top-level YAML document must be a mapping")
        return payload
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid retired DAG edge file {path}: {exc}") from exc


def _validate_edge_record(path: str, raw_edge: dict[str, Any], row_index: int) -> EdgeRecord:
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=r"Edge is missing 'identification'.*", category=DeprecationWarning)
            return EdgeRecord.model_validate(raw_edge)
    except (SchemaError, TypeError, ValueError, ValidationError) as exc:
        missing = _missing_required_fields(exc)
        if missing <= {"id", "source", "target"} and missing:
            raise _MissingEdgeIdentity(missing) from exc
        raise ValueError(f"invalid retired DAG edge file {path}: edge {row_index}: {exc}") from exc


class _MissingEdgeIdentity(ValueError):
    def __init__(self, fields: set[str]) -> None:
        super().__init__(",".join(sorted(fields)))
        self.fields = fields


def _missing_required_fields(exc: BaseException) -> set[str]:
    if not isinstance(exc, ValidationError):
        return set()
    result: set[str] = set()
    for error in exc.errors():
        if error.get("type") == "missing":
            loc = error.get("loc")
            if isinstance(loc, tuple) and len(loc) == 1 and isinstance(loc[0], str):
                result.add(loc[0])
    return result


def _resolve_dot_path(project_root: Path, yaml_path: Path, payload: dict[str, Any], dag_slug: str) -> Path | None:
    source_dot = payload.get("source_dot")
    if isinstance(source_dot, str) and source_dot.strip():
        candidate = project_root / source_dot
        return candidate if candidate.exists() else yaml_path.parent / source_dot
    return yaml_path.parent / f"{dag_slug}.dot"


def _propositions_by_pair(project_root: Path) -> dict[tuple[str, str], list[PropositionEntity]]:
    result: dict[tuple[str, str], list[PropositionEntity]] = {}
    for prop in load_relational_propositions(project_root):
        if prop.subject is None or prop.object is None:
            continue
        result.setdefault((prop.subject, prop.object), []).append(prop)
    return result


def _plan_raw_edge(
    *,
    project_root: Path,
    rel_path: str,
    dag: str,
    raw_edge: dict[str, Any],
    row_index: int,
    dot_exists: bool,
    focal_hypothesis: str | None,
    propositions_by_pair: dict[tuple[str, str], list[PropositionEntity]],
) -> RetiredEdgeMigrationRow:
    try:
        edge = _validate_edge_record(rel_path, raw_edge, row_index)
    except _MissingEdgeIdentity as exc:
        blockers = tuple(f"missing-{field}" for field in sorted(exc.fields))
        return RetiredEdgeMigrationRow(
            path=rel_path,
            dag=dag,
            edge_id=_raw_int(raw_edge.get("id")),
            source=_raw_text(raw_edge.get("source")),
            target=_raw_text(raw_edge.get("target")),
            status="blocked",
            blockers=blockers,
        )
    return _plan_edge(
        project_root=project_root,
        rel_path=rel_path,
        dag=dag,
        edge=edge,
        dot_exists=dot_exists,
        focal_hypothesis=focal_hypothesis,
        propositions_by_pair=propositions_by_pair,
    )


def _raw_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _raw_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _plan_edge(
    *,
    project_root: Path,
    rel_path: str,
    dag: str,
    edge: EdgeRecord,
    dot_exists: bool,
    focal_hypothesis: str | None,
    propositions_by_pair: dict[tuple[str, str], list[PropositionEntity]],
) -> RetiredEdgeMigrationRow:
    del project_root
    source = edge.source.strip()
    target = edge.target.strip()
    blockers: list[str] = []
    notes: list[str] = []

    if not source:
        blockers.append("missing-source")
    if not target:
        blockers.append("missing-target")
    if edge.id is None:
        blockers.append("missing-edge-id")
    if not dot_exists:
        blockers.append("dot-missing")
    if edge.edge_status == EdgeStatus.eliminated:
        blockers.append("eliminated-edge")

    matches = propositions_by_pair.get((source, target), [])
    if matches:
        missing_legacy = [
            prop.id
            for prop in matches
            if getattr(prop, "legacy_patch", None) is None or getattr(prop, "legacy_edge_id", None) is None
        ]
        if missing_legacy:
            notes.append("matching proposition lacks legacy_patch/legacy_edge_id")
        return RetiredEdgeMigrationRow(
            path=rel_path,
            dag=dag,
            edge_id=edge.id,
            source=source,
            target=target,
            status="skipped",
            blockers=("matching-proposition-exists",),
            notes=tuple(notes),
            matching_propositions=tuple(sorted(prop.id for prop in matches if prop.id is not None)),
        )

    membership_required = focal_hypothesis is None and edge.id is not None
    if membership_required:
        blockers.append("membership-required")

    proposed_row, evidence_warnings = _proposed_workbench_row(
        dag=dag,
        edge=edge,
        focal_hypothesis=focal_hypothesis,
    )
    status: MigrationStatus = "blocked" if blockers else "ready"
    return RetiredEdgeMigrationRow(
        path=rel_path,
        dag=dag,
        edge_id=edge.id,
        source=source,
        target=target,
        status=status,
        blockers=tuple(blockers),
        notes=tuple(notes),
        predicate_review_required=True,
        membership_required=membership_required,
        evidence_warnings=tuple(evidence_warnings),
        proposed_row=proposed_row,
    )


def _proposed_workbench_row(
    *,
    dag: str,
    edge: EdgeRecord,
    focal_hypothesis: str | None,
) -> tuple[dict[str, Any], list[str]]:
    row: dict[str, Any] = {
        "subject": edge.source.strip(),
        "predicate": "affects",
        "object": edge.target.strip(),
        "patch": dag,
        "polarity": "positive",
        "claim_layer": _claim_layer(edge),
        "identification_strength": _identification_strength(edge.identification),
        "legacy_relation_label": edge.relation or edge.original_label,
        "legacy_patch": dag,
        "legacy_edge_id": edge.id,
    }
    if focal_hypothesis is not None:
        row["discusses"] = [focal_hypothesis]

    evidence, warnings = _evidence_stubs(edge)
    if evidence:
        row["evidence"] = evidence
    return _drop_none(row), warnings


def _claim_layer(edge: EdgeRecord) -> str:
    if edge.edge_status == EdgeStatus.structural or edge.identification == Identification.structural:
        return "structural_claim"
    return "causal_effect"


def _identification_strength(value: Identification) -> str:
    return value.value


def _evidence_stubs(edge: EdgeRecord) -> tuple[list[dict[str, str]], list[str]]:
    evidence: list[dict[str, str]] = []
    warnings: list[str] = []
    for entry in edge.data_support:
        source = _ref_source(entry)
        if source is None:
            warnings.append("unmapped-data-support")
            continue
        evidence.append({"source": source, "evidence_type": "empirical_data", "stance": "supports"})
    for entry in edge.lit_support:
        source = _ref_source(entry)
        if source is None:
            warnings.append("unmapped-lit-support")
            continue
        evidence.append({"source": source, "evidence_type": "literature", "stance": "supports"})
    return evidence, warnings


def _ref_source(entry: object) -> str | None:
    extra = getattr(entry, "__pydantic_extra__", None) or {}
    for key in ("task", "dataset", "accession", "paper", "doi", "proposition", "interpretation", "discussion"):
        value = extra.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}:{value.strip()}"
    return None


def _drop_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None and value != []}


def migration_plan_to_workbench_yaml(plan: RetiredEdgeMigrationPlan) -> str:
    ready_rows = [row.proposed_row for row in plan.rows if row.status == "ready" and row.proposed_row is not None]
    if not ready_rows:
        raise ValueError("no compile-compatible retired edge migration rows; pass --focal-hypothesis or inspect blockers")
    doc: dict[str, Any] = {"rows": ready_rows}
    if plan.focal_hypothesis is not None:
        doc["focal_hypothesis"] = plan.focal_hypothesis
    WorkbenchFile.model_validate(doc)
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def render_migration_plan_table(plan: RetiredEdgeMigrationPlan) -> str:
    payload = plan.to_json()
    lines = [
        "Retired edge migration plan: "
        f"{payload['summary']['ready']} ready, "
        f"{payload['summary']['blocked']} blocked, "
        f"{payload['summary']['skipped']} skipped."
    ]
    for row in payload["rows"]:
        blockers = ",".join(row["blockers"]) if row["blockers"] else "-"
        notes = ",".join(row["notes"]) if row["notes"] else "-"
        lines.append(
            f"  {row['dag']}#{row['edge_id']}: {row['source']} -> {row['target']} "
            f"{row['status']} blockers={blockers} notes={notes}"
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run the core tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_retired_edge_migration.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
rtk git add science/src/science_tool/dag/retired_edge_migration.py science/tests/dag/test_retired_edge_migration.py
rtk git commit -m "feat: plan retired DAG edge migrations"
```

Expected: commit succeeds.

---

### Task 2: CLI JSON And Table Surface

**Files:**
- Modify: `science/src/science_tool/dag/cli.py`
- Modify: `science/tests/dag/test_cli.py`

- [ ] **Step 1: Add failing CLI tests for JSON and table output**

Append these tests to `science/tests/dag/test_cli.py` after `test_cli_dag_retired_edges_table_reports_orphans`:

```python
def _write_retired_migration_project(project: Path) -> None:
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True, exist_ok=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
edges:
  - id: 1
    source: a
    target: b
    relation: biases
    edge_status: supported
    identification: observational
    description: Retired edge text.
    lit_support:
      - paper: Smith2020
        description: Literature support.
""".strip(),
        encoding="utf-8",
    )


def test_cli_dag_retired_edge_migration_plan_json_blocks_without_membership(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)

    result = CliRunner().invoke(
        main,
        ["dag", "retired-edge-migration-plan", "--project", str(project), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["summary"]["blocked"] == 1
    assert payload["summary"]["membership_required"] == 1
    assert payload["rows"][0]["blockers"] == ["membership-required"]
    assert payload["rows"][0]["predicate_review_required"] is True


def test_cli_dag_retired_edge_migration_plan_table_reports_blockers(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)

    result = CliRunner().invoke(
        main,
        ["dag", "retired-edge-migration-plan", "--project", str(project)],
    )

    assert result.exit_code == 0, result.output
    assert "Retired edge migration plan" in result.output
    assert "h1#1" in result.output
    assert "membership-required" in result.output
```

- [ ] **Step 2: Run the new CLI tests and verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/dag/test_cli.py::test_cli_dag_retired_edge_migration_plan_json_blocks_without_membership \
  science/tests/dag/test_cli.py::test_cli_dag_retired_edge_migration_plan_table_reports_blockers \
  -q
```

Expected: FAIL because `retired-edge-migration-plan` is not registered.

- [ ] **Step 3: Add the CLI command**

In `science/src/science_tool/dag/cli.py`, add this block immediately after `retired_edges_cmd` and before the `schema` section:

```python
@dag_group.command("retired-edge-migration-plan")
@click.option(
    "--dag",
    "slug",
    default=None,
    help="Plan migration for one retired DAG edge file. Defaults to every *.edges.yaml file.",
)
@click.option(
    "--focal-hypothesis",
    default=None,
    help="Hypothesis ref to use as file-level workbench membership for migrated rows.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "workbench"]),
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
def retired_edge_migration_plan_cmd(
    slug: str | None,
    focal_hypothesis: str | None,
    output_format: str,
    project_path: Path | None,
) -> None:
    """Plan read-only migration from retired *.edges.yaml rows to workbench rows."""
    from science_tool.dag.retired_edge_migration import (
        build_retired_edge_migration_plan,
        migration_plan_to_workbench_yaml,
        render_migration_plan_table,
    )

    project = (project_path or Path.cwd()).resolve()
    try:
        plan = build_retired_edge_migration_plan(project, dag=slug, focal_hypothesis=focal_hypothesis)
        if output_format == "json":
            click.echo(json.dumps(plan.to_json(), indent=2, sort_keys=True))
            return
        if output_format == "workbench":
            click.echo(migration_plan_to_workbench_yaml(plan), nl=False)
            return
        click.echo(render_migration_plan_table(plan), nl=False)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
```

- [ ] **Step 4: Run the CLI tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/dag/test_cli.py::test_cli_dag_retired_edge_migration_plan_json_blocks_without_membership \
  science/tests/dag/test_cli.py::test_cli_dag_retired_edge_migration_plan_table_reports_blockers \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
rtk git add science/src/science_tool/dag/cli.py science/tests/dag/test_cli.py
rtk git commit -m "feat: expose retired edge migration planner"
```

Expected: commit succeeds.

---

### Task 3: Workbench YAML Output

**Files:**
- Modify: `science/tests/dag/test_retired_edge_migration.py`
- Modify: `science/tests/dag/test_cli.py`
- Modify if needed: `science/src/science_tool/dag/retired_edge_migration.py`

- [ ] **Step 1: Add failing core workbench-output tests**

Append these imports near the top of `science/tests/dag/test_retired_edge_migration.py`:

```python
import yaml

from science_tool.dag.retired_edge_migration import migration_plan_to_workbench_yaml
from science_tool.dag.workbench import WorkbenchFile
```

If the file already imports `build_retired_edge_migration_plan` with a single-line import, replace it with:

```python
from science_tool.dag.retired_edge_migration import (
    build_retired_edge_migration_plan,
    migration_plan_to_workbench_yaml,
)
```

Append these tests:

```python
def test_workbench_yaml_requires_ready_rows(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    plan = build_retired_edge_migration_plan(project)

    with pytest.raises(ValueError, match="no compile-compatible"):
        migration_plan_to_workbench_yaml(plan)


def test_workbench_yaml_is_strict_workbench_file_with_focal_hypothesis(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    plan = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1")

    text = migration_plan_to_workbench_yaml(plan)
    payload = yaml.safe_load(text)
    parsed = WorkbenchFile.model_validate(payload)

    assert parsed.focal_hypothesis == "hypothesis:h1"
    assert len(parsed.rows) == 1
    row = parsed.rows[0]
    assert row.subject == "a"
    assert row.predicate == "affects"
    assert row.object == "b"
    assert row.patch == "h1"
    assert row.legacy_relation_label == "biases"
    assert row.legacy_patch == "h1"
    assert row.legacy_edge_id == 1
    assert row.discusses == ["hypothesis:h1"]
    assert "predicate_review_required" not in text
    assert "membership_required" not in text
```

- [ ] **Step 2: Run the core workbench tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/dag/test_retired_edge_migration.py::test_workbench_yaml_requires_ready_rows \
  science/tests/dag/test_retired_edge_migration.py::test_workbench_yaml_is_strict_workbench_file_with_focal_hypothesis \
  -q
```

Expected: PASS if Task 1 implemented `migration_plan_to_workbench_yaml` exactly. If this fails because the function is missing or emits forbidden keys, fix `science/src/science_tool/dag/retired_edge_migration.py` to match the Task 1 implementation block.

- [ ] **Step 3: Add failing CLI workbench-output tests**

Append these tests to `science/tests/dag/test_cli.py` after the migration-plan JSON/table tests:

```python
def test_cli_dag_retired_edge_migration_plan_workbench_requires_focal_hypothesis(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)

    result = CliRunner().invoke(
        main,
        ["dag", "retired-edge-migration-plan", "--project", str(project), "--format", "workbench"],
    )

    assert result.exit_code != 0
    assert "no compile-compatible" in result.output


def test_cli_dag_retired_edge_migration_plan_workbench_outputs_strict_yaml(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "retired-edge-migration-plan",
            "--project",
            str(project),
            "--focal-hypothesis",
            "hypothesis:h1",
            "--format",
            "workbench",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = yaml.safe_load(result.stdout)
    from science_tool.dag.workbench import WorkbenchFile

    parsed = WorkbenchFile.model_validate(payload)
    assert parsed.focal_hypothesis == "hypothesis:h1"
    assert len(parsed.rows) == 1
    assert parsed.rows[0].legacy_patch == "h1"
    assert parsed.rows[0].legacy_edge_id == 1
    assert "predicate_review_required" not in result.stdout
```

Also add `import yaml` near the top of `science/tests/dag/test_cli.py` if it is not already imported.

- [ ] **Step 4: Run CLI workbench tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/dag/test_cli.py::test_cli_dag_retired_edge_migration_plan_workbench_requires_focal_hypothesis \
  science/tests/dag/test_cli.py::test_cli_dag_retired_edge_migration_plan_workbench_outputs_strict_yaml \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
rtk git add science/src/science_tool/dag/retired_edge_migration.py science/tests/dag/test_retired_edge_migration.py science/tests/dag/test_cli.py
rtk git commit -m "feat: render retired edge migration workbench drafts"
```

Expected: commit succeeds.

---

### Task 4: Public Export, Integration Guard, And Documentation Touch-Up

**Files:**
- Modify: `science/src/science_tool/dag/__init__.py`
- Modify: `docs/user-guide/big-picture-synthesis.md`
- Test: `science/tests/dag/test_cli.py`

- [ ] **Step 1: Export the planner API minimally**

Open `science/src/science_tool/dag/__init__.py`. Add imports near the other DAG helper exports:

```python
from science_tool.dag.retired_edge_migration import (
    RetiredEdgeMigrationPlan,
    RetiredEdgeMigrationRow,
    build_retired_edge_migration_plan,
    migration_plan_to_workbench_yaml,
    render_migration_plan_table,
)
```

Add these names to the `__all__` tuple/list:

```python
    "RetiredEdgeMigrationPlan",
    "RetiredEdgeMigrationRow",
    "build_retired_edge_migration_plan",
    "migration_plan_to_workbench_yaml",
    "render_migration_plan_table",
```

- [ ] **Step 2: Run import smoke**

Run:

```bash
rtk uv run --frozen --project science python - <<'PY'
from science_tool.dag import build_retired_edge_migration_plan
print(build_retired_edge_migration_plan.__name__)
PY
```

Expected stdout contains:

```text
build_retired_edge_migration_plan
```

- [ ] **Step 3: Add CLI help assertion**

Append this test to `science/tests/dag/test_cli.py`:

```python
def test_cli_dag_help_lists_retired_edge_migration_plan() -> None:
    result = CliRunner().invoke(main, ["dag", "--help"])

    assert result.exit_code == 0
    assert "retired-edge-migration-plan" in result.output
```

- [ ] **Step 4: Run help test**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/dag/test_cli.py::test_cli_dag_help_lists_retired_edge_migration_plan -q
```

Expected: PASS.

- [ ] **Step 5: Add user-guide mention**

In `docs/user-guide/big-picture-synthesis.md`, find the DAG section that describes DOT topology and relational propositions. Add this paragraph after the text explaining retired `*.edges.yaml` inspection:

```markdown
For migration work, `science dag retired-edge-migration-plan` can read the
explicit retired-edge inspection surface and print a reviewable plan or draft
workbench YAML. It is read-only: it does not write workbenches, compile
propositions, or make retired `*.edges.yaml` authoritative again.
```

If that exact location is not present, add the paragraph immediately after the first paragraph in the file that mentions `science dag retired-edges`.

- [ ] **Step 6: Verify docs mention the command without presenting YAML as active**

Run:

```bash
rtk rg -n "retired-edge-migration-plan|edges.yaml.*authoritative|edges.yaml.*active" docs/user-guide/big-picture-synthesis.md
```

Expected: at least one `retired-edge-migration-plan` hit. Any `edges.yaml` hit must describe retired/migration behavior, not active authoring.

- [ ] **Step 7: Commit Task 4**

Run:

```bash
rtk git add science/src/science_tool/dag/__init__.py science/tests/dag/test_cli.py docs/user-guide/big-picture-synthesis.md
rtk git commit -m "docs: document retired edge migration planner"
```

Expected: commit succeeds.

---

### Task 5: Focused Verification And Real-Project Smoke

**Files:**
- Verify only unless failures require fixes.

- [ ] **Step 1: Run focused planner and CLI tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/dag/test_retired_edge_migration.py \
  science/tests/dag/test_retired_edges.py \
  science/tests/dag/test_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run ruff on changed Python files**

Run:

```bash
rtk uv run --frozen --project science ruff check \
  science/src/science_tool/dag/retired_edge_migration.py \
  science/src/science_tool/dag/cli.py \
  science/src/science_tool/dag/__init__.py \
  science/tests/dag/test_retired_edge_migration.py \
  science/tests/dag/test_cli.py
```

Expected: PASS with no lint errors.

- [ ] **Step 3: Run pyright on changed source files**

Run:

```bash
rtk uv run --frozen --project science pyright \
  science/src/science_tool/dag/retired_edge_migration.py \
  science/src/science_tool/dag/cli.py \
  science/src/science_tool/dag/__init__.py
```

Expected: PASS. If pyright flags `__pydantic_extra__` access in `_ref_source`, replace `_ref_source` with this version and rerun:

```python
def _ref_source(entry: object) -> str | None:
    extra = getattr(entry, "__pydantic_extra__", None)
    if not isinstance(extra, dict):
        return None
    for key in ("task", "dataset", "accession", "paper", "doi", "proposition", "interpretation", "discussion"):
        value = extra.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}:{value.strip()}"
    return None
```

- [ ] **Step 4: Smoke zero-content project**

Run:

```bash
rtk uv run --frozen --project science science dag retired-edge-migration-plan --project ~/d/science/meta --format json
```

Expected: command exits 0 and reports:

```json
"rows": 0
```

The absolute path in JSON may resolve to a real filesystem path; do not copy that resolved path into docs or code. Use `~/d/...` style for human-facing examples.

- [ ] **Step 5: Smoke protein-landscape blockers without focal hypothesis**

Run:

```bash
rtk uv run --frozen --project science science dag retired-edge-migration-plan --project ~/d/protein-landscape --format json
```

Expected: command exits 0. The summary should show six blocked rows and six `membership_required` rows if the live project state still matches the design sample:

```json
"blocked": 6
"membership_required": 6
```

If counts differ, inspect the JSON. Treat live-corpus counts as observational; code correctness is determined by fixture tests.

- [ ] **Step 6: Smoke protein-landscape workbench draft with reviewed focal hypothesis**

Run with a placeholder hypothesis ref that validates as a string-level workbench value:

```bash
rtk uv run --frozen --project science science dag retired-edge-migration-plan \
  --project ~/d/protein-landscape \
  --focal-hypothesis hypothesis:h01-multi-manifold-protein-universe \
  --format workbench
```

Expected: command exits 0 and stdout begins with a `focal_hypothesis:` key and a `rows:` list. It must not write files.

- [ ] **Step 7: Verify default DAG tests still pass**

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

Expected: PASS. This guards the Phase 5f boundary that default commands still ignore retired YAML.

- [ ] **Step 8: Run full science test suite if focused checks pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests -q
```

Expected: PASS with warnings only.

- [ ] **Step 9: Commit verification fixes if any were needed**

If Steps 1-8 required code/test/doc fixes, commit those exact files:

```bash
rtk git add science/src/science_tool/dag/retired_edge_migration.py \
  science/src/science_tool/dag/cli.py \
  science/src/science_tool/dag/__init__.py \
  science/tests/dag/test_retired_edge_migration.py \
  science/tests/dag/test_cli.py \
  docs/user-guide/big-picture-synthesis.md
rtk git commit -m "fix: verify retired edge migration planner"
```

Expected: commit succeeds. If there were no fixes, skip this step.

- [ ] **Step 10: Final status**

Run:

```bash
rtk git status --short
rtk git log --oneline -6
```

Expected: status is clean. Recent commits include the Phase 5g implementation commits.

---

## Self-Review Checklist

- Spec coverage:
  - Read-only planner: Tasks 1-3.
  - Flat command with `--focal-hypothesis`: Task 2.
  - Strict per-row schema validation through `EdgeRecord`: Task 1.
  - `membership-required` blocker by default: Task 1 and Task 3.
  - Conservative predicate with review metadata: Task 1.
  - Workbench YAML strictness and no review-only keys: Task 3.
  - No writes/compile/apply behavior: Tasks 2, 3, and smoke Step 6.
  - Default DAG command isolation: Task 5 Step 7.
- Placeholder scan:
  - No placeholder markers or undefined future work required for this plan.
  - Every code-touching step includes concrete code or an exact command.
- Type consistency:
  - Core type names: `RetiredEdgeMigrationPlan`, `RetiredEdgeMigrationRow`.
  - Core function names: `build_retired_edge_migration_plan`, `migration_plan_to_workbench_yaml`, `render_migration_plan_table`.
  - CLI command name: `retired-edge-migration-plan`.
