"""Health checks, one module per check.

`HEALTH_CHECKS` is assembled by explicit import below — never by filesystem
discovery, which would make check order implicit. The tuple's order is the
execution order and the order of `_meta.timings`; changing it is observable.
"""

from __future__ import annotations

from science_tool.graph.health_checks import (
    agent_context,
    archive_lag,
    cross_paper_evidence,
    dataset_anomalies,
    entity_identity,
    identity_policy,
    invalid_entity_aspects,
    layered_claim_migration,
    legacy_task_type,
    lingering_tags,
    managed_artifacts,
    prose_epistemics,
    tooling_scaffold,
    unregistered_ref_kinds,
    unresolved_refs,
    validate,
)
from science_tool.graph.health_checks.base import (
    HealthCheck,
    HealthContext,
    HealthTiming,
    context_sources,
)

HEALTH_CHECKS: tuple[HealthCheck, ...] = (
    identity_policy.CHECK,
    entity_identity.CHECK,
    layered_claim_migration.CHECK,
    cross_paper_evidence.CHECK,
    archive_lag.CHECK,
    managed_artifacts.CHECK,
    tooling_scaffold.CHECK,
    validate.CHECK,
    prose_epistemics.CHECK,
    agent_context.CHECK,
    unresolved_refs.CHECK,
    unregistered_ref_kinds.CHECK,
    lingering_tags.CHECK,
    dataset_anomalies.CHECK,
    legacy_task_type.CHECK,
    invalid_entity_aspects.CHECK,
)

__all__ = [
    "HEALTH_CHECKS",
    "HealthCheck",
    "HealthContext",
    "HealthTiming",
    "context_sources",
]
