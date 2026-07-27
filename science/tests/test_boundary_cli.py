from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from science_tool.boundary.cli import boundary_group
from science_tool.boundary.generate import MANAGED_BEGIN


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
_COMMANDS = (
    ("check",),
    ("sync",),
    ("sync", "--check"),
    ("sync", "--verify-current-tree"),
    ("init",),
)
_SYNC_COMMANDS = _COMMANDS[1:4]


def _invoke(repo: Path, command: tuple[str, ...]):
    return CliRunner().invoke(boundary_group, [*command, "--project-root", str(repo)])


def _assert_boundary_error(result) -> None:
    assert result.exit_code == 2
    assert "boundary:" in result.output
    assert "Traceback" not in result.output


def _break_config(repo: Path, kind: str) -> None:
    config = repo / "science.yaml"
    if kind == "malformed-yaml":
        config.write_text("name: [\n")
    elif kind == "invalid-schema":
        config.write_text("name: D\nid: d\nboundary: not-a-mapping\n")
    elif kind == "top-level-list":
        config.write_text("- name: D\n")
    elif kind == "top-level-scalar":
        config.write_text("D\n")
    elif kind == "missing":
        config.unlink()
    elif kind == "unreadable":
        config.unlink()
        config.mkdir()
    else:
        raise AssertionError(f"unknown config failure kind {kind!r}")


def _commit(repo: Path, *paths: str) -> None:
    subprocess.run(["git", "-C", str(repo), "add", *paths], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)


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


def test_check_reports_tracked_ignored_before_deferred_config_error(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    (repo / "data").mkdir()
    (repo / "data/x.csv").write_text("a")
    subprocess.run(["git", "-C", str(repo), "add", "-f", "data/x.csv"], check=True)
    (repo / ".gitignore").write_text("/data/\n")
    _break_config(repo, "invalid-schema")
    result = _invoke(repo, ("check",))
    _assert_boundary_error(result)
    assert "data/x.csv" in result.output
    assert ".gitignore:1" in result.output
    assert result.output.index("data/x.csv") < result.output.index("\nboundary:")
    assert "vcs-boundary: clean" not in result.output


@pytest.mark.parametrize("command", _COMMANDS)
@pytest.mark.parametrize(
    "kind",
    ("malformed-yaml", "invalid-schema", "top-level-list", "top-level-scalar", "missing", "unreadable"),
)
def test_commands_render_project_config_failures(tmp_path: Path, command: tuple[str, ...], kind: str):
    repo = _repo(tmp_path, DECL)
    _break_config(repo, kind)
    _assert_boundary_error(_invoke(repo, command))


def test_check_renders_malformed_managed_block(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    (repo / ".gitignore").write_text(f"{MANAGED_BEGIN}\n")
    _commit(repo, ".gitignore")
    _assert_boundary_error(_invoke(repo, ("check",)))


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


@pytest.mark.parametrize("command", _SYNC_COMMANDS)
def test_sync_branches_render_malformed_managed_block(tmp_path: Path, command: tuple[str, ...]):
    repo = _repo(tmp_path, DECL)
    (repo / ".gitignore").write_text(f"{MANAGED_BEGIN}\n")
    _commit(repo, ".gitignore")
    _assert_boundary_error(_invoke(repo, command))


@pytest.mark.parametrize("command", _SYNC_COMMANDS)
def test_sync_branches_render_empty_boundary_declaration(tmp_path: Path, command: tuple[str, ...]):
    repo = _repo(tmp_path, {"roots": []})
    _assert_boundary_error(_invoke(repo, command))


def test_sync_verify_renders_dirty_gitignore(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    (repo / ".gitignore").write_text("dirty\n")
    _assert_boundary_error(_invoke(repo, ("sync", "--verify-current-tree")))


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
