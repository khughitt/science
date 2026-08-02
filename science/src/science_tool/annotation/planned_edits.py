"""The shared plan-then-apply edit vocabulary.

Reconciliation grew this vocabulary first, and resynthesis reached across a module
boundary for six of its private names. This module owns them so no generic helper
stays owned by one workflow.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlannedFileEdit:
    path: Path
    reason: str
    before_sha256: str
    after_sha256: str
    final_text: str
    changed: bool


def path_string(path: Path) -> str:
    return path.as_posix()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def current_text(path: Path) -> str:
    """Read a planning pre-image WITHOUT universal-newline translation.

    `Path.read_text()` normalizes CRLF to LF before planning ever runs, so a CRLF body
    would be silently rewritten by an edit that never touched it -- and the round-trip
    guard would certify that rewrite as correct. `entities.py`'s preserving parser reads
    the same way.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def plan_update(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    before = current_text(path)
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=sha256_text(before),
        after_sha256=sha256_text(final_text),
        final_text=final_text,
        changed=before != final_text,
    )


def changed_and_noop_paths(
    edits: Sequence[PlannedFileEdit],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    changed = tuple(path_string(edit.path) for edit in edits if edit.changed)
    noop = tuple(path_string(edit.path) for edit in edits if not edit.changed)
    return changed, noop
