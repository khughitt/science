"""Unit tests for science_tool.dag.validate."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.dag.paths import DagPaths, load_dag_paths
from science_tool.dag.validate import (
    ValidationFinding,
    ValidationReport,
    validate_project,
)


def _write_project_manifest(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / "science.yaml").write_text(
        "name: dag-validation-test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _write_project_manifest_with_dags(project: Path, dags: list[str]) -> None:
    project.mkdir(parents=True, exist_ok=True)
    dag_lines = "\n".join(f"    - {dag}" for dag in dags)
    (project / "science.yaml").write_text(
        f"""name: dag-validation-test
knowledge_profiles:
  local: local
dag:
  dags:
{dag_lines}
""",
        encoding="utf-8",
    )


def _write_dot(project: Path, slug: str, body: str) -> Path:
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True, exist_ok=True)
    dot_path = dag_dir / f"{slug}.dot"
    dot_path.write_text(f"digraph {slug.replace('-', '_')} {{\n{body}\n}}\n", encoding="utf-8")
    return dot_path


def _write_proposition(
    project: Path,
    slug: str,
    subject: str,
    obj: str,
    *,
    legacy_patch: str | None = None,
    legacy_edge_id: int | None = None,
) -> None:
    prop = project / "entities/propositions" / f"{slug}.md"
    prop.parent.mkdir(parents=True, exist_ok=True)
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


def _write_propositions(project: Path, edges: list[tuple[str, str]]) -> None:
    for index, (subject, obj) in enumerate(edges, start=1):
        _write_proposition(project, f"{subject}-affects-{obj}-{index}", subject, obj)


def test_validation_report_ok_on_clean_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    _write_dot(project, "h1", "  a -> b;")
    _write_proposition(project, "a-affects-b", "a", "b")

    report = validate_project(load_dag_paths(project))

    assert isinstance(report, ValidationReport)
    assert report.ok, f"unexpected findings: {report.findings}"
    assert report.strict is False
    assert report.findings == ()


def test_validation_report_to_json_shape(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    _write_dot(project, "h1", "  a -> b;")
    _write_proposition(project, "a-affects-b", "a", "b")

    report = validate_project(load_dag_paths(project))
    js = report.to_json()

    assert js["ok"] is True
    assert js["strict"] is False
    assert js["findings"] == []
    assert "today" in js


def test_validation_finding_severity_literal() -> None:
    finding = ValidationFinding(
        dag="x",
        edge_id=1,
        rule="dot_nodes_unused",
        severity="strict_error",
        message="missing",
        location="x.dot",
    )
    report = ValidationReport(today=date.today(), strict=False, findings=(finding,))
    assert report.ok is True

    strict_report = ValidationReport(today=date.today(), strict=True, findings=(finding,))
    assert strict_report.ok is False


def test_validate_flags_dot_edge_without_matching_proposition(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    _write_dot(project, "h1", "  a -> b;")

    report = validate_project(load_dag_paths(project))

    assert not report.ok
    finding = next(f for f in report.findings if f.rule == "proposition_edge_missing")
    assert finding.dag == "h1"
    assert "a -> b" in finding.message


def test_validate_ignores_malformed_edges_yaml_when_dot_and_proposition_are_valid(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    dag_dir = project / "doc/figures/dags"
    _write_dot(project, "h1", "  a -> b;")
    (dag_dir / "h1.edges.yaml").write_text("not: [valid", encoding="utf-8")
    _write_proposition(project, "a-affects-b", "a", "b")

    report = validate_project(load_dag_paths(project))

    assert report.ok, report.findings


def test_validate_legacy_patch_edge_mismatch_when_referenced_dot_exists(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    _write_dot(project, "h2", "  x -> y;")
    _write_proposition(project, "x-affects-y", "x", "y")
    _write_proposition(project, "a-affects-b", "a", "b", legacy_patch="h2", legacy_edge_id=1)

    report = validate_project(load_dag_paths(project))

    assert not report.ok
    finding = next(f for f in report.findings if f.rule == "legacy_dag_edge_unresolved")
    assert "h2#1" in finding.message


def test_validate_legacy_patch_skipped_when_referenced_dot_absent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    _write_dot(project, "h1", "  a -> b;")
    _write_proposition(project, "a-affects-b", "a", "b", legacy_patch="h2", legacy_edge_id=1)

    report = validate_project(load_dag_paths(project))

    assert report.ok, report.findings
    assert not any(f.rule == "legacy_dag_edge_unresolved" for f in report.findings)


def test_validate_legacy_patch_matching_dot_edge_is_clean(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    _write_dot(project, "h1", "  a -> b;")
    _write_proposition(project, "a-affects-b", "a", "b", legacy_patch="h1", legacy_edge_id=1)

    report = validate_project(load_dag_paths(project))

    assert report.ok, report.findings


def test_validate_empty_project_with_no_dot_files_is_clean(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)

    report = validate_project(load_dag_paths(project))

    assert report.ok, report.findings
    assert report.findings == ()


def test_validate_configured_missing_dot_is_error(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest_with_dags(project, ["h1"])

    report = validate_project(load_dag_paths(project))

    assert not report.ok
    finding = next(f for f in report.findings if f.rule == "source_dot_missing")
    assert finding.dag == "h1"


def test_validate_configured_dot_needs_no_edges_yaml_when_backed_by_proposition(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest_with_dags(project, ["h1"])
    _write_dot(project, "h1", "  a -> b;")
    _write_proposition(project, "a-affects-b", "a", "b")

    report = validate_project(load_dag_paths(project))

    assert report.ok, report.findings
    assert not (project / "doc/figures/dags/h1.edges.yaml").exists()


def test_validate_ignores_generated_dot_files_during_auto_discovery(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "h1-auto.dot").write_text("digraph h1 {\n  missing -> edge;\n}\n", encoding="utf-8")
    (dag_dir / "h1-numbered.dot").write_text("digraph h1 {\n  missing -> edge;\n}\n", encoding="utf-8")
    (dag_dir / "h1.dot.reference").write_text("digraph h1 {\n  missing -> edge;\n}\n", encoding="utf-8")

    report = validate_project(load_dag_paths(project))

    assert report.ok, report.findings


def test_acyclicity_flags_cycle(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    edges = [("a", "b"), ("b", "c"), ("c", "a")]
    _write_dot(project, "h1", "  a -> b;\n  b -> c;\n  c -> a;")
    _write_propositions(project, edges)

    report = validate_project(load_dag_paths(project))

    acyclicity_findings = [f for f in report.findings if f.rule == "acyclicity"]
    assert len(acyclicity_findings) == 1
    msg = acyclicity_findings[0].message
    assert "a" in msg and "b" in msg and "c" in msg


def test_acyclicity_passes_on_clean(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    _write_dot(project, "h1", "  a -> b;")
    _write_proposition(project, "a-affects-b", "a", "b")

    report = validate_project(load_dag_paths(project))

    assert not any(f.rule == "acyclicity" for f in report.findings)


def test_strict_flags_orphan_dot_node(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    _write_dot(project, "h1", "  a -> b;\n  orphan;")
    _write_proposition(project, "a-affects-b", "a", "b")

    strict = validate_project(load_dag_paths(project), strict=True)

    rules = {f.rule for f in strict.findings if f.severity == "strict_error"}
    assert "dot_nodes_unused" in rules
    msg = next(f.message for f in strict.findings if f.rule == "dot_nodes_unused")
    assert "orphan" in msg


def test_non_strict_does_not_emit_strict_orphan_dot_node(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    _write_dot(project, "h1", "  a -> b;\n  orphan;")
    _write_proposition(project, "a-affects-b", "a", "b")

    non_strict = validate_project(load_dag_paths(project), strict=False)

    assert non_strict.ok, non_strict.findings
    assert not any(f.rule == "dot_nodes_unused" for f in non_strict.findings)


def test_strict_flags_cross_dag_node_case_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    _write_dot(project, "first", "  prc2 -> ifn;")
    _write_dot(project, "second", "  PRC2 -> other;")
    _write_propositions(project, [("prc2", "ifn"), ("PRC2", "other")])

    strict = validate_project(load_dag_paths(project), strict=True)

    rules = {f.rule for f in strict.findings if f.severity == "strict_error"}
    assert "cross_dag_node_consistency" in rules

    non_strict = validate_project(load_dag_paths(project), strict=False)
    assert non_strict.ok, non_strict.findings


def test_project_root_fallback_supports_default_layout_tests(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_project_manifest(project)
    dag_dir = project / "doc/figures/dags"
    tasks_dir = project / "tasks"
    _write_dot(project, "h1", "  a -> b;")
    _write_proposition(project, "a-affects-b", "a", "b")

    report = validate_project(DagPaths(dag_dir=dag_dir, tasks_dir=tasks_dir, dags=None))

    assert report.ok, report.findings
