from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.dag.validate import _parse_dot_topology

FIXTURE_ROOT = Path(__file__).parent / "fixtures/mm30"
FIXTURE_MINIMAL = Path(__file__).parent / "fixtures/minimal"
SLUGS = ("h1-prognosis", "h1-progression", "h2-subtype-architecture", "h1-h2-bridge")


def _write_proposition(project: Path, slug: str, source: str, target: str) -> None:
    prop_dir = project / "entities/propositions"
    prop_dir.mkdir(parents=True, exist_ok=True)
    (prop_dir / f"{slug}.md").write_text(
        f"""---
id: proposition:{slug}
type: proposition
title: {source} affects {target}
status: active
subject: {source}
predicate: affects
object: {target}
polarity: positive
claim_layer: causal_effect
identification_strength: observational
legacy_relation_label: affects
---

{source} affects {target}.
""",
        encoding="utf-8",
    )


def _write_malformed_proposition(project: Path) -> None:
    prop_dir = project / "entities/propositions"
    prop_dir.mkdir(parents=True, exist_ok=True)
    (prop_dir / "malformed.md").write_text(
        """---
id: proposition:malformed
type: proposition
title: Malformed
status: active
subject: a
predicate: affects
object: b
polarity: not_a_real_polarity
---

Malformed proposition entity.
""",
        encoding="utf-8",
    )


def _write_propositions_for_dot(project: Path, dot_path: Path, slug_prefix: str) -> None:
    _, dot_edges = _parse_dot_topology(dot_path)
    for index, (source, target) in enumerate(sorted(dot_edges), start=1):
        _write_proposition(project, f"{slug_prefix}-{index}", source, target)


def _assert_no_retired_edge_yaml(project: Path) -> None:
    assert not list(project.glob("doc/figures/dags/*.edges.yaml"))


def _remove_retired_edge_yaml(project: Path) -> None:
    for edge_yaml in project.glob("doc/figures/dags/*.edges.yaml"):
        edge_yaml.unlink()


def _copy_minimal_fixture_with_propositions(source: Path, target: Path) -> Path:
    shutil.copytree(source, target)
    _remove_retired_edge_yaml(target)
    for dot_path in sorted((target / "doc/figures/dags").glob("*.dot")):
        _write_propositions_for_dot(target, dot_path, dot_path.stem)
    return target


