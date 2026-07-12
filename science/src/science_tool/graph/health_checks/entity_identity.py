"""Entity-identity health check: canonical entity identifiers, baseline status, and prose references."""

from __future__ import annotations

from typing import TypedDict

from science_model.contracts.inventory_common import InventoryWarning

from science_tool.entity_identity import collect_identity_warnings
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, context_sources


class EntityIdentityFinding(TypedDict):
    code: str
    severity: str
    message: str
    path: str | None
    canonical_id: str | None


def _entity_identity_finding(warning: InventoryWarning) -> EntityIdentityFinding:
    return {
        "code": warning.code,
        "severity": warning.severity,
        "message": warning.message,
        "path": warning.path,
        "canonical_id": warning.canonical_id,
    }


def _collect_entity_identity(context: HealthContext) -> list[EntityIdentityFinding]:
    sources = context_sources(context)
    return [
        _entity_identity_finding(warning)
        for warning in collect_identity_warnings(context.project_root, sources=sources)
    ]


CHECK = HealthCheck(
    name="entity_identity",
    description="Validate canonical entity identifiers, baseline status, and prose references.",
    requires_sources=True,
    run=_collect_entity_identity,
    empty=lambda _root: [],
)
