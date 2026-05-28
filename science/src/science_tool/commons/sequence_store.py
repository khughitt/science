"""Content-addressed C4a per-contig sequence store reader.

Each contig is stored as one file named by its refget digest. A contig is
stream-verified on first use, its byte length is cached, and subsequent
sequence reads seek directly to the requested byte slice. This reader does not
fetch remote data and does not route contig reads through whole-file sha256
resource resolution.
"""

from __future__ import annotations

import base64
import hashlib
import string
from dataclasses import dataclass, field
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024
_REFGET_PREFIX = "SQ."
_REFGET_SUFFIX_LENGTH = 32
_REFGET_SUFFIX_CHARS = frozenset(string.ascii_letters + string.digits + "_-")


class SequenceStoreError(LookupError):
    """The sequence store cannot provide the requested contig or slice."""


def _sha512t24u(data: bytes) -> str:
    digest = hashlib.sha512(data).digest()[:24]
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def refget_digest(seq: str) -> str:
    """Return the GA4GH refget digest over the exact ASCII sequence bytes."""

    return _REFGET_PREFIX + _sha512t24u(seq.encode("ascii"))


def _validate_refget_digest(digest: str) -> None:
    suffix = digest.removeprefix(_REFGET_PREFIX)
    if (
        suffix == digest
        or len(suffix) != _REFGET_SUFFIX_LENGTH
        or any(char not in _REFGET_SUFFIX_CHARS for char in suffix)
    ):
        raise SequenceStoreError(f"invalid refget digest {digest!r}")


@dataclass
class SequenceStore:
    root: Path
    _lengths: dict[str, int] = field(default_factory=dict)

    def _path(self, digest: str) -> Path:
        _validate_refget_digest(digest)
        return self.root / digest

    def _verify(self, digest: str) -> int:
        path = self._path(digest)
        if not path.is_file():
            raise SequenceStoreError(f"contig {digest!r} not in sequence store at {self.root}")

        hasher = hashlib.sha512()
        length = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
                hasher.update(chunk)
                length += len(chunk)

        actual = _REFGET_PREFIX + base64.urlsafe_b64encode(hasher.digest()[:24]).decode("ascii").rstrip("=")
        if actual != digest:
            raise SequenceStoreError(f"refget digest mismatch for {path}: expected {digest}, got {actual}")

        self._lengths[digest] = length
        return length

    def length(self, digest: str) -> int:
        if digest not in self._lengths:
            return self._verify(digest)
        return self._lengths[digest]

    def sequence(self, digest: str, start: int | None = None, end: int | None = None) -> str:
        length = self.length(digest)
        slice_start = 0 if start is None else start
        slice_end = length if end is None else end

        if slice_start < 0 or slice_end < slice_start or slice_end > length:
            raise SequenceStoreError(
                f"invalid sequence slice for {digest}: start={slice_start}, end={slice_end}, length={length}"
            )

        path = self._path(digest)
        expected_length = slice_end - slice_start
        try:
            with path.open("rb") as handle:
                handle.seek(slice_start)
                data = handle.read(expected_length)
        except FileNotFoundError as error:
            raise SequenceStoreError(f"contig {digest!r} not in sequence store at {self.root}") from error

        if len(data) != expected_length:
            raise SequenceStoreError(
                f"short read for {digest}: requested {expected_length} bytes at offset {slice_start}, got {len(data)}"
            )

        return data.decode("ascii")


def open_store(root: Path) -> SequenceStore:
    return SequenceStore(root=Path(root))
