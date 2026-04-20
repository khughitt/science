from pathlib import Path

import pytest

from science_tool.dag.paths import DagPaths, load_dag_paths  # noqa: F401


def test_load_dag_paths_reads_explicit_block(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "profile: research\ndag:\n  dag_dir: custom/dag\n  tasks_dir: backlog\n  dags:\n    - h1\n    - h2\n"
    )
    paths = load_dag_paths(tmp_path)
    assert paths.dag_dir == tmp_path / "custom/dag"
    assert paths.tasks_dir == tmp_path / "backlog"
    assert paths.dags == ("h1", "h2")


def test_load_dag_paths_research_profile_defaults(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("profile: research\n")
    paths = load_dag_paths(tmp_path)
    assert paths.dag_dir == tmp_path / "doc/figures/dags"
    assert paths.tasks_dir == tmp_path / "tasks"
    assert paths.dags is None  # auto-discover


def test_load_dag_paths_software_profile_without_block_errors(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("profile: software\n")
    with pytest.raises(FileNotFoundError, match="dag:"):
        load_dag_paths(tmp_path)
