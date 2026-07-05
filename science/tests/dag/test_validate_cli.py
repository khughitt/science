"""Click-runner tests for `science dag validate` + `dag schema`."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from click.testing import CliRunner

from science_tool.dag.cli import dag_group
from science_tool.dag.validate import _parse_dot_topology

FIXTURE_MINIMAL = Path(__file__).parent / "fixtures" / "minimal"
FIXTURE_MM30 = Path(__file__).parent / "fixtures" / "mm30"


def _write_proposition(project: Path, slug: str, source: str, target: str) -> None:
    prop_dir = project / "entities/propositions"
    prop_dir.mkdir(parents=True, exist_ok=True)
    (prop_dir / f"{slug}.md").write_text(
        f"""---
id: proposition:{slug}
kind: proposition
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


def _copy_fixture_with_propositions(source: Path, target: Path) -> Path:
    shutil.copytree(source, target)
    for edge_yaml in target.glob("doc/figures/dags/*.edges.yaml"):
        edge_yaml.unlink()
    for dot_path in sorted((target / "doc/figures/dags").glob("*.dot")):
        _, dot_edges = _parse_dot_topology(dot_path)
        for index, (source_node, target_node) in enumerate(sorted(dot_edges), start=1):
            _write_proposition(target, f"{dot_path.stem}-{index}", source_node, target_node)
    return target


def test_schema_stdout_is_valid_json() -> None:
    runner = CliRunner()
    result = runner.invoke(dag_group, ["schema"])
    assert result.exit_code == 0
    assert "RETIRED" in result.stderr
    assert "edges.yaml" in result.stderr
    data = json.loads(result.stdout)
    assert data.get("title") == "EdgesYamlFile"


def test_schema_write_to_file(tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "s.json"
    result = runner.invoke(dag_group, ["schema", "--output", str(out)])
    assert result.exit_code == 0
    assert "RETIRED" in result.stderr
    assert "edges.yaml" in result.stderr
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data.get("title") == "EdgesYamlFile"


def test_validate_clean_exits_zero(tmp_path: Path) -> None:
    project = _copy_fixture_with_propositions(FIXTURE_MINIMAL / "clean", tmp_path / "clean")
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        ["validate", "--project", str(project)],
    )
    assert result.exit_code == 0, result.output


def test_validate_cyclic_exits_one(tmp_path: Path) -> None:
    project = _copy_fixture_with_propositions(FIXTURE_MINIMAL / "cyclic", tmp_path / "cyclic")
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        ["validate", "--project", str(project)],
    )
    assert result.exit_code == 1
    assert "acyclicity" in result.output


def test_validate_json_shape(tmp_path: Path) -> None:
    project = _copy_fixture_with_propositions(FIXTURE_MINIMAL / "clean", tmp_path / "clean")
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        [
            "validate",
            "--json",
            "--project",
            str(project),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["strict"] is False
    assert data["findings"] == []


def test_validate_dag_scope(tmp_path: Path) -> None:
    # The mm30 fixture has 4 DAGs. --dag h1-h2-bridge restricts to one.
    project = _copy_fixture_with_propositions(FIXTURE_MM30, tmp_path / "mm30")
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        [
            "validate",
            "--dag",
            "h1-h2-bridge",
            "--project",
            str(project),
        ],
    )
    assert result.exit_code == 0, result.output


def test_validate_configured_dag_without_edges_yaml_exits_zero(tmp_path: Path) -> None:
    project = tmp_path / "project"
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (project / "science.yaml").write_text(
        "name: dag-validation-test\nknowledge_profiles:\n  local: local\ndag:\n  dags:\n    - h1\n",
        encoding="utf-8",
    )
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    _write_proposition(project, "a-affects-b", "a", "b")

    result = CliRunner().invoke(dag_group, ["validate", "--project", str(project)])

    assert result.exit_code == 0, result.output
    assert not (dag_dir / "h1.edges.yaml").exists()


def test_audit_json_includes_validation(tmp_path: Path) -> None:
    import json

    project = _copy_fixture_with_propositions(FIXTURE_MINIMAL / "clean", tmp_path / "clean")
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        ["audit", "--json", "--project", str(project)],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "validation" in data
    assert data["validation"]["ok"] is True
