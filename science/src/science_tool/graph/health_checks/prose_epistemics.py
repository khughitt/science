"""Prose-epistemics health check: reads the project-level prose epistemics artifact."""

from __future__ import annotations

from science_tool.graph.health_checks.base import HealthCheck, HealthContext


def _empty_prose_epistemics() -> dict[str, object]:
    return {
        "applicable": False,
        "summary": {},
        "coverage": {},
        "sources": [],
        "findings": [],
    }


def _collect_prose_epistemics(context: HealthContext) -> dict[str, object]:
    from science_tool.annotation.prose_health import (
        ProseHealthError,
        load_prose_health_artifact,
        load_prose_health_manifest,
        prose_health_manifest_path,
        prose_health_path,
    )

    manifest_path = prose_health_manifest_path(context.project_root)
    artifact_path = prose_health_path(context.project_root)
    if not manifest_path.exists() and not artifact_path.exists():
        return _empty_prose_epistemics()
    if manifest_path.exists():
        try:
            load_prose_health_manifest(context.project_root)
        except ProseHealthError as exc:
            return {
                "applicable": True,
                "summary": {},
                "coverage": {},
                "sources": [],
                "findings": [
                    {
                        "code": "manifest_invalid",
                        "severity": "error",
                        "counts_as_issue": True,
                        "source_ref": None,
                        "path": manifest_path.relative_to(context.project_root).as_posix(),
                        "message": str(exc),
                    }
                ],
            }
    if not artifact_path.exists():
        return {
            "applicable": True,
            "summary": {},
            "coverage": {},
            "sources": [],
            "findings": [
                {
                    "code": "prose_health_artifact_missing",
                    "severity": "warning",
                    "counts_as_issue": True,
                    "source_ref": None,
                    "path": artifact_path.relative_to(context.project_root).as_posix(),
                    "message": (
                        "Prose health manifest exists but prose-health.json is missing; "
                        "run science annotate build-prose-health --write."
                    ),
                }
            ],
        }
    try:
        artifact = load_prose_health_artifact(context.project_root)
    except ProseHealthError as exc:
        return {
            "applicable": True,
            "summary": {},
            "coverage": {},
            "sources": [],
            "findings": [
                {
                    "code": "prose_health_artifact_invalid",
                    "severity": "error",
                    "counts_as_issue": True,
                    "source_ref": None,
                    "path": artifact_path.relative_to(context.project_root).as_posix(),
                    "message": str(exc),
                }
            ],
        }
    return {
        "applicable": True,
        "summary": artifact.get("summary", {}),
        "coverage": artifact.get("coverage", {}),
        "sources": artifact.get("sources", []),
        "findings": artifact.get("findings", []),
    }


CHECK = HealthCheck(
    name="prose_epistemics",
    description="Read the project-level prose epistemics health artifact.",
    requires_sources=False,
    run=_collect_prose_epistemics,
    empty=lambda _root: _empty_prose_epistemics(),
)
