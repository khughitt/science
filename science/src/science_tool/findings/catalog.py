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
    """Plan 2's atomic cutover replaces the empty tuple with all three namespaces."""
    return ()


def build_registry_for_entity_registry(
    entity_registry: EntityRegistry,
) -> FindingRegistry:
    active = frozenset(entity_registry.registered_kinds())
    return build_registry(list(registered_producers()), active_kinds=active)


def build_project_registry(project_root: Path) -> FindingRegistry:
    return build_registry_for_entity_registry(registry_for_project(project_root))
