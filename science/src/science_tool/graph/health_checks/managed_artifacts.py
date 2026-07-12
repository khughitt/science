"""Managed-artifacts health check: installed managed artifacts vs. canonical versions."""

from __future__ import annotations

from typing import cast

from science_tool.graph.health_checks.base import HealthCheck, HealthContext


def _collect_managed_artifacts(context: HealthContext) -> list[dict]:
    from science_tool.project_artifacts.health_integration import health_findings

    return cast("list[dict]", health_findings(context.project_root))


CHECK = HealthCheck(
    name="managed_artifacts",
    description="Check installed managed artifacts against canonical versions.",
    requires_sources=False,
    run=_collect_managed_artifacts,
    empty=lambda _root: [],
)
