from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
import pytest
from pydantic import ValidationError

from science_tool.boundary.gitio import BoundaryGitError
from science_tool.data_audit import audit_project


def _repo(tmp_path: Path, boundary: dict | None = None, gitignore: str = "") -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    payload: dict = {"name": "D", "id": "d"}
    if boundary:
        payload["boundary"] = boundary
    (tmp_path / "science.yaml").write_text(yaml.safe_dump(payload))
    (tmp_path / ".gitignore").write_text(gitignore)
    return tmp_path


def test_ignored_tooling_noise_is_skipped(tmp_path: Path):
    repo = _repo(tmp_path, gitignore=".venv/\n")
    (repo / ".venv/lib").mkdir(parents=True)
    (repo / ".venv/lib/blob.csv").write_text("x")
    assert all(".venv" not in v.path for v in audit_project(repo))


def test_stranded_record_inside_declared_root_is_still_found(tmp_path: Path):
    decl = {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}
    repo = _repo(tmp_path, decl, gitignore="/data/external/**\n!/data/external/**/\n")
    (repo / "data/external/ds").mkdir(parents=True)
    (repo / "data/external/ds/RESULTS.md").write_text("# r\n")
    paths = [v.path for v in audit_project(repo)]
    assert "data/external/ds/RESULTS.md" in paths


def test_undeclared_project_audits_visible_files_only(tmp_path: Path):
    repo = _repo(tmp_path, gitignore="build/\n")
    (repo / "build").mkdir()
    (repo / "build/x.csv").write_text("x")
    (repo / "keep.csv").write_text("x")
    paths = [v.path for v in audit_project(repo)]
    assert "keep.csv" in paths
    assert "build/x.csv" not in paths


def test_invalid_boundary_declaration_fails_closed(tmp_path: Path):
    repo = _repo(tmp_path, boundary={"roots": "not-a-list"})
    with pytest.raises(ValidationError, match="roots"):
        audit_project(repo)


def test_missing_config_is_undeclared(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "keep.csv").write_text("x")
    assert "keep.csv" in [violation.path for violation in audit_project(tmp_path)]


def test_non_git_project_audits_all_paths(tmp_path: Path):
    (tmp_path / "science.yaml").write_text("name: D\nid: d\n")
    (tmp_path / "keep.csv").write_text("x")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv/tool.csv").write_text("x")
    paths = [violation.path for violation in audit_project(tmp_path)]
    assert "keep.csv" in paths
    assert ".venv/tool.csv" in paths


def test_nested_project_uses_parent_git_visibility(tmp_path: Path):
    repo = tmp_path / "parent"
    repo.mkdir()
    _repo(repo, gitignore="nested/build/\n")
    project = repo / "nested"
    project.mkdir()
    (project / "science.yaml").write_text("name: D\nid: d\n")
    (project / "build").mkdir()
    (project / "build/x.csv").write_text("x")
    (project / "keep.csv").write_text("x")
    paths = [violation.path for violation in audit_project(project)]
    assert "keep.csv" in paths
    assert "build/x.csv" not in paths


def test_corrupt_git_marker_fails_closed(tmp_path: Path):
    (tmp_path / "science.yaml").write_text("name: D\nid: d\n")
    (tmp_path / ".git").write_text("not a gitdir\n")
    with pytest.raises(BoundaryGitError):
        audit_project(tmp_path)
