from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.dag.retired_edge_migration import build_retired_edge_migration_plan, migration_plan_to_workbench_yaml
from science_tool.dag.workbench import WorkbenchFile


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


def _write_lineage_proposition(
    project: Path,
    *,
    slug: str = "a-affects-b",
    subject: str = "a",
    object_: str = "b",
    legacy_patch: str = "h1",
    legacy_edge_id: int = 1,
    status: str = "active",
) -> None:
    prop_dir = project / "entities/propositions"
    prop_dir.mkdir(parents=True, exist_ok=True)
    (prop_dir / f"{slug}.md").write_text(
        f"""---
id: proposition:{slug}
kind: proposition
title: {subject} affects {object_}
status: {status}
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
        "closed": 0,
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
    assert row["description"] == "A retired claim that should become a reviewed migration row."
    assert row["raw_support"] == [
        {
            "section": "data_support",
            "source": "task:t001",
            "description": "Completed task support.",
        },
        {
            "section": "lit_support",
            "source": "paper:Smith2020",
            "description": "Literature support.",
        },
    ]
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

    payload = yaml.safe_load(migration_plan_to_workbench_yaml(plan))
    workbench = WorkbenchFile.model_validate(payload)

    assert workbench.focal_hypothesis == "hypothesis:h1"
    assert len(workbench.rows) == 1
    row = workbench.rows[0]
    assert row.subject == "a"
    assert row.predicate == "affects"
    assert row.object == "b"
    assert row.patch == "h1"
    assert row.legacy_relation_label == "biases"
    assert row.legacy_patch == "h1"
    assert row.legacy_edge_id == 1
    assert row.discusses == ["hypothesis:h1"]
    assert payload["rows"][0]["subject"] == "a"
    assert payload["rows"][0]["predicate"] == "affects"
    assert payload["rows"][0]["object"] == "b"
    assert not {
        "status",
        "blockers",
        "notes",
        "predicate_review_required",
        "membership_required",
        "evidence_warnings",
        "matching_propositions",
        "description",
        "raw_support",
        "proposed_row",
    } & set(payload["rows"][0])


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
    assert result.total_row_count == 1
    assert result.closed_row_count == 0
    assert result.closed_by == ()
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
    assert result.total_row_count == 1
    assert result.closed_row_count == 0
    assert result.closed_by == ()
    assert result.output_path == "doc/figures/dags/h1.workbench.yaml"
    assert (project / "doc/figures/dags/h1.workbench.yaml").exists()


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


def test_scaffold_retired_edge_workbench_all_closed_rejects_escaping_output(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    with pytest.raises(ValueError, match="escapes project root"):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=tmp_path / "outside.workbench.yaml",
        )


@pytest.mark.parametrize(
    ("output_path", "message"),
    [
        (Path("doc/figures/dags/h1.edges.yaml"), r"\.edges\.yaml"),
        (Path("doc/figures/dags/h1.dot"), "DOT file"),
    ],
)
def test_scaffold_retired_edge_workbench_all_closed_rejects_retired_or_dot_outputs(
    tmp_path: Path, output_path: Path, message: str
) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    with pytest.raises(ValueError, match=message):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=output_path,
        )


def test_render_retired_edge_workbench_scaffold_table_complete_uses_explicit_row_counts(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import (
        render_retired_edge_workbench_scaffold_table,
        scaffold_retired_edge_workbench,
    )

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    result = scaffold_retired_edge_workbench(
        project,
        dag="h1",
        focal_hypothesis="hypothesis:h1",
        output_path=Path("missing-parent/h1.workbench.yaml"),
    )

    assert render_retired_edge_workbench_scaffold_table(result) == (
        "Retired edge workbench scaffold complete: h1\n"
        "  status: complete\n"
        "  focal_hypothesis: hypothesis:h1\n"
        "  written_rows: 0\n"
        "  total_rows: 1\n"
        "  closed_rows: 1\n"
    )


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
    assert first.total_row_count == 1
    assert first.closed_row_count == 0
    assert first.closed_by == ()
    assert second.status == "no-op"
    assert second.written is False
    assert second.total_row_count == 1
    assert second.closed_row_count == 0
    assert second.closed_by == ()
    assert second.byte_count == first.byte_count


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


def test_scaffold_retired_edge_workbench_missing_retired_file_fails_before_write(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_manifest(project)
    _dag_dir(project)

    with pytest.raises(ValueError, match="retired DAG edge file does not exist"):
        scaffold_retired_edge_workbench(
            project,
            dag="missing",
            focal_hypothesis="hypothesis:h1",
            output_path=Path("doc/figures/dags/missing.workbench.yaml"),
        )

    assert not (project / "doc/figures/dags/missing.workbench.yaml").exists()


def test_scaffold_retired_edge_workbench_empty_retired_file_fails_before_write(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_migration import scaffold_retired_edge_workbench

    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
edges: []
""".strip(),
        encoding="utf-8",
    )
    output = project / "doc/figures/dags/h1.workbench.yaml"

    with pytest.raises(ValueError, match="contains no migration rows"):
        scaffold_retired_edge_workbench(
            project,
            dag="h1",
            focal_hypothesis="hypothesis:h1",
            output_path=output,
        )

    assert not output.exists()


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
kind: proposition
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


