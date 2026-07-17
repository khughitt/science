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
    BookEntity,
    ChainAuditEntity,
    CodeFileEntity,
    DatasetEntity,
    Entity,
    EvidenceLineEntity,
    FalsificationEntity,
    HypothesisEntity,
    InquiryEntity,
    MechanismEntity,
    MethodEntity,
    PaperEntity,
    ProjectEntity,
    ResearchPackageEntity,
    StructuralChainEntity,
    TalkEntity,
    TaskEntity,
    ThemeEntity,
    WorkflowRunEntity,
    WorkflowStepEntity,
)
from science_model.identity import CurationScope, EntityClass
from science_model.patch_definition import PatchDefinitionEntity
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.schema import KindCategory
from science_model.propositions import PropositionEntity


class EntityKindAlreadyRegisteredError(ValueError):
    """Raised when a kind is registered twice."""


class EntityKindShadowError(ValueError):
    """Raised when an extension tries to register a core kind."""


class EntityKindNotRegisteredError(KeyError):
    """Raised when resolve() is called with an unregistered kind."""


# The only per-kind fact that cannot be data: the bound Pydantic class. Kinds
# absent here default to ProjectEntity at registration (design §2.4). Consumed by
# with_core_types() once the registry flip lands (Task 6).
CORE_KIND_MODELS: dict[str, type[Entity]] = {
    "task": TaskEntity,
    "dataset": DatasetEntity,
    "workflow-run": WorkflowRunEntity,
    "workflow-step": WorkflowStepEntity,
    "method": MethodEntity,
    "research-package": ResearchPackageEntity,
    "mechanism": MechanismEntity,
    "theme": ThemeEntity,
    "book": BookEntity,
    "paper": PaperEntity,
    "talk": TalkEntity,
    "structural-chain": StructuralChainEntity,
    "chain-audit": ChainAuditEntity,
    "code-file": CodeFileEntity,
    "evidence-line": EvidenceLineEntity,
    "falsification": FalsificationEntity,
    "hypothesis": HypothesisEntity,
    "inquiry": InquiryEntity,
    "proposition": PropositionEntity,
    "patch-definition": PatchDefinitionEntity,
}


class EntityRegistry:
    """Resolves kind strings to their Entity subclass at load time."""

    def __init__(self) -> None:
        self._core: dict[str, type[Entity]] = {}
        self._profile: dict[str, type[Entity]] = {}
        self._catalog: dict[str, type[Entity]] = {}
        self._extensions: dict[str, type[Entity]] = {}
        self._kind_class: dict[str, EntityClass] = {}
        self._curation_scope_declared: dict[str, CurationScope | None] = {}

    @classmethod
    def with_core_types(cls) -> "EntityRegistry":
        """Return a registry pre-populated with Science core kinds, read from the
        descriptor SSOT (CORE_PROFILE). Model class comes from CORE_KIND_MODELS;
        kinds without a typed subclass default to ProjectEntity."""
        r = cls()
        for ek in CORE_PROFILE.entity_kinds:
            if ek.category not in (KindCategory.AUTHORED_CORE, KindCategory.RESERVED):
                continue
            if ek.entity_class is None:
                raise ValueError(f"core kind {ek.name!r} has no entity_class in CORE_PROFILE")
            r.register_core_kind(
                ek.name,
                CORE_KIND_MODELS.get(ek.name, ProjectEntity),
                entity_class=ek.entity_class,
                curation_scope=ek.curation_scope,
            )
        return r

    def register_core_kind(
        self,
        kind: str,
        cls: type[Entity],
        *,
        entity_class: EntityClass,
        curation_scope: CurationScope | None = None,
    ) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core or kind in self._profile or kind in self._catalog or kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"kind {kind!r} already registered")
        self._core[kind] = cls
        self._kind_class[kind] = entity_class
        self._curation_scope_declared[kind] = curation_scope

    def register_profile_kind(
        self,
        kind: str,
        cls: type[Entity],
        *,
        owner: str,
        entity_class: EntityClass = EntityClass.OPERATIONAL,
        curation_scope: CurationScope | None = None,
    ) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core:
            raise EntityKindShadowError(f"profile kind {kind!r} shadows a core kind from {owner}")
        if kind in self._profile or kind in self._catalog or kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"profile kind {kind!r} already registered")
        self._profile[kind] = cls
        self._kind_class[kind] = entity_class
        self._curation_scope_declared[kind] = curation_scope

    def register_catalog_kind(
        self,
        kind: str,
        cls: type[Entity],
        *,
        owner: str,
        entity_class: EntityClass = EntityClass.REFERENCE,
        curation_scope: CurationScope | None = None,
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
        self._curation_scope_declared[kind] = curation_scope

    def register_extension_kind(
        self,
        kind: str,
        cls: type[Entity],
        *,
        entity_class: EntityClass = EntityClass.OPERATIONAL,
        curation_scope: CurationScope | None = None,
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
        self._curation_scope_declared[kind] = curation_scope

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

    def is_core_kind(self, kind: str) -> bool:
        return kind in self._core

    def core_kinds(self) -> frozenset[str]:
        """Names of the registered core kinds (for reconciliation tests)."""
        return frozenset(self._core)

    def kind_class(self, kind: str) -> EntityClass:
        if kind not in self._kind_class:
            raise EntityKindNotRegisteredError(f"no classification registered for kind {kind!r}")
        return self._kind_class[kind]

    def curation_scope_for_kind(self, kind: str) -> CurationScope:
        """Resolve a kind's curation scope — the SINGLE decider (design §6.1).

        Declared value wins. Otherwise the default is polarity-split by registration
        bucket (design §6.2): core/profile/catalog kinds default to `none` (a newly
        registered core kind is out of scope until declared); extension kinds and
        wholly-unregistered kinds default to `correspondence`, preserving today's
        reviewable-by-default behaviour for exactly the population that has it
        (project-local extension kinds such as multiple-myeloma's `design`).
        """
        declared = self._curation_scope_declared.get(kind)
        if declared is not None:
            return declared
        if kind in self._core or kind in self._profile or kind in self._catalog:
            return CurationScope.NONE
        return CurationScope.CORRESPONDENCE

    def all_kind_classes(self) -> dict[str, EntityClass]:
        return dict(self._kind_class)

    def registered_kinds(self) -> dict[str, type[Entity]]:
        """All registered kind -> bound model, deterministic by kind name.

        Merges core, profile, catalog, and extension registrations. Used to map a
        reference field back to the kinds that declare it (graph audit's
        undeclared_key diagnostic).
        """
        merged = {**self._core, **self._profile, **self._catalog, **self._extensions}
        return dict(sorted(merged.items()))

    @staticmethod
    def _require_entity_subclass(candidate: object) -> None:
        if not (isinstance(candidate, type) and issubclass(candidate, Entity)):
            raise TypeError(f"registered class must subclass Entity, got {candidate!r}")
