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
def test_root_gitignore_swap_before_atomic_replace_preserves_outside_target(tmp_path: Path, monkeypatch, operation):
    from science_tool.boundary.gitio import BoundaryGitError
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)
    gitignore = repo / ".gitignore"
    outside = tmp_path / "outside-ignore"
    original = b"outside/\n"
    outside.write_bytes(original)

    def swap_to_symlink(path: Path):
        path.unlink()
        path.symlink_to(outside)

    monkeypatch.setattr(sync_mod, "_before_atomic_replace", swap_to_symlink)
    with pytest.raises(BoundaryGitError, match="symlink"):
        operation(repo)

    assert gitignore.is_symlink()
    assert outside.read_bytes() == original


def test_verify_preserves_concurrent_edit_instead_of_restoring_over_it(tmp_path: Path, monkeypatch):
    from science_tool.boundary.gitio import BoundaryGitError
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)
    concurrent = b"concurrent\n"
    calls = 0

    def edit_after_install(_root: Path, paths: list[str]) -> dict[str, bool]:
        nonlocal calls
        calls += 1
        if calls == 2:
            (repo / ".gitignore").write_bytes(concurrent)
        return {path: False for path in paths}

    monkeypatch.setattr(sync_mod, "_probe_decisions", edit_after_install)
    with pytest.raises(BoundaryGitError, match="changed during verification"):
        verify_current_tree(repo)

    assert (repo / ".gitignore").read_bytes() == concurrent


def test_verify_preserves_same_byte_candidate_replacement(tmp_path: Path, monkeypatch):
    from science_tool.boundary.gitio import BoundaryGitError
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)
    replacement_inode = 0

    def replace_candidate(path: Path):
        nonlocal replacement_inode
        replacement = path.with_name("concurrent-ignore")
        replacement.write_bytes(path.read_bytes())
        os.replace(replacement, path)
        replacement_inode = path.stat().st_ino

    monkeypatch.setattr(sync_mod, "_after_atomic_replace", replace_candidate)
    with pytest.raises(BoundaryGitError, match="candidate installation"):
        verify_current_tree(repo)

    assert (repo / ".gitignore").stat().st_ino == replacement_inode


def test_staging_cleanup_preserves_replaced_temp_name(tmp_path: Path, monkeypatch):
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)
    replacement = b"concurrent temp\n"
    staged_path: Path | None = None

    def abort_replace(_path: Path):
        raise RuntimeError("abort")

    def replace_staged(path: Path):
        nonlocal staged_path
        path.unlink()
        path.write_bytes(replacement)
        staged_path = path

    monkeypatch.setattr(sync_mod, "_before_atomic_replace", abort_replace)
    monkeypatch.setattr(sync_mod, "_before_staged_cleanup", replace_staged)
    with pytest.raises(RuntimeError, match="abort"):
        sync(repo)

    assert staged_path is not None
    assert staged_path.read_bytes() == replacement


def test_staging_cleanup_removes_unchanged_temp_on_pre_replace_failure(tmp_path: Path, monkeypatch):
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)

    def abort_replace(_path: Path):
        raise RuntimeError("abort")

    monkeypatch.setattr(sync_mod, "_before_atomic_replace", abort_replace)
    with pytest.raises(RuntimeError, match="abort"):
        sync(repo)

    assert not list(repo.glob(".science-boundary-*.tmp"))


def test_verify_preserves_symlink_swapped_during_absent_file_cleanup(tmp_path: Path, monkeypatch):
    from science_tool.boundary.gitio import BoundaryGitError
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)
    gitignore = repo / ".gitignore"
    gitignore.unlink()
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "--cached", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "drop"], check=True)
    outside = tmp_path / "outside-ignore"
    outside.write_bytes(b"outside\n")
    replacements = 0
    probes = 0

    def swap_on_restore(path: Path):
        nonlocal replacements
        replacements += 1
        if replacements == 2:
            path.unlink()
            path.symlink_to(outside)

    def fail_after_install(*_a, **_k):
        nonlocal probes
        probes += 1
        if probes == 2:
            raise RuntimeError("probe failure")
        return {}

    monkeypatch.setattr(sync_mod, "_before_atomic_replace", swap_on_restore)
    monkeypatch.setattr(sync_mod, "_probe_decisions", fail_after_install)
    with pytest.raises(BoundaryGitError, match="symlink"):
        verify_current_tree(repo)

    assert gitignore.is_symlink()
    assert outside.read_bytes() == b"outside\n"


def test_verify_restores_when_candidate_git_probe_fails(tmp_path: Path, monkeypatch):
    from science_tool.boundary.gitio import BoundaryGitError
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)
    before = (repo / ".gitignore").read_bytes()
    real_run = sync_mod.subprocess.run
    probes = 0

    class _Failed:
        returncode = 128
        stdout = b""
        stderr = b"fatal: injected failure"

    def fail_second_probe(args, **kwargs):
        nonlocal probes
        if "check-ignore" in args:
            probes += 1
            if probes == 2:
                return _Failed()
        return real_run(args, **kwargs)

    monkeypatch.setattr(sync_mod.subprocess, "run", fail_second_probe)
    with pytest.raises(BoundaryGitError, match="check-ignore failed"):
        verify_current_tree(repo)

    assert probes == 2
    assert (repo / ".gitignore").read_bytes() == before


@pytest.mark.parametrize(
    ("stdout", "problem"),
    [
        (b"data/external/probe.bin", "terminate"),
        (b"\0", "empty"),
        (b"outside/probe.bin\0", "unexpected"),
    ],
)
def test_probe_decisions_rejects_malformed_git_output(tmp_path: Path, monkeypatch, stdout: bytes, problem: str):
    from science_tool.boundary.gitio import BoundaryGitError
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)

    class _Result:
        returncode = 0
        stderr = b""

        def __init__(self, output: bytes):
            self.stdout = output

    monkeypatch.setattr(sync_mod.subprocess, "run", lambda *_a, **_k: _Result(stdout))
    with pytest.raises(BoundaryGitError, match=problem):
        sync_mod._probe_decisions(repo, ["data/external/probe.bin"])


@pytest.mark.parametrize(
    ("returncode", "stdout", "problem"),
    [
        (1, b"data/external/probe.bin\0", "return code 1"),
        (0, b"", "return code 0"),
    ],
)
def test_probe_decisions_rejects_impossible_git_return_output_pairs(
    tmp_path: Path,
    monkeypatch,
    returncode: int,
    stdout: bytes,
    problem: str,
):
    from science_tool.boundary.gitio import BoundaryGitError
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)

    class _Result:
        stderr = b""

        def __init__(self, code: int, output: bytes):
            self.returncode = code
            self.stdout = output

    monkeypatch.setattr(sync_mod.subprocess, "run", lambda *_a, **_k: _Result(returncode, stdout))
    with pytest.raises(BoundaryGitError, match=problem):
        sync_mod._probe_decisions(repo, ["data/external/probe.bin"])


def test_verify_deduplicates_real_paths_and_probes(tmp_path: Path, monkeypatch):
    import science_tool.boundary.sync as sync_mod

    repo = _repo(tmp_path, DECL)
    path = repo / "data/external/probe.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x")
    calls: list[list[str]] = []

    def decisions(_root: Path, paths: list[str]) -> dict[str, bool]:
        calls.append(paths)
        return {item: False for item in paths}

    monkeypatch.setattr(sync_mod, "_probe_decisions", decisions)
    verify_current_tree(repo)

    assert len(calls) == 2
    assert all(paths == sorted(paths) for paths in calls)
    assert all(paths.count("data/external/probe.bin") == 1 for paths in calls)


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
