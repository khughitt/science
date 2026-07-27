from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.boundary.cli import boundary_group


def _repo(tmp_path: Path, boundary: dict | None = None) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    payload: dict = {"name": "D", "id": "d"}
    if boundary:
        payload["boundary"] = boundary
    (tmp_path / "science.yaml").write_text(yaml.safe_dump(payload))
    return tmp_path


DECL = {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}


def test_check_exits_zero_on_clean_repo(tmp_path: Path):
    repo = _repo(tmp_path)
    result = CliRunner().invoke(boundary_group, ["check", "--project-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "clean" in result.output


def test_check_exits_one_and_names_the_rule(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "data").mkdir()
    (repo / "data/x.csv").write_text("a")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "data/x.csv"], check=True)
    (repo / ".gitignore").write_text("/data/\n")
    result = CliRunner().invoke(boundary_group, ["check", "--project-root", str(repo)])
    assert result.exit_code == 1
    assert "data/x.csv" in result.output
    assert ".gitignore:1" in result.output


def test_check_renders_git_failure(tmp_path: Path):
    result = CliRunner().invoke(boundary_group, ["check", "--project-root", str(tmp_path)])
    assert result.exit_code == 2
    assert "boundary: git ls-files -z failed" in result.output


def test_sync_writes_the_block(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    result = CliRunner().invoke(boundary_group, ["sync", "--project-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "/data/external/**" in (repo / ".gitignore").read_text()


def test_sync_check_flag_reports_drift_without_writing(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    (repo / ".gitignore").write_text("")
    result = CliRunner().invoke(boundary_group, ["sync", "--check", "--project-root", str(repo)])
    assert result.exit_code == 1
    assert (repo / ".gitignore").read_text() == ""


def test_sync_renders_unsafe_gitignore_failure(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    (repo / "ignore-target").write_text("")
    (repo / ".gitignore").symlink_to("ignore-target")
    result = CliRunner().invoke(boundary_group, ["sync", "--project-root", str(repo)])
    assert result.exit_code == 2
    assert "boundary: cannot manage root .gitignore: root .gitignore is a symlink" in result.output


def test_init_discovers_an_already_ignored_payload_root(tmp_path: Path):
    """The whole point of an adoption aid: find roots that are ALREADY ignored."""
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("data/raw/*\n")
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/big.parquet").write_text("x" * 200_000)
    (repo / "data/external/ot").mkdir(parents=True)
    (repo / "data/external/ot/datapackage.json").write_text("{}")
    result = CliRunner().invoke(boundary_group, ["init", "--project-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "data/raw" in result.output
    assert "data/external" in result.output
    assert "boundary:" not in (repo / "science.yaml").read_text()


def test_init_proposes_only_the_descriptor_names_it_saw(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "data/external/ot").mkdir(parents=True)
    (repo / "data/external/ot/datapackage.yaml").write_text("{}")
    output = CliRunner().invoke(boundary_group, ["init", "--project-root", str(repo)]).output
    assert "datapackage.yaml" in output
    assert "datapackage.json" not in output
