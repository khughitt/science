from __future__ import annotations

import hashlib as _hashlib
import hashlib
import os
from pathlib import Path

import pytest

from science_tool.plan_common import (
    StateFingerprint, UnsupportedPathType, fingerprint, matches,
    ArchiveStatusSweep, ExplicitArchiveIds, AllSupersessionMembers, ExplicitSupersessionIds,
    PathTransition, EnvelopeError, plan_sha256, read_plan_bytes, verify_envelope,
    StagingError, classify_staging, staged_write, staging_path_for,
    PathEscape, RollbackHalt, SurfaceMismatch, assert_same_surface, assert_staging_unique,
    resolve_within, rollback_transitions, snapshot_paths,
)


def test_fingerprint_of_a_file_captures_content_mode_and_type(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("hello", encoding="utf-8")
    os.chmod(p, 0o644)
    fp = fingerprint(p)
    assert fp.existed is True
    assert fp.type == "file"
    assert fp.content_sha256 == hashlib.sha256(b"hello").hexdigest()
    assert fp.mode == 0o644
    assert fp.symlink_target is None
    assert matches(fp, p) is True


def test_fingerprint_of_absent_path(tmp_path: Path) -> None:
    fp = fingerprint(tmp_path / "missing")
    assert fp.existed is False
    assert fp.type is None
    assert fp.content_sha256 is None
    assert matches(fp, tmp_path / "missing") is True


def test_fingerprint_of_symlink_records_target_not_content(tmp_path: Path) -> None:
    target = tmp_path / "t.txt"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "l"
    link.symlink_to("t.txt")
    fp = fingerprint(link)
    assert fp.type == "symlink"
    assert fp.symlink_target == "t.txt"
    assert fp.content_sha256 is None


def test_fingerprint_of_directory_records_mode_not_content(tmp_path: Path) -> None:
    d = tmp_path / "sub"
    d.mkdir()
    os.chmod(d, 0o755)
    fp = fingerprint(d)
    assert fp.type == "dir"
    assert fp.content_sha256 is None
    assert fp.symlink_target is None
    assert fp.mode == 0o755


def test_fingerprint_refuses_unsupported_fs_object(tmp_path: Path) -> None:
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)  # a FIFO would block read_bytes()
    with pytest.raises(UnsupportedPathType):
        fingerprint(fifo)


def test_matches_is_false_when_content_changes(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("hello", encoding="utf-8")
    fp = fingerprint(p)
    p.write_text("world", encoding="utf-8")
    assert matches(fp, p) is False


def test_extra_forbid_on_state_fingerprint() -> None:
    with pytest.raises(ValueError):
        StateFingerprint(existed=False, type=None, content_sha256=None, mode=None,
                         symlink_target=None, bogus=1)  # type: ignore[call-arg]


@pytest.mark.parametrize("kwargs", [
    # present but no type
    dict(existed=True, type=None, content_sha256=None, mode=0o644, symlink_target=None),
    # absent but carries attributes
    dict(existed=False, type=None, content_sha256="x" * 64, mode=None, symlink_target=None),
    # file without content
    dict(existed=True, type="file", content_sha256=None, mode=0o644, symlink_target=None),
    # symlink without target
    dict(existed=True, type="symlink", content_sha256=None, mode=0o777, symlink_target=None),
    # dir carrying content
    dict(existed=True, type="dir", content_sha256="x" * 64, mode=0o755, symlink_target=None),
    # present without mode
    dict(existed=True, type="file", content_sha256="x" * 64, mode=None, symlink_target=None),
])
def test_state_fingerprint_rejects_incoherent_combinations(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        StateFingerprint(**kwargs)  # type: ignore[arg-type]


def _file_fp(content: str) -> StateFingerprint:
    return StateFingerprint(existed=True, type="file",
                            content_sha256=_hashlib.sha256(content.encode()).hexdigest(),
                            mode=0o644, symlink_target=None)


def _absent_fp() -> StateFingerprint:
    return StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)


def test_entity_rewrite_requires_postimage_hash_to_match_post() -> None:
    body = "new bytes"
    t = PathTransition(role="entity-rewrite", rel_path="entities/x/1.md",
                       pre=_file_fp("old"), post=_file_fp(body), postimage=body)
    assert t.postimage == body


def test_entity_rewrite_rejects_postimage_hash_mismatch() -> None:
    with pytest.raises(ValueError):
        PathTransition(role="entity-rewrite", rel_path="entities/x/1.md",
                       pre=_file_fp("old"), post=_file_fp("A"), postimage="B")


def test_archive_src_post_must_be_absent() -> None:
    with pytest.raises(ValueError):
        PathTransition(role="archive-src", rel_path="entities/x/1.md",
                       pre=_file_fp("x"), post=_file_fp("x"), postimage=None)


def test_created_dir_has_no_postimage_and_absent_pre() -> None:
    dir_post = StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None)
    t = PathTransition(role="created-dir", rel_path="entities/_archive/x",
                       pre=_absent_fp(), post=dir_post, postimage=None)
    assert t.postimage is None
    with pytest.raises(ValueError):
        PathTransition(role="created-dir", rel_path="entities/_archive/x",
                       pre=_absent_fp(), post=dir_post, postimage="oops")


