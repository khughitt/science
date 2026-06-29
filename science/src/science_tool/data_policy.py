"""The data-policy SSOT: classify a project file as a tracked RECORD, an ignored
PAYLOAD, or a FLAG (ambiguous — surfaced for an explicit human decision).

This is the single place the COMMIT-vs-KEEP-IGNORED rule is expressed; the audit
(and any future size-guard hook) consume `classify`. Pure and deterministic: no
filesystem mutation, no git calls. See docs/plans/2026-06-28-data-audit-design.md.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class FileClass(StrEnum):
    RECORD = "record"    # lightweight, durable → belongs tracked
    PAYLOAD = "payload"  # large/regenerable → belongs ignored under data/
    FLAG = "flag"        # ambiguous → never auto-acted, surfaced for a decision


@dataclass(frozen=True)
class DataPolicy:
    record_patterns: tuple[str, ...]
    payload_extensions: tuple[str, ...]
    size_threshold: int


# Name/path-based record globs only — size is the classifier's job, never encoded
# into a pattern. A bare .csv/.json matching none of these falls to unknown-small
# → FLAG (the intended conservative behavior).
_DEFAULT_RECORD_PATTERNS: tuple[str, ...] = (
    "datapackage.json",
    "datapackage.yaml",
    "RESULTS*.md",
    "*-report.md",
    "*-report.json",
    "**/qa/*.json",
    "README.md",
    "RUBRIC.md",
    "validate_*.py",
    "*worksheet*.jsonl",
    "*verdict*",
    "*label*",
    "*-notes.md",
    "*majority*",
    "*.datapackage.json",  # dataset metadata sidecars
    "*interpretation*.md",
)

_DEFAULT_PAYLOAD_EXTENSIONS: tuple[str, ...] = (
    ".parquet", ".feather", ".pkl", ".pdf", ".npy", ".npz",
    ".tar", ".tar.gz", ".tgz", ".zip", ".mp4", ".mat",
)

DEFAULT_DATA_POLICY = DataPolicy(
    record_patterns=_DEFAULT_RECORD_PATTERNS,
    payload_extensions=_DEFAULT_PAYLOAD_EXTENSIONS,
    size_threshold=150_000,
)


def _matches_any(rel_path: Path, patterns: tuple[str, ...]) -> bool:
    posix = rel_path.as_posix()
    name = rel_path.name
    return any(
        fnmatch.fnmatch(posix, pat) or fnmatch.fnmatch(name, pat) for pat in patterns
    )


def classify(
    rel_path: Path, size_bytes: int, policy: DataPolicy = DEFAULT_DATA_POLICY
) -> FileClass:
    """Classify a repo-relative path + size. Conservative; first match wins."""
    name = rel_path.name.lower()
    if any(name.endswith(ext) for ext in policy.payload_extensions):
        return FileClass.PAYLOAD
    is_record = _matches_any(rel_path, policy.record_patterns)
    if is_record:
        return FileClass.RECORD if size_bytes <= policy.size_threshold else FileClass.FLAG
    if size_bytes > policy.size_threshold:
        return FileClass.PAYLOAD  # large unknown → safe to ignore
    return FileClass.FLAG          # small unknown → never auto-track
