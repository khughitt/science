"""Drift classification for installed managed artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from science_tool.project_artifacts.hashing import body_hash
from science_tool.project_artifacts.header import parse_header
from science_tool.project_artifacts.registry_schema import Artifact, Pin


class Status(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    LOCALLY_MODIFIED = "locally_modified"
    UNTRACKED = "untracked"
    MISSING = "missing"
    PINNED = "pinned"
    PINNED_BUT_LOCALLY_MODIFIED = "pinned_but_locally_modified"


@dataclass(frozen=True)
class ClassifyResult:
    status: Status
    detail: str = ""
    versions_behind: int | None = None  # populated for STALE


def classify(install_target: Path, artifact: Artifact, pins: list[Pin]) -> Status:
    """Convenience: return only the Status enum.

    Use `classify_full` to get versions_behind and detail.
    """
    return classify_full(install_target, artifact, pins).status


def classify_full(install_target: Path, artifact: Artifact, pins: list[Pin]) -> ClassifyResult:
    if not install_target.exists():
        return ClassifyResult(Status.MISSING)

    file_bytes = install_target.read_bytes()
    parsed = parse_header(file_bytes, artifact.header_protocol)
    body_h = body_hash(file_bytes, artifact.header_protocol)

    # Find any matching pin first; pins override stale/current classification.
    pin = next((p for p in pins if p.name == artifact.name), None)
    if pin is not None:
        if body_h == pin.pinned_hash:
            return ClassifyResult(Status.PINNED, detail=f"pinned to {pin.pinned_to}")
        return ClassifyResult(
            Status.PINNED_BUT_LOCALLY_MODIFIED,
            detail=f"installed bytes diverge from pin {pin.pinned_to}",
        )

    if parsed is None:
        return ClassifyResult(Status.UNTRACKED, detail="no managed header present")

    if body_h == artifact.current_hash:
        return ClassifyResult(Status.CURRENT)

    for idx, prev in enumerate(artifact.previous_hashes):
        if body_h == prev.hash:
            behind = len(artifact.previous_hashes) - idx
            return ClassifyResult(
                Status.STALE,
                detail=f"{behind} version(s) behind; last bumped {artifact.version}",
                versions_behind=behind,
            )

    return ClassifyResult(Status.LOCALLY_MODIFIED, detail="hash matches no known version")
