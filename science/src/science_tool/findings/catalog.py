from __future__ import annotations

from pathlib import Path

from science_tool.findings.producers import (
    FindingProducer,
    FindingRegistry,
    build_registry,
)
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import registry_for_project


def registered_producers() -> tuple[FindingProducer, ...]:
    """Return the complete producer catalog without introducing import cycles."""
    from science_tool.data_audit import DATA_AUDIT_PRODUCER
    from science_tool.graph.health_checks import HEALTH_CHECKS
    from science_tool.graph.health_checks.schema_invalid import (
        SCHEMA_INVALID_PRODUCER,
    )
    from science_tool.validate.checks import CANONICAL_CHECKS
    from science_tool.validate.runtime import VALIDATION_RUNTIME_PRODUCER

    return (
        *(check.producer for check in HEALTH_CHECKS),
        SCHEMA_INVALID_PRODUCER,
        *(entry.producer for entry in CANONICAL_CHECKS),
        VALIDATION_RUNTIME_PRODUCER,
        DATA_AUDIT_PRODUCER,
    )


def build_registry_for_entity_registry(
    entity_registry: EntityRegistry,
) -> FindingRegistry:
    active = frozenset(entity_registry.registered_kinds())
    return build_registry(list(registered_producers()), active_kinds=active)


def build_project_registry(project_root: Path) -> FindingRegistry:
    return build_registry_for_entity_registry(registry_for_project(project_root))
