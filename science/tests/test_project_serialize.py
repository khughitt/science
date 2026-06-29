import json
import subprocess
from pathlib import Path

import pytest

from science_tool.data_worktree import DEFAULT_DATA_DIRS
from science_tool.project_package.serialize import (
    SerializeError,
    _build_manifest,
    _payload_inventory,
    _selected_source,
    _tracked_files,
)


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _write(root: Path, rel: str, content: bytes = b"x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def _commit_all(root: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, check=True)


def test_tracked_files_raises_without_git(tmp_path: Path):
    with pytest.raises(SerializeError):
        _tracked_files(tmp_path)


def test_selected_source_filters_to_roots_and_singles():
    tracked = [
        "science.yaml",
        "papers/references.bib",
        "knowledge/graph.trig",
        "entities/questions/q1.md",
        "results/exp/summary.md",
        "doc/notes.md",          # excluded: not a source root / single
        "data/processed/x.csv",  # excluded: data/
        "README.md",             # excluded: untracked-root single not in allowlist
    ]
    assert _selected_source(tracked) == [
        "entities/questions/q1.md",
        "knowledge/graph.trig",
        "papers/references.bib",
        "results/exp/summary.md",
        "science.yaml",
    ]


def test_payload_inventory_hashes_data_without_copy(tmp_path: Path):
    import hashlib
    _write(tmp_path, "data/processed/a.parquet", b"\x01\x02\x03")
    inv = _payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set=set())
    assert inv == [{
        "path": "data/processed/a.parquet",
        "sha256": hashlib.sha256(b"\x01\x02\x03").hexdigest(),
        "bytes": 3,
        "git_tracked": False,
    }]


def test_payload_inventory_marks_tracked(tmp_path: Path):
    _write(tmp_path, "data/raw/t.bin", b"\x00")
    inv = _payload_inventory(
        tmp_path, DEFAULT_DATA_DIRS, tracked_set={"data/raw/t.bin"}
    )
    assert inv[0]["git_tracked"] is True


def test_payload_inventory_guards_symlink_cycle(tmp_path: Path):
    d = tmp_path / "data" / "processed"
    d.mkdir(parents=True)
    (d / "loop").symlink_to(tmp_path / "data" / "processed", target_is_directory=True)
    with pytest.raises(SerializeError):
        _payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set=set())


def test_build_manifest_shape(tmp_path: Path):
    from science_tool.project_package.core import file_resource
    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\nlast_modified: 2026-06-29\n")
    files = [file_resource(tmp_path, "science.yaml")]
    payloads = [{"path": "data/raw/a", "sha256": "ab", "bytes": 1, "git_tracked": False}]
    manifest = _build_manifest(
        tmp_path, files, payloads, audit_passed=True, forced=False, git_commit="abc123"
    )
    assert manifest["schema_version"] == "science-project-serialized.v1"
    assert manifest["project"]["id"] == "demo"
    assert manifest["project"]["label"] == "Demo"
    assert manifest["boundary_audit"] == {"passed": True, "forced": False}
    assert manifest["files"][0]["path"] == "science.yaml"
    assert manifest["payloads"] == payloads
    assert manifest["data_version"].startswith("2026-06-29+")


def test_data_version_changes_on_path_rename(tmp_path: Path):
    # Canonical-record hashing: identical bytes at a different path must change
    # the version (the manifest changed, so the version must too).
    from science_tool.project_package.core import FileResource

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\nlast_modified: 2026-06-29\n")
    a = [FileResource(path="entities/a.md", sha256="deadbeef", bytes=4)]
    b = [FileResource(path="entities/b.md", sha256="deadbeef", bytes=4)]
    va = _build_manifest(
        tmp_path, a, [], audit_passed=True, forced=False, git_commit="abc123"
    )["data_version"]
    vb = _build_manifest(
        tmp_path, b, [], audit_passed=True, forced=False, git_commit="abc123"
    )["data_version"]
    assert va != vb
