"""Layered-claim-migration health check: layered-claim adoption gaps and migration issues."""

from __future__ import annotations

from pathlib import Path

from science_tool.graph.health_checks.base import HealthCheck, context_sources
from science_tool.graph.migrate import (
    LayeredClaimMigrationReport,
    build_layered_claim_migration_report,
)


def _empty_layered_claim_migration_report(project_root: Path) -> LayeredClaimMigrationReport:
    return {
        "project_root": str(project_root),
        "rows": [],
        "summary": {
            "proposition_count": 0,
            "authored_claim_layer_count": 0,
            "authored_identification_strength_count": 0,
            "warning_count": 0,
            "todo_count": 0,
        },
    }


CHECK = HealthCheck(
    name="layered_claim_migration",
    description="Report layered-claim adoption gaps and migration issues.",
    requires_sources=True,
    run=lambda context: build_layered_claim_migration_report(
        context.project_root, sources=context_sources(context)
    ),
    empty=_empty_layered_claim_migration_report,
)