def test_explicit_ids_reject_empty_and_unsorted_and_duplicate() -> None:
    with pytest.raises(ValueError):
        ExplicitSupersessionIds(kind="explicit_ids", ids=[])
    with pytest.raises(ValueError):
        ExplicitSupersessionIds(kind="explicit_ids", ids=["b:2", "a:1"])  # unsorted
    with pytest.raises(ValueError):
        ExplicitSupersessionIds(kind="explicit_ids", ids=["a:1", "a:1"])  # duplicate
    ok = ExplicitSupersessionIds(kind="explicit_ids", ids=["a:1", "b:2"])
    assert ok.ids == ["a:1", "b:2"]


def test_archive_status_sweep_and_explicit_ids_shapes() -> None:
    ArchiveStatusSweep(kind="all_by_status", statuses=["archived", "superseded"])
    ExplicitArchiveIds(kind="explicit_ids", ids=["x:1"], allowed_statuses=["superseded"])
    AllSupersessionMembers(kind="all")


def test_envelope_accepts_matching_and_rejects_mismatch(tmp_path: Path) -> None:
    p = tmp_path / "plan.json"
    p.write_bytes(b'{"a": 1}')
    raw = read_plan_bytes(p)
    assert raw == b'{"a": 1}'
    verify_envelope(raw, plan_sha256(raw))  # no raise
    with pytest.raises(EnvelopeError):
        verify_envelope(raw, "0" * 64)


def test_staged_write_replaces_atomically_with_mode(tmp_path: Path) -> None:
    target = tmp_path / "entities" / "x" / "1.md"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")
    staged_write(target, "new-bytes", 0o644, token="batch1", target_pre=fingerprint(target))
    assert target.read_text(encoding="utf-8") == "new-bytes"
    assert (os.stat(target).st_mode & 0o777) == 0o644
    assert not staging_path_for(target, "batch1").exists()  # tmp consumed


