from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
from types import TracebackType
from typing import Self

import httpx
import pytest

from science_tool.commons.sequence_store import refget_digest
from science_tool.commons.sequence_store_build import fetch_fasta, slice_fasta_to_store


def test_slice_fasta_preserves_exact_case_and_manifest_hashes(tmp_path: Path) -> None:
    fasta_path = tmp_path / "genome.fa"
    fasta_path.write_text(">1 chromosome 1\nACgt\nacGT\n>MT\nTTtt\n", encoding="ascii")

    manifest = slice_fasta_to_store(fasta_path, tmp_path / "store")

    chr1_seq = "ACgtacGT"
    chr1_digest = refget_digest(chr1_seq)
    assert (tmp_path / "store" / chr1_digest).read_text(encoding="ascii") == chr1_seq
    assert refget_digest(chr1_seq) != refget_digest(chr1_seq.upper())
    assert manifest == [
        {
            "name": "1",
            "refget_digest": chr1_digest,
            "length": len(chr1_seq),
            "sha256": hashlib.sha256(chr1_seq.encode("ascii")).hexdigest(),
        },
        {
            "name": "MT",
            "refget_digest": refget_digest("TTtt"),
            "length": 4,
            "sha256": hashlib.sha256(b"TTtt").hexdigest(),
        },
    ]


def test_slice_fasta_rejects_empty_contig(tmp_path: Path) -> None:
    fasta_path = tmp_path / "genome.fa"
    fasta_path.write_text(">1\n\n>2\nACGT\n", encoding="ascii")

    with pytest.raises(ValueError, match="empty contig '1'"):
        slice_fasta_to_store(fasta_path, tmp_path / "store")


def test_slice_fasta_rejects_sequence_before_first_header(tmp_path: Path) -> None:
    fasta_path = tmp_path / "genome.fa"
    fasta_path.write_text("ACGT\n>1\nACGT\n", encoding="ascii")

    with pytest.raises(ValueError, match="sequence before first FASTA header"):
        slice_fasta_to_store(fasta_path, tmp_path / "store")


def test_slice_fasta_rejects_duplicate_contig_names_and_digests(tmp_path: Path) -> None:
    duplicate_name = tmp_path / "duplicate-name.fa"
    duplicate_name.write_text(">1\nACGT\n>1 other\nTGCA\n", encoding="ascii")
    with pytest.raises(ValueError, match="duplicate contig name '1'"):
        slice_fasta_to_store(duplicate_name, tmp_path / "name-store")

    duplicate_digest = tmp_path / "duplicate-digest.fa"
    duplicate_digest.write_text(">1\nACGT\n>2\nACGT\n", encoding="ascii")
    with pytest.raises(ValueError, match="duplicate refget digest"):
        slice_fasta_to_store(duplicate_digest, tmp_path / "digest-store")


class _FakeStream:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self) -> list[bytes]:
        return [self._payload[:5], self._payload[5:]]


def test_fetch_fasta_streams_and_decompresses_gzip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = gzip.compress(b">1\nACgt\n")
    calls: list[tuple[str, str]] = []

    def fake_stream(method: str, url: str, **kwargs: object) -> _FakeStream:
        calls.append((method, url))
        assert kwargs["follow_redirects"] is True
        return _FakeStream(payload)

    monkeypatch.setattr(httpx, "stream", fake_stream)

    dest = fetch_fasta("https://example.test/genome.fa.gz", tmp_path / "genome.fa")

    assert dest == tmp_path / "genome.fa"
    assert dest.read_bytes() == b">1\nACgt\n"
    assert calls == [("GET", "https://example.test/genome.fa.gz")]


def test_fetch_fasta_decompresses_concatenated_gzip_members(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = gzip.compress(b">1\nACgt\n") + gzip.compress(b">2\nTTaa\n")

    def fake_stream(method: str, url: str, **kwargs: object) -> _FakeStream:
        assert method == "GET"
        assert url == "https://example.test/genome.fa.gz"
        assert kwargs["follow_redirects"] is True
        return _FakeStream(payload)

    monkeypatch.setattr(httpx, "stream", fake_stream)

    dest = fetch_fasta("https://example.test/genome.fa.gz", tmp_path / "genome.fa")

    assert dest.read_bytes() == b">1\nACgt\n>2\nTTaa\n"
