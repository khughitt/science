"""Payload inventory walk for project package serialization."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from science_tool.data_root import logical_data_dir_to_physical


class PayloadError(Exception):
    """Raised for hard-fail payload inventory guard failures."""


def payload_inventory(
    project_root: Path,
    data_dirs: tuple[Path, ...],
    tracked_set: set[str],
    data_root: Path | None = None,
) -> list[dict]:
    physical_root = data_root or project_root / "data"
    payloads: list[dict] = []
    seen_dirs: set[str] = set()
    for logical_dir in data_dirs:
        base = logical_data_dir_to_physical(physical_root, logical_dir)
        if not base.exists():
            continue
        _walk_payload_dir(logical_dir, base, base, tracked_set, seen_dirs, payloads)
    payloads.sort(key=lambda p: p["path"])
    return payloads


def _walk_payload_dir(
    logical_dir: Path,
    physical_base: Path,
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
            _walk_payload_dir(
                logical_dir, physical_base, path, tracked_set, seen_dirs, payloads
            )
        elif entry.is_file(follow_symlinks=True):
            data = path.read_bytes()  # follows symlink to hydrated content
            logical_path = (logical_dir / path.relative_to(physical_base)).as_posix()
            payloads.append(
                {
                    "path": logical_path,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                    "git_tracked": logical_path in tracked_set,
                }
            )
        else:
            raise PayloadError(f"non-regular file under data dir: {entry.path}")
