"""Health-report integration: collect managed-artifact findings."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from science_tool.project_artifacts import default_registry
from science_tool.project_artifacts.pin import read_pins
from science_tool.project_artifacts.status import Status, classify_full


class ManagedArtifactFinding(TypedDict):
    name: str
    install_target: str
    version: str
    status: str
    detail: str
    counts_as_issue: bool


_ISSUE_STATUSES = {
    Status.STALE.value,
    Status.LOCALLY_MODIFIED.value,
    Status.MISSING.value,
    Status.PINNED_BUT_LOCALLY_MODIFIED.value,
}


def health_findings(project_root: Path) -> list[ManagedArtifactFinding]:
    """One finding per registered managed artifact."""
    registry = default_registry()
    pins = []
    if (project_root / "science.yaml").exists():
        try:
            pins = read_pins(project_root)
        except Exception:  # malformed science.yaml is a separate concern
            pins = []

    out: list[ManagedArtifactFinding] = []
    for art in registry.artifacts:
        target = project_root / art.install_target
        result = classify_full(target, art, pins)
        out.append(
            ManagedArtifactFinding(
                name=art.name,
                install_target=art.install_target,
                version=art.version,
                status=result.status.value,
                detail=result.detail,
                counts_as_issue=result.status.value in _ISSUE_STATUSES,
            )
        )
    return out
