from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from science_tool.boundary.config import BoundaryConfig
from science_tool.boundary.probes import probe_paths
from science_tool.boundary.sync import BoundaryDirtyError, sync, verify_current_tree


def _repo(tmp_path: Path, boundary: dict, gitignore: str = "") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "D", "id": "d", "boundary": boundary}))
    (tmp_path / ".gitignore").write_text(gitignore)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True)
    return tmp_path


DECL = {"roots": [{"path": "data/external", "class": "manifest", "tracked": ["datapackage.json"]}]}


def test_probes_cover_depth_and_each_glob():
    cfg = BoundaryConfig.model_validate(DECL)
    probes = probe_paths(cfg)
    assert any(p.count("/") == 2 for p in probes)
    assert any(p.count("/") >= 4 for p in probes)
    assert any(p.endswith("datapackage.json") for p in probes)
    assert any(p.endswith(".parquet") for p in probes)


def test_sync_installs_block_and_is_idempotent(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    first = sync(repo)
    assert first.changed
    text = (repo / ".gitignore").read_text()
    second = sync(repo)
    assert not second.changed
    assert (repo / ".gitignore").read_text() == text


def test_verify_refuses_dirty_gitignore(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    (repo / ".gitignore").write_text("dirty\n")
    with pytest.raises(BoundaryDirtyError):
        verify_current_tree(repo)


def test_verify_restores_original_on_change(tmp_path: Path):
    repo = _repo(tmp_path, DECL, gitignore="/data/external/**\n")
    (repo / "data/external/ot").mkdir(parents=True)
    (repo / "data/external/ot/datapackage.json").write_text("{}")
    before = (repo / ".gitignore").read_text()
    diff = verify_current_tree(repo)
    assert diff, "descriptor decision must change"
    assert (repo / ".gitignore").read_text() == before


def test_verify_restores_original_when_clean(tmp_path: Path):
    repo = _repo(tmp_path, DECL, gitignore="")
    before = (repo / ".gitignore").read_text()
    verify_current_tree(repo)
    assert (repo / ".gitignore").read_text() == before


def test_verify_detects_a_flip_on_an_already_tracked_file(tmp_path: Path):
    """The reachability oracle CANNOT see this: an indexed file stays visible
    before and after, so the decision change would be reported as no change."""
    repo = _repo(tmp_path, DECL, gitignore="")
    (repo / "data/external/ot").mkdir(parents=True)
    target = repo / "data/external/ot/mm.parquet"
    target.write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "-f", str(target)], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "add"], check=True)
    changed = {p for p, _was, _now in verify_current_tree(repo)}
    assert "data/external/ot/mm.parquet" in changed


def test_verify_restores_absence_when_gitignore_did_not_exist(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    (repo / ".gitignore").unlink()
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "--cached", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "drop"], check=True)
    verify_current_tree(repo)
    assert not (repo / ".gitignore").exists(), "must restore absence, not write an empty file"


def test_verify_restores_on_exception(tmp_path: Path, monkeypatch):
    repo = _repo(tmp_path, DECL)
    before = (repo / ".gitignore").read_text()
    import science_tool.boundary.sync as sync_mod

    calls = 0

    def boom(*_a, **_k):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("boom")
        return {}

    monkeypatch.setattr(sync_mod, "_probe_decisions", boom)
    with pytest.raises(RuntimeError):
        verify_current_tree(repo)
    assert calls == 2
    assert (repo / ".gitignore").read_text() == before


@pytest.mark.parametrize("operation", [sync, verify_current_tree])
def test_root_gitignore_symlink_is_rejected_without_following(tmp_path: Path, operation):
    from science_tool.boundary.gitio import BoundaryGitError

    repo = _repo(tmp_path, DECL)
    outside = tmp_path / "outside-ignore"
    original = b"outside/\n"
    outside.write_bytes(original)
    gitignore = repo / ".gitignore"
    gitignore.unlink()
    gitignore.symlink_to(outside)
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "symlink"], check=True)

    with pytest.raises(BoundaryGitError, match="root .gitignore is a symlink"):
        operation(repo)

    assert gitignore.is_symlink()
    assert outside.read_bytes() == original


def test_verify_raises_when_git_status_fails(tmp_path: Path, monkeypatch):
    """A nonzero `git status` was treated as 'clean', so verification would go
    on to rewrite a .gitignore whose state it could not read -- the one moment
    the restore matters most."""
    from science_tool.boundary.gitio import BoundaryGitError
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)

    class _Failed:
        returncode = 128
        stdout = b""
        stderr = b"fatal: not a git repository"

    monkeypatch.setattr(sync_mod.subprocess, "run", lambda *a, **k: _Failed())
    with pytest.raises(BoundaryGitError, match="git status failed"):
        verify_current_tree(repo)


def test_verify_handles_a_non_utf8_filename(tmp_path: Path):
    """A legal git filename need not be valid UTF-8. `iter_repo_files` surfaces
    those bytes as surrogates, and a plain `.encode()` raised
    UnicodeEncodeError -- crashing verification on a tree git handles fine."""
    repo = _repo(tmp_path, DECL)
    (repo / "data").mkdir(exist_ok=True)
    bad = os.path.join(str(repo / "data"), b"caf\xe9.bin".decode("utf-8", "surrogateescape"))
    with open(bad.encode("utf-8", "surrogateescape"), "wb") as fh:
        fh.write(b"x")
    verify_current_tree(repo)


def test_sync_preserves_a_non_utf8_gitignore(tmp_path: Path):
    """Task 3 accepts byte-valued rules, so sync cannot silently restore the
    strict-UTF-8 assumption at a later boundary."""
    repo = _repo(tmp_path, DECL)
    original = b"caf\xe9/\n"
    (repo / ".gitignore").write_bytes(original)
    first = sync(repo)
    assert first.changed
    assert original in (repo / ".gitignore").read_bytes()
    assert not sync(repo).changed


def test_verify_restores_a_non_utf8_gitignore_byte_for_byte(tmp_path: Path):
    repo = _repo(tmp_path, DECL)
    original = b"caf\xe9/\n"
    (repo / ".gitignore").write_bytes(original)
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "raw ignore"], check=True)
    verify_current_tree(repo)
    assert (repo / ".gitignore").read_bytes() == original
