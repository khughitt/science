"""EntityRegistry — explicit kind → schema dispatch.

Per spec §Model Registry and Kind Resolution. Core kinds are registered by
Science; extension kinds are registered by the project. Duplicate
registrations are hard errors; extensions may not shadow core kinds.

Each registered kind also carries an `EntityClass` classification
(epistemic / operational / reference) used by the freshness engine to
decide which entities can be `bears_on` targets and which propagate
needs-review state.
"""

from __future__ import annotations

from science_model.entities import (
    DatasetEntity,
    Entity,
    EntityClass,
    MechanismEntity,
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


# Classification for every kind in with_core_types(). Adding a new kind there
# requires adding an entry here — the registration call asserts coverage.
_CORE_KIND_CLASSES: dict[str, EntityClass] = {
    # Typed entities
    "task": EntityClass.OPERATIONAL,
    "dataset": EntityClass.OPERATIONAL,
    "workflow-run": EntityClass.OPERATIONAL,
    "research-package": EntityClass.OPERATIONAL,
    "mechanism": EntityClass.EPISTEMIC,
    # Generic project kinds (alphabetized)
    "article": EntityClass.REFERENCE,
    "assumption": EntityClass.EPISTEMIC,
    "concept": EntityClass.REFERENCE,
    "curation-sweep": EntityClass.OPERATIONAL,
    "data-package": EntityClass.OPERATIONAL,
    "discussion": EntityClass.EPISTEMIC,
    "experiment": EntityClass.OPERATIONAL,
    "finding": EntityClass.EPISTEMIC,
    "hypothesis": EntityClass.EPISTEMIC,
    "inquiry": EntityClass.EPISTEMIC,
    "interpretation": EntityClass.EPISTEMIC,
    "method": EntityClass.OPERATIONAL,
    "observation": EntityClass.EPISTEMIC,
    "paper": EntityClass.OPERATIONAL,
    "plan": EntityClass.OPERATIONAL,
    "pre-registration": EntityClass.OPERATIONAL,
    "proposition": EntityClass.EPISTEMIC,
    "question": EntityClass.EPISTEMIC,
    "report": EntityClass.EPISTEMIC,
    "search": EntityClass.OPERATIONAL,
    "spec": EntityClass.OPERATIONAL,
    "story": EntityClass.EPISTEMIC,
    "topic": EntityClass.REFERENCE,
    "transformation": EntityClass.OPERATIONAL,
    "unknown": EntityClass.REFERENCE,
    "validation-report": EntityClass.EPISTEMIC,
    "variable": EntityClass.REFERENCE,
    "workflow": EntityClass.OPERATIONAL,
    "workflow-step": EntityClass.OPERATIONAL,
}


class EntityRegistry:
    """Resolves kind strings to their Entity subclass at load time."""

    def __init__(self) -> None:
        self._core: dict[str, type[Entity]] = {}
        self._profile: dict[str, type[Entity]] = {}
        self._catalog: dict[str, type[Entity]] = {}
        self._extensions: dict[str, type[Entity]] = {}
        self._kind_class: dict[str, EntityClass] = {}

    @classmethod
    def with_core_types(cls) -> "EntityRegistry":
        """Return a registry pre-populated with Science core kinds."""
        r = cls()
        # Typed entities
        r.register_core_kind("task", TaskEntity, entity_class=_CORE_KIND_CLASSES["task"])
        r.register_core_kind("dataset", DatasetEntity, entity_class=_CORE_KIND_CLASSES["dataset"])
        r.register_core_kind("workflow-run", WorkflowRunEntity, entity_class=_CORE_KIND_CLASSES["workflow-run"])
        r.register_core_kind(
            "research-package", ResearchPackageEntity, entity_class=_CORE_KIND_CLASSES["research-package"]
        )
        r.register_core_kind("mechanism", MechanismEntity, entity_class=_CORE_KIND_CLASSES["mechanism"])
        # Generic project kinds → ProjectEntity.
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
            "pre-registration",
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
            "spec",
            "curation-sweep",
        ):
            r.register_core_kind(kind, ProjectEntity, entity_class=_CORE_KIND_CLASSES[kind])
        return r

    def register_core_kind(self, kind: str, cls: type[Entity], *, entity_class: EntityClass) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core or kind in self._profile or kind in self._catalog or kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"kind {kind!r} already registered")
        self._core[kind] = cls
        self._kind_class[kind] = entity_class

    def register_profile_kind(
        self,
        kind: str,
        cls: type[Entity],
        *,
        owner: str,
        entity_class: EntityClass = EntityClass.OPERATIONAL,
    ) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core:
            raise EntityKindShadowError(f"profile kind {kind!r} shadows a core kind from {owner}")
        if kind in self._profile or kind in self._catalog or kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"profile kind {kind!r} already registered")
        self._profile[kind] = cls
        self._kind_class[kind] = entity_class

    def register_catalog_kind(
        self,
        kind: str,
        cls: type[Entity],
        *,
        owner: str,
        entity_class: EntityClass = EntityClass.REFERENCE,
    ) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core:
            return
        if kind in self._profile:
            raise EntityKindShadowError(f"catalog kind {kind!r} shadows an existing kind from {owner}")
        if kind in self._catalog:
            if self._catalog[kind] is cls:
                return
            raise EntityKindAlreadyRegisteredError(f"catalog kind {kind!r} already registered")
        if kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"catalog kind {kind!r} already registered")
        self._catalog[kind] = cls
        self._kind_class[kind] = entity_class

    def register_extension_kind(
        self,
        kind: str,
        cls: type[Entity],
        *,
        entity_class: EntityClass = EntityClass.OPERATIONAL,
    ) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core or kind in self._profile or kind in self._catalog:
            raise EntityKindShadowError(
                f"extension kind {kind!r} shadows a registered kind; use a project-specific prefix"
            )
        if kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"extension kind {kind!r} already registered")
        self._extensions[kind] = cls
        self._kind_class[kind] = entity_class

    def resolve(self, kind: str) -> type[Entity]:
        if kind in self._core:
            return self._core[kind]
        if kind in self._profile:
            return self._profile[kind]
        if kind in self._catalog:
            return self._catalog[kind]
        if kind in self._extensions:
            return self._extensions[kind]
        raise EntityKindNotRegisteredError(f"no schema registered for kind {kind!r}")

    def kind_class(self, kind: str) -> EntityClass:
        if kind not in self._kind_class:
            raise EntityKindNotRegisteredError(f"no classification registered for kind {kind!r}")
        return self._kind_class[kind]

    def all_kind_classes(self) -> dict[str, EntityClass]:
        return dict(self._kind_class)

    @staticmethod
    def _require_entity_subclass(candidate: object) -> None:
        if not (isinstance(candidate, type) and issubclass(candidate, Entity)):
            raise TypeError(f"registered class must subclass Entity, got {candidate!r}")