def test_scaffold_retired_edge_workbench_no_claim_support_skip_fails_before_write(tmp_path: Path) -> None:
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
""".strip(),
        encoding="utf-8",
    )
    output = project / "doc/figures/dags/h1.workbench.yaml"

    with pytest.raises(ValueError, match="no-claim-support-content"):
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


def test_plan_skips_matching_compiled_proposition(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    prop_dir = project / "entities/propositions"
    prop_dir.mkdir(parents=True)
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


def test_plan_closure_wins_eliminated_edge_blocker(tmp_path: Path) -> None:
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
    _write_lineage_proposition(project)

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["closed"] == 1
    assert payload["summary"]["blocked"] == 0
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
kind: proposition
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


def test_plan_ignores_superseded_legacy_lineage_claim(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project, status="superseded")

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["closed"] == 0
    assert payload["summary"]["ready"] == 1
    row = payload["rows"][0]
    assert row["status"] == "ready"
    assert row["closed_by"] == []


def test_plan_active_lineage_still_closes_when_superseded_duplicate_exists(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project, slug="a-affects-b")
    _write_lineage_proposition(project, slug="a-affects-b-old", status="superseded")

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["closed"] == 1
    assert payload["summary"]["blocked"] == 0
    row = payload["rows"][0]
    assert row["status"] == "closed"
    assert row["closed_by"] == ["proposition:a-affects-b"]
    assert row["closure_conflicts"] == []


def test_plan_superseded_mismatched_lineage_does_not_block(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project, subject="a", object_="c", status="superseded")

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["blocked"] == 0
    assert payload["summary"]["closed"] == 0
    assert payload["summary"]["ready"] == 1
    row = payload["rows"][0]
    assert row["status"] == "ready"
    assert row["closure_conflicts"] == []


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


def test_plan_blocks_invalid_identification_as_row_diagnostic(tmp_path: Path) -> None:
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
    identification: not-real
    description: Invalid identification should be a row-level blocker.
""".strip(),
        encoding="utf-8",
    )

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["blocked"] == 1
    row = payload["rows"][0]
    assert row["status"] == "blocked"
    assert row["blockers"] == ["invalid-identification"]
    assert row["edge_id"] == 1
    assert row["source"] == "a"
    assert row["target"] == "b"
    assert row["proposed_row"] is None


def test_plan_notes_missing_identification_default(tmp_path: Path) -> None:
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
    description: Missing identification should default visibly.
""".strip(),
        encoding="utf-8",
    )

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["ready"] == 1
    row = payload["rows"][0]
    assert row["status"] == "ready"
    assert row["notes"] == ["missing-identification-defaulted-to-none"]
    assert row["proposed_row"]["identification_strength"] == "none"


def test_plan_skips_rows_with_no_claim_or_support_content(tmp_path: Path) -> None:
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
    description: ""
""".strip(),
        encoding="utf-8",
    )

    payload = build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1").to_json()

    assert payload["summary"]["skipped"] == 1
    assert payload["summary"]["ready"] == 0
    row = payload["rows"][0]
    assert row["status"] == "skipped"
    assert row["notes"] == ["no-claim-support-content"]
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


def test_plan_fails_loud_on_duplicate_pair_with_invalid_identification(tmp_path: Path) -> None:
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
    identification: not-real
    description: First row has invalid identification.
  - id: 2
    source: a
    target: b
    edge_status: supported
    identification: observational
    description: Second row duplicates the same pair.
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


def test_plan_wraps_malformed_retired_yaml(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.edges.yaml").write_text("not: [valid\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid retired DAG edge file"):
        build_retired_edge_migration_plan(project, focal_hypothesis="hypothesis:h1")