def test_staged_write_refuses_preexisting_staging_file(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    target.write_text("x", encoding="utf-8")
    staging_path_for(target, "batch1").write_text("stale", encoding="utf-8")
    with pytest.raises(StagingError):
        staged_write(target, "y", 0o644, token="batch1", target_pre=fingerprint(target))


def test_classify_staging_absent_prefix_complete(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    staging = staging_path_for(target, "b")
    assert classify_staging(staging, "hello") == "absent"
    staging.write_text("hel", encoding="utf-8")
    assert classify_staging(staging, "hello") == "prefix"
    staging.write_text("hello", encoding="utf-8")
    assert classify_staging(staging, "hello") == "complete"
    staging.write_text("hellX", encoding="utf-8")
    with pytest.raises(StagingError):
        classify_staging(staging, "hello")  # not a prefix -> interference


def test_staged_write_mid_kill_leaves_attributable_prefix_and_untouched_target(tmp_path: Path) -> None:
    # C3 / design §3.4: a kill DURING staging (BaseException from the `_fault` seam, after the write
    # but before replace) must leave the real writer in only-modeled state — a partial `.tmp` that is
    # a byte-prefix of the postimage, the target unchanged, and no other debris in the directory.
    class _Kill(BaseException):
        pass

    target = tmp_path / "entities" / "x" / "1.md"
    target.parent.mkdir(parents=True)
    target.write_text("original", encoding="utf-8")

    def fault(label: str) -> None:
        if label == "mid-write":
            raise _Kill()

    postimage = "brand-new-postimage"
    with pytest.raises(_Kill):
        staged_write(target, postimage, 0o644, token="batch1", target_pre=fingerprint(target), _fault=fault)

    assert target.read_text(encoding="utf-8") == "original"  # target never touched (attributable state)
    survivor = staging_path_for(target, "batch1")
    survivor_bytes = survivor.read_bytes()
    assert 0 < len(survivor_bytes) < len(postimage.encode())         # a STRICT, non-empty prefix
    assert classify_staging(survivor, postimage) == "prefix"          # not "complete"
    # no undeclared debris — only the target and the one attributable staging survivor exist
    assert {p.name for p in target.parent.iterdir()} == {target.name, survivor.name}


def test_staged_write_caught_error_removes_only_attributable_survivor(tmp_path: Path, monkeypatch) -> None:
    # The `except Exception` cleanup removes our own partial write when it is an attributable prefix.
    target = tmp_path / "a.md"
    target.write_text("x", encoding="utf-8")

    def boom(*a, **k):
        raise RuntimeError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(RuntimeError, match="replace failed"):
        staged_write(target, "hello", 0o644, token="b", target_pre=fingerprint(target))
    assert not staging_path_for(target, "b").exists()              # attributable prefix → cleaned up
    assert target.read_text(encoding="utf-8") == "x"               # target untouched (atomic replace)


def test_staged_write_refuses_to_remove_a_non_prefix_survivor(tmp_path: Path, monkeypatch) -> None:
    # If the survivor is NOT a byte-prefix of the postimage (concurrent interference), cleanup refuses
    # to delete it and raises — surfacing the anomaly instead of erasing evidence. Target stays put.
    target = tmp_path / "a.md"
    target.write_text("x", encoding="utf-8")

    def corrupt_then_fail(src, dst):
        Path(src).write_bytes(b"FOREIGN-NON-PREFIX")  # something we did not write appears at the tmp
        raise RuntimeError("replace failed")

    monkeypatch.setattr(os, "replace", corrupt_then_fail)
    with pytest.raises(StagingError, match="not an attributable prefix"):
        staged_write(target, "hello", 0o644, token="b", target_pre=fingerprint(target))
    assert staging_path_for(target, "b").exists()                  # NOT deleted — evidence preserved
    assert target.read_text(encoding="utf-8") == "x"               # target untouched


def test_staged_write_halts_when_target_changed_concurrently(tmp_path: Path, monkeypatch) -> None:
    # Critical (design §3.3): a survivor is removed only when the persistent TARGET is ALSO still
    # attributable to this op. If `os.replace` fails AFTER a concurrent writer changed the target, our
    # staged survivor is preserved as recovery evidence and the op HALTS — deleting it would erase the
    # only record that a write was in flight when the corpus diverged. The prefix predicate alone
    # (satisfied here — the survivor is a complete, attributable write) is NOT sufficient.
    target = tmp_path / "a.md"
    target.write_text("original", encoding="utf-8")
    target_pre = fingerprint(target)

    def change_target_then_fail(src, dst):
        Path(dst).write_bytes(b"CONCURRENT-EDIT-BY-SOMEONE-ELSE")  # target diverges before replace fails
        raise RuntimeError("replace failed")

    monkeypatch.setattr(os, "replace", change_target_then_fail)
    with pytest.raises(StagingError, match="target changed concurrently"):
        staged_write(target, "hello", 0o644, token="b", target_pre=target_pre)
    assert staging_path_for(target, "b").exists()                  # survivor preserved as evidence
    assert target.read_text(encoding="utf-8") == "CONCURRENT-EDIT-BY-SOMEONE-ELSE"  # target left as-found


def test_rollback_reverts_a_completed_write_to_pre(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    target = tmp_path / "e.md"
    target.write_text("OLD", encoding="utf-8")
    pre = fingerprint(target)
    snap = snapshot_paths([target])
    target.write_text("NEW", encoding="utf-8")  # simulate the write landed
    post = fingerprint(target)
    t = PathTransition(role="entity-rewrite", rel_path="e.md", pre=pre, post=post, postimage="NEW")
    rollback_transitions([t], tmp_path, snap)
    assert target.read_text(encoding="utf-8") == "OLD"


def test_rollback_preserves_non_default_file_mode(tmp_path: Path) -> None:
    target = tmp_path / "e.md"
    target.write_text("OLD", encoding="utf-8")
    os.chmod(target, 0o640)
    pre = fingerprint(target)
    snap = snapshot_paths([target])
    target.write_text("NEW", encoding="utf-8")
    os.chmod(target, 0o644)
    post = fingerprint(target)
    t = PathTransition(role="entity-rewrite", rel_path="e.md", pre=pre, post=post, postimage="NEW")
    rollback_transitions([t], tmp_path, snap)
    assert (os.stat(target).st_mode & 0o777) == 0o640  # exact mode restored


def test_rollback_restores_symlink_not_a_regular_file(tmp_path: Path) -> None:
    link = tmp_path / "l"
    link.symlink_to("t.txt")
    pre = fingerprint(link)
    snap = snapshot_paths([link])
    link.unlink()
    link.write_text("clobbered-as-file", encoding="utf-8")  # simulate a bad landing
    post = fingerprint(link)
    t = PathTransition(role="entity-rewrite", rel_path="l", pre=pre, post=post,
                       postimage="clobbered-as-file")
    rollback_transitions([t], tmp_path, snap)
    assert link.is_symlink()
    assert os.readlink(link) == "t.txt"


def test_rollback_removes_nested_created_dirs_bottom_up(tmp_path: Path) -> None:
    # archive-dst moved a file into a freshly created nested dir; rollback removes both.
    created_outer = tmp_path / "entities" / "_archive"
    created_inner = created_outer / "interpretations"
    moved = created_inner / "x.md"
    absent = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)
    dir_fp = StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None)
    # Snapshot BEFORE anything lands, so the snapshot records all three paths ABSENT (== pre).
    snap = snapshot_paths([created_outer, created_inner, moved])
    # Now simulate the landed state: both dirs created, file moved in.
    created_inner.mkdir(parents=True)
    os.chmod(created_inner, 0o755)
    os.chmod(created_outer, 0o755)
    moved.write_text("X", encoding="utf-8")
    dst = PathTransition(role="archive-dst", rel_path="entities/_archive/interpretations/x.md",
                         pre=absent, post=fingerprint(moved))
    outer = PathTransition(role="created-dir", rel_path="entities/_archive", pre=absent, post=dir_fp)
    inner = PathTransition(role="created-dir", rel_path="entities/_archive/interpretations",
                           pre=absent, post=dir_fp)
    # declared order is outer, inner, dst; rollback must process dst -> inner -> outer.
    rollback_transitions([outer, inner, dst], tmp_path, snap)
    assert not moved.exists()
    assert not created_inner.exists()
    assert not created_outer.exists()


def test_rollback_halts_when_a_transition_path_has_no_snapshot(tmp_path: Path) -> None:
    # A missing snapshot entry is a defect, not an empty-file reconstruction opportunity.
    target = tmp_path / "e.md"
    target.write_text("NEW", encoding="utf-8")
    pre = StateFingerprint(existed=True, type="file",
                           content_sha256=_hashlib.sha256(b"OLD").hexdigest(), mode=0o644, symlink_target=None)
    post = fingerprint(target)
    t = PathTransition(role="entity-rewrite", rel_path="e.md", pre=pre, post=post, postimage="NEW")
    with pytest.raises(RollbackHalt):
        rollback_transitions([t], tmp_path, {})  # empty snapshot -> halt, do NOT write empty bytes


def test_rollback_halts_on_concurrent_change(tmp_path: Path) -> None:
    target = tmp_path / "e.md"
    target.write_text("OLD", encoding="utf-8")
    pre = fingerprint(target)
    snap = snapshot_paths([target])
    post_fp = StateFingerprint(existed=True, type="file",
                               content_sha256=_hashlib.sha256(b"NEW").hexdigest(), mode=0o644, symlink_target=None)
    t = PathTransition(role="entity-rewrite", rel_path="e.md", pre=pre, post=post_fp, postimage="NEW")
    target.write_text("SOMEONE-ELSE", encoding="utf-8")  # matches neither pre nor post
    with pytest.raises(RollbackHalt):
        rollback_transitions([t], tmp_path, snap)


def test_resolve_within_rejects_absolute_and_escaping_and_noncanonical(tmp_path: Path) -> None:
    (tmp_path / "entities" / "x").mkdir(parents=True)
    assert resolve_within(tmp_path, "entities/x/1.md") == (tmp_path / "entities/x/1.md").resolve()
    for bad in ["/etc/passwd", "../evil", "a/../b", "a/./b", "a//b", "", "sub/"]:
        with pytest.raises(PathEscape):
            resolve_within(tmp_path, bad)


def test_resolve_within_rejects_ancestor_symlink_escape(tmp_path: Path) -> None:
    # `entities` is a symlink pointing OUTSIDE the project; a lexically-clean path under it must
    # still be refused, because it physically resolves outside the corpus.
    outside = tmp_path.parent / "outside_target"
    outside.mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    (root / "entities").symlink_to(outside)
    with pytest.raises(PathEscape):
        resolve_within(root, "entities/x.md")


def test_assert_same_surface_is_order_independent_and_strict() -> None:
    a = PathTransition(role="created-dir", rel_path="d1", pre=_absent_fp(),
                       post=StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None))
    b = PathTransition(role="created-dir", rel_path="d2", pre=_absent_fp(),
                       post=StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None))
    assert_same_surface([a, b], [b, a])  # no raise
    with pytest.raises(SurfaceMismatch):
        assert_same_surface([a], [a, b])


def test_assert_staging_unique_flags_collisions(tmp_path: Path) -> None:
    t1 = tmp_path / "a.md"
    assert_staging_unique(tmp_path, [t1, tmp_path / "b.md"], "tok")  # no raise
    with pytest.raises(StagingError):
        assert_staging_unique(tmp_path, [t1, t1], "tok")
