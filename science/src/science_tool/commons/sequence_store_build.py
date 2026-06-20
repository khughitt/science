"""Build helpers for content-addressed per-contig sequence stores.

Operator-run only: FASTA bytes are materialized locally and not committed.
Each FASTA record is written to ``out_dir/<refget_digest>`` with a manifest row
that commits the contig name, refget digest, length, and sha256 of the exact
sequence bytes stored.
"""

from __future__ import annotations

import hashlib
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Iterator, cast

from science_tool.commons.sequence_store import refget_digest


@dataclass
class _OpenRecord:
    name: str
    path: Path
    handle: BinaryIO
    sha256: Any
    length: int = 0


def _decode_ascii(data: bytes, *, fasta_path: Path, line_no: int) -> str:
    try:
        return data.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError(f"non-ASCII FASTA content in {fasta_path} at line {line_no}") from error


def _record_name(header_line: bytes, *, fasta_path: Path, line_no: int) -> str:
    header = _decode_ascii(header_line[1:].strip(), fasta_path=fasta_path, line_no=line_no)
    parts = header.split(maxsplit=1)
    if not parts:
        raise ValueError(f"empty FASTA header in {fasta_path} at line {line_no}")
    return parts[0]


def _start_record(name: str, out_dir: Path) -> _OpenRecord:
    tmp = tempfile.NamedTemporaryFile("wb", dir=out_dir, prefix=".seqstore-", delete=False)
    return _OpenRecord(name=name, path=Path(tmp.name), handle=cast(BinaryIO, tmp), sha256=hashlib.sha256())


def _finish_record(
    record: _OpenRecord,
    *,
    fasta_path: Path,
    out_dir: Path,
    seen_digests: set[str],
) -> dict[str, Any]:
    record.handle.close()
    if record.length == 0:
        record.path.unlink(missing_ok=True)
        raise ValueError(f"empty contig {record.name!r} in {fasta_path}")

    seq = record.path.read_text(encoding="ascii")
    digest = refget_digest(seq)
    if digest in seen_digests:
        record.path.unlink(missing_ok=True)
        raise ValueError(f"duplicate refget digest {digest!r} in {fasta_path}")

    target = out_dir / digest
    record.path.replace(target)
    seen_digests.add(digest)
    return {
        "name": record.name,
        "refget_digest": digest,
        "length": record.length,
        "sha256": record.sha256.hexdigest(),
    }


def slice_fasta_to_store(fasta_path: Path, out_dir: Path) -> list[dict[str, Any]]:
    """Slice ``fasta_path`` into ``out_dir/<refget_digest>`` and return manifest rows."""

    fasta_path = Path(fasta_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    seen_digests: set[str] = set()
    current: _OpenRecord | None = None

    with fasta_path.open("rb") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip(b"\r\n")
            if line.startswith(b">"):
                if current is not None:
                    manifest.append(
                        _finish_record(
                            current,
                            fasta_path=fasta_path,
                            out_dir=out_dir,
                            seen_digests=seen_digests,
                        )
                    )
                name = _record_name(line, fasta_path=fasta_path, line_no=line_no)
                if name in seen_names:
                    raise ValueError(f"duplicate contig name {name!r} in {fasta_path}")
                seen_names.add(name)
                current = _start_record(name, out_dir)
                continue

            if line == b"":
                continue
            if current is None:
                raise ValueError(f"sequence before first FASTA header in {fasta_path} at line {line_no}")
            _decode_ascii(line, fasta_path=fasta_path, line_no=line_no)
            current.handle.write(line)
            current.sha256.update(line)
            current.length += len(line)

    if current is None:
        raise ValueError(f"no FASTA records in {fasta_path}")
    manifest.append(_finish_record(current, fasta_path=fasta_path, out_dir=out_dir, seen_digests=seen_digests))
    return manifest


def _decompress_gzip_members(chunks: Iterable[bytes]) -> Iterator[bytes]:
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    for chunk in chunks:
        data = chunk
        while data:
            decompressed = inflater.decompress(data)
            if decompressed:
                yield decompressed
            if not inflater.eof:
                break
            data = inflater.unused_data
            inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        if not data and inflater.eof:
            inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    tail = inflater.flush()
    if tail:
        yield tail


def fetch_fasta(url: str, dest: Path) -> Path:
    """Stream a remote FASTA to ``dest``, decompressing ``.gz`` inputs to plain FASTA."""

    import httpx

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    decompress = url.endswith(".gz")

    with httpx.stream("GET", url, timeout=300.0, follow_redirects=True) as response:
        response.raise_for_status()
        with dest.open("wb") as out:
            chunks = _decompress_gzip_members(response.iter_bytes()) if decompress else response.iter_bytes()
            for chunk in chunks:
                if not chunk:
                    continue
                out.write(chunk)
    return dest
