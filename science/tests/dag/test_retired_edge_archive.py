from __future__ import annotations

import hashlib
import json
from pathlib import Path

from science_tool.dag.retired_edge_archive import (
    ARCHIVE_SCHEMA_VERSION,
    build_retired_edge_archive_plan,
)


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


def _write_lineage_proposition(project: Path) -> None:
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


def _archive_path(project: Path, dag: str = "h1") -> Path:
    return project / "archive/dag-retired-edges" / f"{dag}.edges.yaml"


def _manifest_path(project: Path, dag: str = "h1") -> Path:
    return project / "archive/dag-retired-edges" / f"{dag}.edges.yaml.archive.json"


def test_archive_plan_ready_for_all_closed_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    plan = build_retired_edge_archive_plan(project, dag="h1")
    payload = plan.to_json()

    assert payload["status"] == "ready_to_archive"
    assert payload["applied"] is False
    assert payload["dag"] == "h1"
    assert payload["source"] == "doc/figures/dags/h1.edges.yaml"
    assert payload["archive"] == "archive/dag-retired-edges/h1.edges.yaml"
    assert payload["manifest"] == "archive/dag-retired-edges/h1.edges.yaml.archive.json"
    assert payload["closed_rows"] == 1
    assert payload["closed_by"] == ["proposition:a-affects-b"]
    assert payload["sha256"].startswith("sha256:")
    assert payload["blockers"] == []
    assert payload["row_status_counts"] == {"closed": 1}


