from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from science_tool.plan_common import (
    StateFingerprint, UnsupportedPathType, fingerprint, matches,
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


import hashlib as _hashlib

from science_tool.plan_common import PathTransition


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
