"""Payload inventory walk for project package serialization."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


class PayloadError(Exception):
    """Raised for hard-fail payload inventory guard failures."""


def payload_inventory(
    project_root: Path,
    data_dirs: tuple[Path, ...],
    tracked_set: set[str],
) -> list[dict]:
    payloads: list[dict] = []
    seen_dirs: set[str] = set()
    for d in data_dirs:
        base = project_root / d
        if not base.exists():
            continue
        _walk_payload_dir(project_root, base, tracked_set, seen_dirs, payloads)
    payloads.sort(key=lambda p: p["path"])
    return payloads


def _walk_payload_dir(
    project_root: Path,
    directory: Path,
    tracked_set: set[str],
    seen_dirs: set[str],
    payloads: list[dict],
) -> None:
    real = os.path.realpath(directory)
    if real in seen_dirs:
        raise PayloadError(f"symlink cycle under data dir: {directory}")
    seen_dirs.add(real)
    for entry in sorted(os.scandir(directory), key=lambda e: e.name):
        path = Path(entry.path)
        if entry.is_dir(follow_symlinks=True):
            _walk_payload_dir(project_root, path, tracked_set, seen_dirs, payloads)
        elif entry.is_file(follow_symlinks=True):
            data = path.read_bytes()  # follows symlink to hydrated content
            rel = path.relative_to(project_root).as_posix()
            payloads.append({
                "path": rel,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "git_tracked": rel in tracked_set,
            })
        else:
            raise PayloadError(f"non-regular file under data dir: {entry.path}")