def test_archive_plan_blocks_non_closed_rows(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "blocked"
    assert payload["closed_rows"] == 0
    assert payload["closed_by"] == []
    assert payload["row_status_counts"] == {"blocked": 1}
    assert payload["blockers"] == ["not-all-retired-edge-rows-closed"]


def test_archive_plan_blocks_empty_retired_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.edges.yaml").write_text("dag: h1\nedges: []\n", encoding="utf-8")

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["empty-retired-edge-file"]
    assert payload["row_status_counts"] == {}


def test_archive_plan_missing_source_without_archive_blocks(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    _dag_dir(project)

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["retired-edge-file-missing"]
    assert payload["source"] == "doc/figures/dags/h1.edges.yaml"
    assert payload["archive"] == "archive/dag-retired-edges/h1.edges.yaml"


def test_archive_plan_reports_already_archived(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    archived = _archive_path(project)
    archived.parent.mkdir(parents=True)
    archived.write_text("archived yaml\n", encoding="utf-8")
    archived_bytes = b"archived yaml\n"
    sha256 = f"sha256:{hashlib.sha256(archived_bytes).hexdigest()}"
    _manifest_path(project).write_text(
        json.dumps(
            {
                "schema_version": ARCHIVE_SCHEMA_VERSION,
                "dag": "h1",
                "original_path": "doc/figures/dags/h1.edges.yaml",
                "archived_path": "archive/dag-retired-edges/h1.edges.yaml",
                "closed_by": ["proposition:a-affects-b"],
                "closed_rows": 1,
                "sha256": sha256,
                "archived_at": "2026-07-05",
                "tool": "science dag archive-retired-edges",
                "reason": "all-retired-edges-closed",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "already_archived"
    assert payload["applied"] is False
    assert payload["closed_rows"] == 1
    assert payload["closed_by"] == ["proposition:a-affects-b"]
    assert payload["blockers"] == []


def test_archive_plan_reports_ambiguous_state_for_manifest_extra_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    archived = _archive_path(project)
    archived.parent.mkdir(parents=True)
    archived.write_text("archived yaml\n", encoding="utf-8")
    archived_bytes = b"archived yaml\n"
    sha256 = f"sha256:{hashlib.sha256(archived_bytes).hexdigest()}"
    _manifest_path(project).write_text(
        json.dumps(
            {
                "schema_version": ARCHIVE_SCHEMA_VERSION,
                "dag": "h1",
                "original_path": "doc/figures/dags/h1.edges.yaml",
                "archived_path": "archive/dag-retired-edges/h1.edges.yaml",
                "closed_by": ["proposition:a-affects-b"],
                "closed_rows": 1,
                "sha256": sha256,
                "archived_at": "2026-07-05",
                "tool": "science dag archive-retired-edges",
                "reason": "all-retired-edges-closed",
                "extra": "not allowed",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "ambiguous_state"
    assert payload["blockers"] == ["invalid-archive-manifest"]


def test_archive_plan_reports_ambiguous_state_for_manifest_sha_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    archived = _archive_path(project)
    archived.parent.mkdir(parents=True)
    archived.write_text("archived yaml\n", encoding="utf-8")
    _manifest_path(project).write_text(
        json.dumps(
            {
                "schema_version": ARCHIVE_SCHEMA_VERSION,
                "dag": "h1",
                "original_path": "doc/figures/dags/h1.edges.yaml",
                "archived_path": "archive/dag-retired-edges/h1.edges.yaml",
                "closed_by": ["proposition:a-affects-b"],
                "closed_rows": 1,
                "sha256": "sha256:example",
                "archived_at": "2026-07-05",
                "tool": "science dag archive-retired-edges",
                "reason": "all-retired-edges-closed",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "ambiguous_state"
    assert payload["blockers"] == ["invalid-archive-manifest"]


def test_archive_plan_reports_ambiguous_state_for_source_and_archive(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    archived = _archive_path(project)
    archived.parent.mkdir(parents=True)
    archived.write_text("archived yaml\n", encoding="utf-8")

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "ambiguous_state"
    assert payload["blockers"] == ["source-and-archive-both-exist"]


def test_archive_plan_reports_ambiguous_state_for_manifest_without_archive(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    _manifest_path(project).parent.mkdir(parents=True)
    _manifest_path(project).write_text("{}\n", encoding="utf-8")

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "ambiguous_state"
    assert payload["blockers"] == ["archive-manifest-mismatch"]


def test_archive_plan_reports_ambiguous_state_for_non_object_manifest(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    archived = _archive_path(project)
    archived.parent.mkdir(parents=True)
    archived.write_text("archived yaml\n", encoding="utf-8")
    _manifest_path(project).write_text("[]\n", encoding="utf-8")

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "ambiguous_state"
    assert payload["blockers"] == ["invalid-archive-manifest"]


def test_archive_plan_reports_ambiguous_state_for_wrong_manifest_tool(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    archived = _archive_path(project)
    archived.parent.mkdir(parents=True)
    archived.write_text("archived yaml\n", encoding="utf-8")
    _manifest_path(project).write_text(
        json.dumps(
            {
                "schema_version": ARCHIVE_SCHEMA_VERSION,
                "dag": "h1",
                "original_path": "doc/figures/dags/h1.edges.yaml",
                "archived_path": "archive/dag-retired-edges/h1.edges.yaml",
                "closed_by": ["proposition:a-affects-b"],
                "closed_rows": 1,
                "sha256": "sha256:example",
                "archived_at": "2026-07-05",
                "tool": "wrong tool",
                "reason": "all-retired-edges-closed",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "ambiguous_state"
    assert payload["blockers"] == ["invalid-archive-manifest"]


def test_archive_plan_reports_ambiguous_state_for_wrong_manifest_reason(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    archived = _archive_path(project)
    archived.parent.mkdir(parents=True)
    archived.write_text("archived yaml\n", encoding="utf-8")
    _manifest_path(project).write_text(
        json.dumps(
            {
                "schema_version": ARCHIVE_SCHEMA_VERSION,
                "dag": "h1",
                "original_path": "doc/figures/dags/h1.edges.yaml",
                "archived_path": "archive/dag-retired-edges/h1.edges.yaml",
                "closed_by": ["proposition:a-affects-b"],
                "closed_rows": 1,
                "sha256": "sha256:example",
                "archived_at": "2026-07-05",
                "tool": "science dag archive-retired-edges",
                "reason": "wrong reason",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "ambiguous_state"
    assert payload["blockers"] == ["invalid-archive-manifest"]
