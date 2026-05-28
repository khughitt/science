from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.sequence_store import SequenceStoreError, open_store, refget_digest

_SEQ = "ACGTACGTACGTACGTTTTTGGGGCCCC"


def _make_store(tmp_path: Path, seq: str) -> tuple[Path, str]:
    digest = refget_digest(seq)
    (tmp_path / digest).write_text(seq, encoding="ascii")
    return tmp_path, digest


def test_full_and_sliced_reads(tmp_path: Path) -> None:
    root, digest = _make_store(tmp_path, _SEQ)
    store = open_store(root)
    assert store.sequence(digest) == _SEQ
    assert store.sequence(digest, 0, 4) == "ACGT"
    assert store.sequence(digest, 16, 20) == "TTTT"
    assert store.length(digest) == len(_SEQ)


def test_missing_contig_fails_loud(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    with pytest.raises(SequenceStoreError, match="not in sequence store"):
        store.sequence("SQ.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", 0, 4)


def test_corrupt_contig_fails_verification(tmp_path: Path) -> None:
    root, digest = _make_store(tmp_path, _SEQ)
    (root / digest).write_text("CORRUPTEDSEQUENCE", encoding="ascii")
    store = open_store(root)
    with pytest.raises(SequenceStoreError, match="refget digest mismatch"):
        store.sequence(digest, 0, 4)


@pytest.mark.parametrize(("start", "end"), [(-1, 4), (8, 4), (0, len(_SEQ) + 1)])
def test_invalid_slice_bounds_fail_loud(tmp_path: Path, start: int, end: int) -> None:
    root, digest = _make_store(tmp_path, _SEQ)
    store = open_store(root)
    with pytest.raises(SequenceStoreError, match="invalid sequence slice"):
        store.sequence(digest, start, end)


def test_stale_cache_short_read_fails_loud(tmp_path: Path) -> None:
    root, digest = _make_store(tmp_path, _SEQ)
    store = open_store(root)
    assert store.length(digest) == len(_SEQ)
    (root / digest).write_text(_SEQ[:4], encoding="ascii")

    with pytest.raises(SequenceStoreError, match="short read"):
        store.sequence(digest, 0, len(_SEQ))


def test_stale_cache_missing_file_fails_loud(tmp_path: Path) -> None:
    root, digest = _make_store(tmp_path, _SEQ)
    store = open_store(root)
    assert store.length(digest) == len(_SEQ)
    (root / digest).unlink()

    with pytest.raises(SequenceStoreError, match="not in sequence store"):
        store.sequence(digest, 0, 4)


@pytest.mark.parametrize(
    "digest",
    [
        "../x",
        "SQ.short",
        "SQ.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/",
        "SQ.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA+",
        "sha512:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    ],
)
def test_invalid_digest_fails_before_path_lookup(tmp_path: Path, digest: str) -> None:
    store = open_store(tmp_path)
    with pytest.raises(SequenceStoreError, match="invalid refget digest"):
        store.sequence(digest, 0, 4)


def test_refget_digest_matches_ga4gh_core_without_case_normalization() -> None:
    from ga4gh.core import sha512t24u

    seq = "ACgt"
    assert refget_digest(seq) == "SQ." + sha512t24u(seq.encode("ascii"))
    assert refget_digest(seq) != refget_digest(seq.upper())
