"""Hashing and versioning primitives shared across project-package profiles.

Zero app/entity coupling — these operate on files and byte streams only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileResource:
    path: str       # archive-relative posix path (no top-level project dir)
    sha256: str
    bytes: int


def file_resource(root: Path, relpath: str) -> FileResource:
    """Hash one file under ``root``; ``path`` is ``relpath`` verbatim."""
    data = (root / relpath).read_bytes()
    return FileResource(
        path=relpath,
        sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data),
    )


def content_version(base: str, chunks: Iterable[bytes]) -> str:
    """Deterministic version string ``f"{base}+{digest12}"``.

    Folds sha256 over ``chunks`` in order with NO separators or length
    prefixes, so existing call sites that build their own byte stream keep
    their digest byte-for-byte.
    """
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return f"{base}+{digest.hexdigest()[:12]}"