def _build_project_without_propositions(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (project / "tasks").mkdir()
    return project


@pytest.fixture
def cli_project(tmp_path: Path) -> Path:
    """Copy the mm30 fixture to tmp for CLI tests.

    Derived artifacts (-auto.dot, -auto.png, -numbered.dot, .dot.reference)
    are stripped so tests can assert on which files a given command produces.
    """
    project = tmp_path / "project"
    project.mkdir()
    shutil.copytree(FIXTURE_ROOT / "doc", project / "doc")
    shutil.copytree(FIXTURE_ROOT / "tasks", project / "tasks")
    shutil.copy2(FIXTURE_ROOT / "science.yaml", project / "science.yaml")

    # Remove pre-rendered derived files so render/number tests start from scratch.
    dags_dir = project / "doc/figures/dags"
    for pattern in ("*-auto.dot", "*-auto.png", "*-numbered.dot", "*.dot.reference"):
        for f in dags_dir.glob(pattern):
            f.unlink()

    for slug in SLUGS:
        _write_propositions_for_dot(project, dags_dir / f"{slug}.dot", slug)

    return project


@pytest.fixture
def cli_audit_project(cli_project: Path) -> Path:
    _remove_retired_edge_yaml(cli_project)
    _assert_no_retired_edge_yaml(cli_project)
    return cli_project


def test_cli_dag_render_writes_auto_artifacts(cli_project: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["dag", "render", "--project", str(cli_project)])
    assert result.exit_code == 0, result.output
    for slug in SLUGS:
        assert (cli_project / f"doc/figures/dags/{slug}-auto.dot").exists()


def test_cli_dag_render_single_slug(cli_project: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["dag", "render", "--dag", "h1-progression", "--project", str(cli_project)])
    assert result.exit_code == 0
    assert (cli_project / "doc/figures/dags/h1-progression-auto.dot").exists()
    # Other DAGs should NOT be rendered:
    assert not (cli_project / "doc/figures/dags/h1-prognosis-auto.dot").exists()


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


def test_cli_dag_staleness_is_retired(cli_project: Path) -> None:
    result = CliRunner().invoke(main, ["dag", "staleness", "--project", str(cli_project)])

    assert result.exit_code != 0
    assert "retired" in result.output.lower()
    assert "retired-edges" in result.output


def test_dag_validate_accepts_format_json(cli_project: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["dag", "validate", "--project", str(cli_project), "--format", "json"])

    assert result.exit_code in {0, 1}, result.output
    payload = json.loads(result.stdout)
    assert "findings" in payload


def test_dag_audit_accepts_format_json(cli_audit_project: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["dag", "audit", "--project", str(cli_audit_project), "--format", "json"])

    assert result.exit_code in {0, 1}, result.output
    payload = json.loads(result.stdout)
    assert "validation" in payload
    assert "staleness" not in payload


def test_cli_dag_audit_table_prints_ok_on_clean_project(cli_audit_project: Path) -> None:
    result = CliRunner().invoke(main, ["dag", "audit", "--project", str(cli_audit_project)])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "DAG audit OK."
    assert "staleness" not in result.output.lower()


def test_cli_dag_audit_table_prints_validation_findings(tmp_path: Path) -> None:
    project = _copy_minimal_fixture_with_propositions(FIXTURE_MINIMAL / "cyclic", tmp_path / "cyclic")

    result = CliRunner().invoke(main, ["dag", "audit", "--project", str(project)])

    assert result.exit_code == 1
    assert "acyclicity" in result.output
    assert "cycle detected" in result.output
    assert "staleness" not in result.output.lower()


def test_cli_dag_audit_json_reports_missing_proposition_without_render_traceback(tmp_path: Path) -> None:
    project = _build_project_without_propositions(tmp_path)

    result = CliRunner().invoke(main, ["dag", "audit", "--format", "json", "--project", str(project)])

    assert result.exit_code == 1
    assert result.exception is not None
    assert result.exception.__class__.__name__ == "SystemExit"
    assert "no compiled proposition edge" not in result.output.lower()
    payload = json.loads(result.output)
    findings = payload["validation"]["findings"]
    assert [finding["rule"] for finding in findings] == ["proposition_edge_missing"]


def test_cli_dag_audit_table_reports_missing_proposition_without_render_traceback(tmp_path: Path) -> None:
    project = _build_project_without_propositions(tmp_path)

    result = CliRunner().invoke(main, ["dag", "audit", "--project", str(project)])

    assert result.exit_code == 1
    assert result.exception is not None
    assert result.exception.__class__.__name__ == "SystemExit"
    assert "ERROR: [proposition_edge_missing]" in result.output
    assert "a -> b" in result.output
    assert "no compiled proposition edge" not in result.output.lower()


def test_cli_dag_audit_fix_validation_failure_is_click_error(tmp_path: Path) -> None:
    project = _copy_minimal_fixture_with_propositions(FIXTURE_MINIMAL / "cyclic", tmp_path / "cyclic")

    result = CliRunner().invoke(main, ["dag", "audit", "--fix", "--project", str(project)])

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "dag audit --fix refused" in result.output
    assert result.exception is not None
    assert result.exception.__class__.__name__ != "RuntimeError"


def test_cli_dag_audit_is_read_only_by_default(cli_audit_project: Path) -> None:
    """dag audit without --fix must not mutate tasks/active.md or retired edge YAML."""
    active_before = (cli_audit_project / "tasks/active.md").read_text()
    runner = CliRunner()
    result = runner.invoke(main, ["dag", "audit", "--project", str(cli_audit_project), "--format", "json"])
    assert result.exit_code in (0, 1)
    payload = json.loads(result.stdout)
    assert "staleness" not in payload
    assert (cli_audit_project / "tasks/active.md").read_text() == active_before


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
    assert "workbench" in result.output.lower()
    assert "proposition" in result.output.lower()


def test_cli_dag_init_refuses_to_overwrite_existing(cli_project: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "dag",
            "init",
            "h1-prognosis",  # already exists
            "--project",
            str(cli_project),
        ],
    )
    assert result.exit_code != 0
    assert "exists" in result.output.lower() or "already" in result.output.lower()


