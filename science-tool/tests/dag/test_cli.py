from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from science_tool.cli import main

FIXTURE_ROOT = Path(__file__).parent / "fixtures/mm30"


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

    return project


def test_cli_dag_render_writes_auto_artifacts(cli_project: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["dag", "render", "--project", str(cli_project)])
    assert result.exit_code == 0, result.output
    for slug in ("h1-prognosis", "h1-progression", "h2-subtype-architecture", "h1-h2-bridge"):
        assert (cli_project / f"doc/figures/dags/{slug}-auto.dot").exists()


def test_cli_dag_render_single_slug(cli_project: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["dag", "render", "--dag", "h1-progression", "--project", str(cli_project)])
    assert result.exit_code == 0
    assert (cli_project / "doc/figures/dags/h1-progression-auto.dot").exists()
    # Other DAGs should NOT be rendered:
    assert not (cli_project / "doc/figures/dags/h1-prognosis-auto.dot").exists()


def test_cli_dag_staleness_json_schema(cli_project: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["dag", "staleness", "--json", "--project", str(cli_project)])
    # Exit 0 or 1 depending on whether mm30 fixture has drift; parse regardless:
    assert result.exit_code in (0, 1)
    data = json.loads(result.output)
    assert {
        "today",
        "recent_days",
        "drifted_edges",
        "under_reviewed_edges",
        "unresolved_refs",
        "unpropagated_tasks",
    } <= set(data.keys())


def test_cli_dag_staleness_exit_code_on_clean_project(tmp_path: Path) -> None:
    """Empty project with no edges → staleness exits 0."""
    project = tmp_path / "project"
    (project / "doc/figures/dags").mkdir(parents=True)
    (project / "tasks").mkdir()
    (project / "tasks/active.md").write_text("")
    (project / "science.yaml").write_text("profile: research\n")
    runner = CliRunner()
    result = runner.invoke(main, ["dag", "staleness", "--project", str(project)])
    assert result.exit_code == 0


def test_cli_dag_audit_is_read_only_by_default(cli_project: Path) -> None:
    """dag audit without --fix must not mutate tasks/active.md or edges.yaml."""
    active_before = (cli_project / "tasks/active.md").read_text()
    runner = CliRunner()
    result = runner.invoke(main, ["dag", "audit", "--project", str(cli_project)])
    assert result.exit_code in (0, 1)
    assert (cli_project / "tasks/active.md").read_text() == active_before


def test_cli_dag_audit_fix_mutates(cli_project: Path) -> None:
    """dag audit --fix opens tasks (we'll only check that it doesn't error;
    actual mutation behavior is unit-tested in test_audit.py)."""
    runner = CliRunner()
    result = runner.invoke(main, ["dag", "audit", "--fix", "--project", str(cli_project)])
    # --fix path must run without error; it's OK if it also exits 1 (findings present).
    assert result.exit_code in (0, 1), result.output


def test_cli_dag_init_scaffolds_new_dag(cli_project: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["dag", "init", "h3-new-hypothesis", "--label", "H3 New", "--project", str(cli_project)]
    )
    assert result.exit_code == 0, result.output
    dot = cli_project / "doc/figures/dags/h3-new-hypothesis.dot"
    yaml_file = cli_project / "doc/figures/dags/h3-new-hypothesis.edges.yaml"
    assert dot.exists()
    assert yaml_file.exists()
    data = yaml.safe_load(yaml_file.read_text())
    assert data["dag"] == "h3-new-hypothesis"
    assert data["edges"] == []


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
    runner = CliRunner()
    r1 = runner.invoke(main, ["dag", "number", "--project", str(cli_project)])
    assert r1.exit_code == 0, r1.output
    first = (cli_project / "doc/figures/dags/h1-progression-numbered.dot").read_text()
    r2 = runner.invoke(main, ["dag", "number", "--project", str(cli_project)])
    assert r2.exit_code == 0
    second = (cli_project / "doc/figures/dags/h1-progression-numbered.dot").read_text()
    assert first == second
