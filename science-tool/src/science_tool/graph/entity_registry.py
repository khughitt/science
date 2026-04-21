"""EntityRegistry — explicit kind → schema dispatch.

Per spec §Model Registry and Kind Resolution. Core kinds are registered by
Science; extension kinds are registered by the project. Duplicate
registrations are hard errors; extensions may not shadow core kinds.
"""

from __future__ import annotations

from science_model.entities import (
    DatasetEntity,
    Entity,
    ProjectEntity,
    ResearchPackageEntity,
    TaskEntity,
    WorkflowRunEntity,
)


class EntityKindAlreadyRegisteredError(ValueError):
    """Raised when a kind is registered twice."""


class EntityKindShadowError(ValueError):
    """Raised when an extension tries to register a core kind."""


class EntityKindNotRegisteredError(KeyError):
    """Raised when resolve() is called with an unregistered kind."""


class EntityRegistry:
    """Resolves kind strings to their Entity subclass at load time."""

    def __init__(self) -> None:
        self._core: dict[str, type[Entity]] = {}
        self._extensions: dict[str, type[Entity]] = {}

    @classmethod
    def with_core_types(cls) -> "EntityRegistry":
        """Return a registry pre-populated with Science core kinds."""
        r = cls()
        # Typed entities
        r.register_core_kind("task", TaskEntity)
        r.register_core_kind("dataset", DatasetEntity)
        r.register_core_kind("workflow-run", WorkflowRunEntity)
        r.register_core_kind("research-package", ResearchPackageEntity)
        # Generic project kinds that have no typed invariants yet → route to ProjectEntity.
        # Spec §Implication for current model/parameter says these are NOT core typed
        # entities, but we still route them through ProjectEntity during this migration
        # so the kitchen-sink snapshot and existing projects keep working. Task 12
        # removes "model" and "parameter" from this list and makes them extension-only.
        for kind in (
            "concept",
            "hypothesis",
            "question",
            "proposition",
            "observation",
            "inquiry",
            "topic",
            "interpretation",
            "discussion",
            "plan",
            "assumption",
            "transformation",
            "variable",
            "method",
            "experiment",
            "article",
            "workflow",
            "workflow-step",
            "data-package",
            "finding",
            "story",
            "paper",
            "search",
            "report",
            "validation-report",
            "unknown",
            "model",
            "parameter",
            "spec",
        ):
            r.register_core_kind(kind, ProjectEntity)
        return r

    def register_core_kind(self, kind: str, cls: type[Entity]) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core or kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"kind {kind!r} already registered")
        self._core[kind] = cls

    def register_extension_kind(self, kind: str, cls: type[Entity]) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core:
            raise EntityKindShadowError(f"extension kind {kind!r} shadows a core kind; use a project-specific prefix")
        if kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"extension kind {kind!r} already registered")
        self._extensions[kind] = cls

    def resolve(self, kind: str) -> type[Entity]:
        if kind in self._core:
            return self._core[kind]
        if kind in self._extensions:
            return self._extensions[kind]
        raise EntityKindNotRegisteredError(f"no schema registered for kind {kind!r}")

    @staticmethod
    def _require_entity_subclass(candidate: object) -> None:
        if not (isinstance(candidate, type) and issubclass(candidate, Entity)):
            raise TypeError(f"registered class must subclass Entity, got {candidate!r}")