def test_cli_dag_number_is_idempotent(cli_project: Path) -> None:
    _remove_retired_edge_yaml(cli_project)
    runner = CliRunner()
    r1 = runner.invoke(main, ["dag", "number", "--project", str(cli_project)])
    assert r1.exit_code == 0, r1.output
    first = (cli_project / "doc/figures/dags/h1-progression-numbered.dot").read_text()
    _assert_no_retired_edge_yaml(cli_project)

    r2 = runner.invoke(main, ["dag", "number", "--project", str(cli_project)])
    assert r2.exit_code == 0
    second = (cli_project / "doc/figures/dags/h1-progression-numbered.dot").read_text()

    assert first == second
    _assert_no_retired_edge_yaml(cli_project)


def test_cli_dag_number_does_not_load_propositions(cli_project: Path) -> None:
    _remove_retired_edge_yaml(cli_project)
    _write_malformed_proposition(cli_project)

    result = CliRunner().invoke(
        main,
        ["dag", "number", "--dag", "h1-progression", "--project", str(cli_project)],
    )

    assert result.exit_code == 0, result.output
    assert (cli_project / "doc/figures/dags/h1-progression-numbered.dot").exists()


def test_cli_dag_number_force_stubs_is_retired(cli_project: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["dag", "number", "--force-stubs", "--project", str(cli_project)],
    )

    assert result.exit_code != 0
    assert "retired" in result.output.lower()


def test_cli_dag_number_force_stubs_is_retired_before_loading_propositions(cli_project: Path) -> None:
    _write_malformed_proposition(cli_project)

    result = CliRunner().invoke(
        main,
        ["dag", "number", "--force-stubs", "--project", str(cli_project)],
    )

    assert result.exit_code != 0
    assert "retired" in result.output.lower()
    assert "not_a_real_polarity" not in result.output


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


def test_cli_dag_retired_edge_migration_plan_missing_project_is_click_error(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["dag", "retired-edge-migration-plan", "--project", str(tmp_path / "missing")],
    )

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert result.exception is not None
    assert result.exception.__class__.__name__ != "FileNotFoundError"


def test_cli_dag_retired_edge_migration_plan_malformed_yaml_is_click_error(tmp_path: Path) -> None:
    project = tmp_path / "project"
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text("not: [valid\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["dag", "retired-edge-migration-plan", "--project", str(project), "--format", "json"],
    )

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "invalid retired DAG edge file" in result.output
    assert result.exception is not None
    assert "ParserError" not in result.exception.__class__.__name__


def test_cli_dag_retired_edge_migration_plan_workbench_requires_focal_hypothesis(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)

    result = CliRunner().invoke(
        main,
        ["dag", "retired-edge-migration-plan", "--project", str(project), "--format", "workbench"],
    )

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "no compile-compatible" in result.output


def test_cli_dag_retired_edge_migration_plan_workbench_outputs_strict_yaml(tmp_path: Path) -> None:
    from science_tool.dag.workbench import WorkbenchFile

    project = tmp_path / "project"
    _write_retired_migration_project(project)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "retired-edge-migration-plan",
            "--project",
            str(project),
            "--format",
            "workbench",
            "--focal-hypothesis",
            "hypothesis:h1",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = yaml.safe_load(result.stdout)
    workbench = WorkbenchFile.model_validate(payload)
    assert workbench.focal_hypothesis == "hypothesis:h1"
    assert len(workbench.rows) == 1
    row = workbench.rows[0]
    assert row.legacy_patch == "h1"
    assert row.legacy_edge_id == 1
    assert row.discusses == ["hypothesis:h1"]
    assert not {
        "status",
        "blockers",
        "notes",
        "predicate_review_required",
        "membership_required",
        "evidence_warnings",
        "matching_propositions",
        "proposed_row",
    } & set(payload["rows"][0])


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


