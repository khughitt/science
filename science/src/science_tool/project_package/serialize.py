"""`science project serialize` — deterministic, git-faithful project bundle.

Source files (entities + results, no data/ payloads) + a manifest that
hash-inventories the excluded payloads. See
docs/plans/2026-06-29-project-serialize-design.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from science_tool.data_worktree import DEFAULT_DATA_DIRS
from science_tool.project_config import load_project_config
from science_tool.project_package.core import FileResource, content_version, file_resource

SCHEMA_VERSION = "science-project-serialized.v1"
SOURCE_ROOTS = ("entities", "results")
TOP_LEVEL_SINGLES = ("science.yaml", "papers/references.bib", "knowledge/graph.trig")


class SerializeError(Exception):
    """Raised for any hard-fail precondition or guard failure."""


@dataclass(frozen=True)
class SerializeResult:
    out_path: Path
    file_count: int
    payload_count: int
    forced: bool


def _tracked_files(project_root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SerializeError(
            f"not a git worktree (git ls-files failed): {project_root}"
        ) from exc
    return [p for p in out.decode("utf-8").split("\0") if p]


def _selected_source(tracked: list[str]) -> list[str]:
    selected: set[str] = set()
    for rel in tracked:
        if rel in TOP_LEVEL_SINGLES or rel.split("/", 1)[0] in SOURCE_ROOTS:
            selected.add(rel)
    return sorted(selected)


def _payload_inventory(
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
        raise SerializeError(f"symlink cycle under data dir: {directory}")
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
            raise SerializeError(f"non-regular file under data dir: {entry.path}")


def _build_manifest(
    project_root: Path,
    files: list[FileResource],
    payloads: list[dict],
    *,
    audit_passed: bool,
    forced: bool,
    git_commit: str,
) -> dict:
    config = load_project_config(project_root)
    raw = yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8")) or {}
    base = str(raw.get("last_modified") or raw.get("version") or "0")

    chunks: list[bytes] = []
    for fr in files:
        chunks.append(json.dumps(
            {"path": fr.path, "sha256": fr.sha256, "bytes": fr.bytes}, sort_keys=True
        ).encode("utf-8"))
    for p in payloads:
        chunks.append(json.dumps(
            {"path": p["path"], "sha256": p["sha256"], "bytes": p["bytes"],
             "git_tracked": p["git_tracked"]},
            sort_keys=True,
        ).encode("utf-8"))

    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "id": config.id,
            "label": str(raw.get("name") or config.id),
            "summary": raw.get("summary"),
        },
        "data_version": content_version(base, chunks),
        "provenance": {"git_commit": git_commit, "tool": "science"},
        "boundary_audit": {"passed": audit_passed, "forced": forced},
        "files": [{"path": fr.path, "sha256": fr.sha256, "bytes": fr.bytes} for fr in files],
        "payloads": payloads,
    }
