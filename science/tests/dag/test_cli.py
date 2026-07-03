from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.dag.validate import _parse_dot_topology

FIXTURE_ROOT = Path(__file__).parent / "fixtures/mm30"
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


def test_cli_dag_schema_says_schema_is_retired(cli_project: Path) -> None:
    # Banner goes to STDERR so stdout stays pure JSON.
    result = CliRunner().invoke(main, ["dag", "schema"])

    assert result.exit_code == 0
    assert "RETIRED" in result.stderr
    assert "edges.yaml" in result.stderr
    json.loads(result.stdout)