def test_cli_dag_scaffold_retired_edge_workbench_missing_dag_is_click_error(tmp_path: Path) -> None:
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
            "missing",
            "--focal-hypothesis",
            "hypothesis:h1",
            "--output",
            "doc/figures/dags/missing.workbench.yaml",
        ],
    )

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "retired DAG edge file does not exist" in result.output
    assert result.exception is not None
    assert result.exception.__class__.__name__ != "FileNotFoundError"
    assert not (project / "doc/figures/dags/missing.workbench.yaml").exists()


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


def _write_apply_workbench(project: Path, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """rows:
  - id: proposition:a-affects-b
    subject: a
    predicate: affects
    object: b
    patch: h1
    polarity: positive
    claim_layer: causal_effect
    identification_strength: observational
    evidence:
      - stance: supports
        source: paper:Smith2026
        evidence_type: literature
""",
        encoding="utf-8",
    )
    (project / "science.yaml").write_text(
        "name: dag-cli-apply-test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def test_cli_dag_apply_workbench_writes_entities_and_canonicalizes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    workbench = project / "doc/figures/dags/h1.workbench.yaml"
    _write_apply_workbench(project, workbench)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "apply-workbench",
            "--project",
            str(project),
            "--input",
            "doc/figures/dags/h1.workbench.yaml",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "applied"
    assert payload["rows"] == 1
    assert payload["propositions"] == 1
    assert payload["evidence_lines"] == 1
    assert (project / "entities/propositions/a-affects-b.md").is_file()
    assert (project / "entities/evidence-lines/a-affects-b-ev0.md").is_file()
    assert "evidence-line:a-affects-b-ev0" in workbench.read_text(encoding="utf-8")

    check = CliRunner().invoke(main, ["dag", "workbench", "--check", str(workbench)])
    assert check.exit_code == 0, check.output


def test_cli_dag_apply_workbench_json_reports_noop(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    workbench = project / "doc/figures/dags/h1.workbench.yaml"
    _write_apply_workbench(project, workbench)

    first = CliRunner().invoke(
        main,
        ["dag", "apply-workbench", "--project", str(project), "--input", str(workbench), "--format", "json"],
    )
    assert first.exit_code == 0, first.output
    second = CliRunner().invoke(
        main,
        ["dag", "apply-workbench", "--project", str(project), "--input", str(workbench), "--format", "json"],
    )
    assert second.exit_code == 0, second.output
    payload = json.loads(second.output)
    assert payload["status"] == "no-op"
    assert payload["changed_path_count"] == 0


def test_cli_dag_apply_workbench_refuses_retired_edges_input(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    path = project / "doc/figures/dags/h1.edges.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("dag: h1\nedges: []\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["dag", "apply-workbench", "--project", str(project), "--input", str(path)])

    assert result.exit_code != 0
    assert "retired edges YAML" in result.output


def test_cli_dag_apply_workbench_refuses_dot_input(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    path = project / "doc/figures/dags/h1.dot"
    path.parent.mkdir(parents=True)
    path.write_text("digraph h1 { a -> b; }\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["dag", "apply-workbench", "--project", str(project), "--input", str(path)])

    assert result.exit_code != 0
    assert "DOT topology" in result.output


def test_cli_dag_apply_workbench_invalid_workbench_is_click_error(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    path = project / "doc/figures/dags/h1.workbench.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("rows:\n  - subject: a\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["dag", "apply-workbench", "--project", str(project), "--input", str(path)])

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "failed to compile workbench" in result.output
    assert result.exception is not None
    assert result.exception.__class__.__name__ != "ValidationError"


def test_cli_dag_help_lists_retired_edge_migration_plan() -> None:
    result = CliRunner().invoke(main, ["dag", "--help"])

    assert result.exit_code == 0
    assert "retired-edge-migration-plan" in result.output


def test_cli_dag_schema_says_schema_is_retired(cli_project: Path) -> None:
    # Banner goes to STDERR so stdout stays pure JSON.
    result = CliRunner().invoke(main, ["dag", "schema"])

    assert result.exit_code == 0
    assert "RETIRED" in result.stderr
    assert "edges.yaml" in result.stderr
    json.loads(result.stdout)
