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


def test_write_archive_is_deterministic(tmp_path: Path):
    import tarfile
    from science_tool.project_package.core import file_resource
    from science_tool.project_package.serialize import _build_manifest, _write_archive

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\nlast_modified: 2026-06-29\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    files = [file_resource(tmp_path, "science.yaml"),
             file_resource(tmp_path, "entities/questions/q1.md")]
    manifest = _build_manifest(
        tmp_path, files, [], audit_passed=True, forced=False, git_commit="abc123"
    )

    a = tmp_path / "a.tar.gz"
    b = tmp_path / "b.tar.gz"
    _write_archive(a, tmp_path, "demo", files, manifest)
    _write_archive(b, tmp_path, "demo", files, manifest)
    assert a.read_bytes() == b.read_bytes()  # byte-identical

    with tarfile.open(a, "r:gz") as tar:
        names = tar.getnames()
        assert names == sorted(names)  # sorted members
        assert "demo/manifest.json" in names
        assert "demo/entities/questions/q1.md" in names
        for m in tar.getmembers():
            assert m.mtime == 0 and m.uid == 0 and m.gid == 0
            assert m.uname == "" and m.gname == "" and m.mode == 0o644


def test_serialize_happy_path(tmp_path: Path):
    import tarfile
    from science_tool.project_package.serialize import serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\nlast_modified: 2026-06-29\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _write(tmp_path, "results/exp/summary.md", b"# s\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    # Untracked payload (the healthy case): inventoried by hash, never copied,
    # not a TRACKED_PAYLOAD violation.
    _write(tmp_path, "data/processed/big.parquet", b"\x09" * 16)

    out = tmp_path.parent / "bundle.tar.gz"
    result = serialize_project(tmp_path, out, force=False)
    assert result.out_path == out and out.exists()
    assert result.forced is False

    with tarfile.open(out, "r:gz") as tar:
        names = set(tar.getnames())
        manifest = json.loads(tar.extractfile("demo/manifest.json").read())
    assert "demo/entities/questions/q1.md" in names
    assert "demo/results/exp/summary.md" in names
    assert "demo/science.yaml" in names
    # data/ never copied:
    assert not any(n.startswith("demo/data/") for n in names)
    # but inventoried by hash:
    assert manifest["payloads"][0]["path"] == "data/processed/big.parquet"
    assert manifest["payloads"][0]["git_tracked"] is False
    assert all(f["path"] != "data/processed/big.parquet" for f in manifest["files"])
    assert manifest["boundary_audit"] == {"passed": True, "forced": False}


def test_serialize_omits_untracked_results(tmp_path: Path):
    import tarfile
    from science_tool.project_package.serialize import serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "results/exp/tracked.md", b"# t\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    _write(tmp_path, "results/exp/untracked.md", b"# u\n")  # never committed

    out = tmp_path.parent / "b2.tar.gz"
    serialize_project(tmp_path, out)
    with tarfile.open(out, "r:gz") as tar:
        names = set(tar.getnames())
    assert "demo/results/exp/tracked.md" in names
    assert "demo/results/exp/untracked.md" not in names


def test_serialize_refuses_on_boundary_violation(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    # A stranded record under data/ is a boundary violation.
    _write(tmp_path, "data/processed/exp/RESULTS.md", b"# results\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)

    out = tmp_path.parent / "b3.tar.gz"
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, out, force=False)
    assert not out.exists()

    # --force builds and records forced=true.
    result = serialize_project(tmp_path, out, force=True)
    assert result.forced is True and out.exists()


def test_serialize_rejects_out_inside_root(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, tmp_path / "results" / "bundle.tar.gz")


def test_serialize_requires_tracked_science_yaml(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _init_repo(tmp_path)
    subprocess.run(["git", "add", "entities/questions/q1.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=tmp_path, check=True)  # yaml untracked
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, tmp_path.parent / "b4.tar.gz")


def test_serialize_refuses_dirty_source(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    (tmp_path / "entities" / "questions" / "q1.md").write_bytes(b"# q changed\n")  # dirty vs HEAD
    out = tmp_path.parent / "dirty.tar.gz"
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, out)
    assert not out.exists()


def test_serialize_reports_dirty_source_before_invalid_config(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    # The dirty science.yaml is now invalid YAML, but source drift should be
    # reported first because the package promises reproducibility from HEAD.
    (tmp_path / "science.yaml").write_text("id: [unterminated\n", encoding="utf-8")
    with pytest.raises(SerializeError, match="differ from HEAD"):
        serialize_project(tmp_path, tmp_path.parent / "dirty-config.tar.gz")


def test_serialize_rejects_symlink_source(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "entities/questions/real.md", b"# real\n")
    (tmp_path / "entities" / "questions" / "link.md").symlink_to(
        tmp_path / "entities" / "questions" / "real.md"
    )
    _init_repo(tmp_path)
    _commit_all(tmp_path)  # git tracks the symlink as a symlink
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, tmp_path.parent / "sym.tar.gz")


def test_serialize_requires_head_commit(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _init_repo(tmp_path)
    subprocess.run(["git", "add", "science.yaml"], cwd=tmp_path, check=True)  # staged, never committed
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, tmp_path.parent / "nohead.tar.gz")


def test_serialize_rejects_unsafe_project_id(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: bad/id\nname: Demo\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    out = tmp_path.parent / "bad.tar.gz"
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, out)
    assert not out.exists()


def test_serialize_wraps_oserror_on_unreadable_payload(tmp_path: Path):
    import os
    import stat

    from science_tool.project_package.serialize import SerializeError, serialize_project

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root bypasses file permissions")
    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    payload = _write(tmp_path, "data/processed/secret.bin", b"\x00")  # untracked payload
    payload.chmod(0)
    try:
        with pytest.raises(SerializeError):
            serialize_project(tmp_path, tmp_path.parent / "oserr.tar.gz")
    finally:
        payload.chmod(stat.S_IRUSR | stat.S_IWUSR)
