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


def test_plan_blocks_missing_edge_id(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
edges:
  - source: a
    target: b
    edge_status: supported
    identification: observational
    description: Row with no id.
""".strip(),
        encoding="utf-8",
    )

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["blocked"] == 1
    row = payload["rows"][0]
    assert row["status"] == "blocked"
    assert row["blockers"] == ["missing-edge-id"]
    assert row["edge_id"] is None
    assert row["proposed_row"] is None


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


def test_plan_fails_loud_when_identity_missing_and_other_schema_error(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
edges:
  - source: a
    target: b
    edge_status: supported
    identification: observational
    description: Row has a missing id and an invalid support ref.
    data_support:
      - description: Missing kind tag.
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid retired DAG edge file"):
        build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1")


def test_plan_fails_loud_on_duplicate_source_target_pairs(tmp_path: Path) -> None:
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
    description: First duplicate row.
  - id: 2
    source: a
    target: b
    edge_status: supported
    identification: observational
    description: Second duplicate row.
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate edge"):
        build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1")


def test_plan_fails_loud_when_edges_value_is_not_list(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
edges: ""
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="edges must be a list"):
        build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1")
