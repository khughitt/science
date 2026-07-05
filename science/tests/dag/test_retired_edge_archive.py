from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

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
kind: proposition
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


def test_archive_plan_rejects_path_separator_dag_slug(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    _dag_dir(project)

    with pytest.raises(ValueError, match="DAG slug must be a single path segment"):
        build_retired_edge_archive_plan(project, dag="nested/h1")


def test_archive_plan_rejects_parent_path_dag_slug(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    _dag_dir(project)

    with pytest.raises(ValueError, match="DAG slug must be a single path segment"):
        build_retired_edge_archive_plan(project, dag="../h1")


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


def test_apply_retired_edge_archive_moves_file_and_writes_manifest(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    source = project / "doc/figures/dags/h1.edges.yaml"
    before = source.read_text(encoding="utf-8")

    result = apply_retired_edge_archive(project, dag="h1", now="2026-07-05")
    payload = result.to_json()

    assert payload["status"] == "already_archived"
    assert payload["applied"] is True
    assert not source.exists()
    archived = _archive_path(project)
    manifest = _manifest_path(project)
    assert archived.read_text(encoding="utf-8") == before
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload == {
        "archived_at": "2026-07-05",
        "archived_path": "archive/dag-retired-edges/h1.edges.yaml",
        "closed_by": ["proposition:a-affects-b"],
        "closed_rows": 1,
        "dag": "h1",
        "original_path": "doc/figures/dags/h1.edges.yaml",
        "reason": "all-retired-edges-closed",
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "sha256": payload["sha256"],
        "tool": "science dag archive-retired-edges",
    }


def test_apply_retired_edge_archive_rerun_reports_already_archived(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    first = apply_retired_edge_archive(project, dag="h1", now="2026-07-05").to_json()
    second = apply_retired_edge_archive(project, dag="h1", now="2026-07-06").to_json()

    assert first["status"] == "already_archived"
    assert first["applied"] is True
    assert second["status"] == "already_archived"
    assert second["applied"] is False
    assert second["closed_by"] == ["proposition:a-affects-b"]


def test_apply_retired_edge_archive_refuses_blocked_plan(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)

    with pytest.raises(ValueError, match="not ready to archive"):
        apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    assert (project / "doc/figures/dags/h1.edges.yaml").exists()
    assert not _archive_path(project).exists()
    assert not _manifest_path(project).exists()


def test_apply_retired_edge_archive_refuses_destination_collision(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    _archive_path(project).parent.mkdir(parents=True)
    _archive_path(project).write_text("collision\n", encoding="utf-8")

    with pytest.raises(ValueError, match="ambiguous_state"):
        apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    assert (project / "doc/figures/dags/h1.edges.yaml").exists()
    assert _archive_path(project).read_text(encoding="utf-8") == "collision\n"


def test_apply_retired_edge_archive_refuses_archive_race_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import science_tool.dag.retired_edge_archive as module
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    source = project / "doc/figures/dags/h1.edges.yaml"
    before = source.read_text(encoding="utf-8")
    original_move = module._move_without_overwrite

    def racing_move(src: Path, dst: Path) -> None:
        dst.write_text("collision\n", encoding="utf-8")
        original_move(src, dst)

    monkeypatch.setattr(module, "_move_without_overwrite", racing_move)

    with pytest.raises(FileExistsError):
        apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    assert source.read_text(encoding="utf-8") == before
    assert _archive_path(project).read_text(encoding="utf-8") == "collision\n"
    assert not _manifest_path(project).exists()


def test_apply_retired_edge_archive_refuses_manifest_race_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import science_tool.dag.retired_edge_archive as module
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    source = project / "doc/figures/dags/h1.edges.yaml"
    before = source.read_text(encoding="utf-8")
    original_write_text = module._write_text_without_overwrite

    def racing_write_text(path: Path, text: str) -> None:
        path.write_text("collision\n", encoding="utf-8")
        original_write_text(path, text)

    monkeypatch.setattr(module, "_write_text_without_overwrite", racing_write_text)

    with pytest.raises(FileExistsError):
        apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    assert source.read_text(encoding="utf-8") == before
    assert not _archive_path(project).exists()
    assert _manifest_path(project).read_text(encoding="utf-8") == "collision\n"


def test_apply_retired_edge_archive_rolls_back_when_manifest_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import science_tool.dag.retired_edge_archive as module
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    source = project / "doc/figures/dags/h1.edges.yaml"
    before = source.read_text(encoding="utf-8")

    def fail_manifest(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(module, "_write_manifest_file", fail_manifest)

    with pytest.raises(OSError, match="disk full"):
        apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    assert source.read_text(encoding="utf-8") == before
    assert not _archive_path(project).exists()
    assert not _manifest_path(project).exists()


def test_apply_retired_edge_archive_cleans_partial_manifest_on_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import science_tool.dag.retired_edge_archive as module
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    source = project / "doc/figures/dags/h1.edges.yaml"
    before = source.read_text(encoding="utf-8")

    def partial_manifest(path: Path, **_kwargs: object) -> None:
        path.write_text("partial manifest\n", encoding="utf-8")
        raise OSError("fsync failed")

    monkeypatch.setattr(module, "_write_manifest_file", partial_manifest)

    with pytest.raises(OSError, match="fsync failed"):
        apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    assert source.read_text(encoding="utf-8") == before
    assert not _archive_path(project).exists()
    assert not _manifest_path(project).exists()
    assert build_retired_edge_archive_plan(project, dag="h1").to_json()["status"] == "ready_to_archive"


def test_archived_retired_edge_file_is_not_active_migration_debt(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive
    from science_tool.dag.retired_edge_migration import build_retired_edge_migration_plan
    from science_tool.dag.retired_edges import build_retired_edges_report

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    apply_retired_edge_archive(project, dag="h1", now="2026-07-05")
    assert _archive_path(project).exists()

    retired_report = build_retired_edges_report(project, dag="h1").to_json()
    assert retired_report["summary"]["files"] == 0
    assert retired_report["files"] == []
    with pytest.raises(ValueError, match="retired DAG edge file does not exist"):
        build_retired_edge_migration_plan(project, dag="h1")


def test_archived_retired_edge_file_does_not_break_dag_validation(tmp_path: Path) -> None:
    from science_tool.dag.paths import load_dag_paths
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive
    from science_tool.dag.validate import validate_project

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    apply_retired_edge_archive(project, dag="h1", now="2026-07-05")
    _archive_path(project).write_text("not: [valid\n", encoding="utf-8")

    report = validate_project(load_dag_paths(project))
    assert report.ok
