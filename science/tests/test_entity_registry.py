"""Tests for EntityRegistry — kind → schema dispatch per spec §Model Registry."""

from __future__ import annotations

from pathlib import Path

import pytest
from science_model.entities import (
    DatasetEntity,
    DomainEntity,
    Entity,
    EvidenceLineEntity,
    MechanismEntity,
    PaperEntity,
    ProjectEntity,
    TaskEntity,
)
from science_model.identity import CurationScope, EntityClass

from science_tool.graph.entity_registry import (
    EntityKindAlreadyRegisteredError,
    EntityKindNotRegisteredError,
    EntityKindShadowError,
    EntityRegistry,
)

_EPISTEMIC = {
    "assumption",
    "chain-audit",
    "discussion",
    "evidence-line",
    "falsification",
    "finding",
    "hypothesis",
    "inquiry",
    "interpretation",
    "mechanism",
    "observation",
    "patch-definition",
    "proposition",
    "question",
    "report",
    "research-question",
    "story",
    "structural-chain",
    "synthesis",
    "theme",
    "validation-report",
}
_CORRESPONDENCE = {
    "claim-registry",
    "curation-sweep",
    "method",
    "plan",
    "pre-registration",
    "research-package",
    "spec",
    "transformation",
    "workflow",
}
# Every core kind not in the two sets above resolves to `none`.
_NONE = {
    "article",
    "book",
    "code-file",
    "concept",
    "construct",
    "data-package",
    "dataset",
    "decision",
    "experiment",
    "outcome",
    "paper",
    "prose-source",
    "search",
    "talk",
    "task",
    "topic",
    "unknown",
    "variable",
    "workflow-run",
    "workflow-step",
}


def test_core_roster_resolves_exhaustively() -> None:
    """Design acceptance test 8: every core kind maps to the ratified §5 scope."""
    registry = EntityRegistry.with_core_types()
    expected = (
        {kind: CurationScope.EPISTEMIC for kind in _EPISTEMIC}
        | {kind: CurationScope.CORRESPONDENCE for kind in _CORRESPONDENCE}
        | {kind: CurationScope.NONE for kind in _NONE}
    )
    assert set(expected) == registry.core_kinds(), "roster and registered core kinds disagree"
    for kind, scope in expected.items():
        assert registry.curation_scope_for_kind(kind) is scope, kind


def test_closed_list_kinds_all_resolve_none() -> None:
    """Design acceptance test 2: the deleted closed list's knowledge is preserved."""
    registry = EntityRegistry.with_core_types()
    for kind in (
        "task",
        "dataset",
        "workflow-run",
        "data-package",
        "paper",
        "prose-source",
        "book",
        "experiment",
        "code-file",
    ):
        assert registry.curation_scope_for_kind(kind) is CurationScope.NONE, kind


def test_core_kind_undeclared_defaults_none() -> None:
    """Design acceptance test 3: a core kind with no declaration → none (refused later)."""
    registry = EntityRegistry()
    registry.register_core_kind("gadget", ProjectEntity, entity_class=EntityClass.OPERATIONAL)
    assert registry.curation_scope_for_kind("gadget") is CurationScope.NONE


def test_extension_kind_undeclared_defaults_correspondence() -> None:
    """Design acceptance test 9: an undeclared EXTENSION kind → correspondence."""
    registry = EntityRegistry()
    registry.register_extension_kind("design", ProjectEntity, entity_class=EntityClass.OPERATIONAL)
    assert registry.curation_scope_for_kind("design") is CurationScope.CORRESPONDENCE


def test_extension_kind_declared_scope_wins() -> None:
    registry = EntityRegistry()
    registry.register_extension_kind(
        "design",
        ProjectEntity,
        entity_class=EntityClass.OPERATIONAL,
        curation_scope=CurationScope.NONE,
    )
    assert registry.curation_scope_for_kind("design") is CurationScope.NONE


def test_unregistered_kind_defaults_correspondence() -> None:
    """Unknown kinds behave like extension kinds — reviewable by default (§6.2)."""
    registry = EntityRegistry.with_core_types()
    assert (
        registry.curation_scope_for_kind("totally-unknown-kind")
        is CurationScope.CORRESPONDENCE
    )


def test_registered_kinds_returns_all_registered_sorted() -> None:
    registry = EntityRegistry.with_core_types()

    class WidgetEntity(Entity):
        pass

    registry.register_extension_kind("widget", WidgetEntity, entity_class=EntityClass.OPERATIONAL)

    kinds = registry.registered_kinds()
    assert kinds["workflow-step"].__name__ == "WorkflowStepEntity"
    assert kinds["widget"] is WidgetEntity
    assert list(kinds) == sorted(kinds)
    declaring = [k for k, cls in kinds.items() if "method" in cls.model_fields]
    assert declaring == ["workflow-step"]


def test_with_core_types_registers_all_core_kinds() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("task") is TaskEntity
    assert registry.resolve("dataset") is DatasetEntity
    assert registry.resolve("workflow-run").__name__ == "WorkflowRunEntity"
    assert registry.resolve("research-package").__name__ == "ResearchPackageEntity"
    assert registry.resolve("paper") is PaperEntity


def test_generic_kinds_default_to_project_entity() -> None:
    """Kinds without a dedicated typed entity (concept, topic, question...) are registered
    against ProjectEntity so generic tooling still works."""
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("concept") is ProjectEntity
    assert registry.resolve("topic") is ProjectEntity


def test_hypothesis_resolves_to_its_typed_entity() -> None:
    """`hypothesis` is no longer generic: it carries the two orthogonal lifecycle axes
    (`status` = epistemic verdict, `disposition` = workflow state), and `disposition` must
    be a DECLARED model field or it is silently dropped at model_validate -- which is what
    already happened to `phase` (fb-2026-07-11-005).
    """
    from science_model.entities import HypothesisEntity

    registry = EntityRegistry.with_core_types()
    assert registry.resolve("hypothesis") is HypothesisEntity


def test_curation_sweep_kind_registered() -> None:
    """fb-2026-05-01-007: curation-sweep ledgers must resolve so health/inventory
    don't emit skip-noise on every run."""
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("curation-sweep") is ProjectEntity


def test_pre_registration_kind_registered_as_operational() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("pre-registration") is ProjectEntity
    assert registry.kind_class("pre-registration") == EntityClass.OPERATIONAL


def test_inquiry_kind_is_epistemic() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.kind_class("inquiry") == EntityClass.EPISTEMIC


def test_research_question_kind_registered() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("research-question") is ProjectEntity
    assert registry.kind_class("research-question") == EntityClass.EPISTEMIC


def test_mechanism_kind_resolves_to_typed_entity() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("mechanism") is MechanismEntity


def test_unknown_kind_raises() -> None:
    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindNotRegisteredError, match="frobnicator"):
        registry.resolve("frobnicator")


def test_duplicate_core_registration_is_hard_error() -> None:
    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindAlreadyRegisteredError):
        registry.register_core_kind("task", TaskEntity, entity_class=EntityClass.OPERATIONAL)


def test_duplicate_extension_registration_is_hard_error() -> None:
    class ProjectExtA(ProjectEntity):
        pass

    class ProjectExtB(ProjectEntity):
        pass

    registry = EntityRegistry.with_core_types()
    registry.register_extension_kind("natural-system:model", ProjectExtA)
    with pytest.raises(EntityKindAlreadyRegisteredError):
        registry.register_extension_kind("natural-system:model", ProjectExtB)


def test_extension_cannot_shadow_core() -> None:
    class BogusDataset(ProjectEntity):
        pass

    registry = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindShadowError, match="dataset"):
        registry.register_extension_kind("dataset", BogusDataset)


def test_profile_kind_registration_resolves() -> None:
    registry = EntityRegistry.with_core_types()
    registry.register_profile_kind("model", ProjectEntity, owner="local")
    assert registry.resolve("model") is ProjectEntity


def test_declared_catalog_kind_resolves_to_domain_entity() -> None:
    registry = EntityRegistry.with_core_types()
    registry.register_catalog_kind("gene", DomainEntity, owner="biology")
    assert registry.resolve("gene") is DomainEntity


def test_duplicate_catalog_kind_registration_is_allowed_when_schema_matches() -> None:
    registry = EntityRegistry.with_core_types()
    registry.register_catalog_kind("electric_field", DomainEntity, owner="physics")
    registry.register_catalog_kind("electric_field", DomainEntity, owner="units")

    assert registry.resolve("electric_field") is DomainEntity


def test_extension_cannot_shadow_catalog_kind() -> None:
    registry = EntityRegistry.with_core_types()
    registry.register_catalog_kind("gene", DomainEntity, owner="biology")
    with pytest.raises(EntityKindShadowError, match="gene"):
        registry.register_extension_kind("gene", ProjectEntity)


def test_resolve_round_trip_extension() -> None:
    class CustomModelEntity(ProjectEntity):
        equation: str = ""

    registry = EntityRegistry.with_core_types()
    registry.register_extension_kind("natural-system:model", CustomModelEntity)
    assert registry.resolve("natural-system:model") is CustomModelEntity


def test_evidence_line_kind_resolves_to_typed_entity() -> None:
    """evidence-line must be registered as a typed EPISTEMIC entity in the core registry."""
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("evidence-line") is EvidenceLineEntity
    assert registry.kind_class("evidence-line") == EntityClass.EPISTEMIC


def test_registered_class_must_subclass_entity() -> None:
    class NotAnEntity:
        pass

    registry = EntityRegistry()
    with pytest.raises(TypeError, match="must subclass Entity"):
        registry.register_core_kind("x", NotAnEntity, entity_class=EntityClass.OPERATIONAL)  # type: ignore[arg-type]


def test_core_registry_resolves_patch_definition() -> None:
    from science_model.entities import EntityClass
    from science_model.patch_definition import PatchDefinitionEntity

    from science_tool.graph.entity_registry import EntityRegistry

    registry = EntityRegistry.with_core_types()

    assert registry.resolve("patch-definition") is PatchDefinitionEntity
    assert registry.kind_class("patch-definition") is EntityClass.EPISTEMIC


def test_load_project_sources_binds_falsification_entity(tmp_path: Path) -> None:
    """A kind: falsification source file loads as FalsificationEntity, proving CORE_KIND_MODELS."""
    from science_model.entities import FalsificationEntity

    from _fixtures.entity_helpers import seed_project, write_markdown_entity
    from science_tool.graph.sources import load_project_sources

    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/propositions/p1.md",
        {
            "id": "proposition:p1",
            "kind": "proposition",
            "title": "Drug improves recovery",
            "status": "active",
            "source_refs": [],
        },
        "Drug improves recovery\n",
    )
    write_markdown_entity(
        tmp_path,
        "entities/falsifications/f01.md",
        {
            "id": "falsification:f01",
            "kind": "falsification",
            "title": "Refuted",
            "status": "active",
            "falsifies": "proposition:p1",
            "predicted": "improves",
            "observed": "no change",
            "decision": "reject",
            "source_of_prediction": "topic:x",
            "related": [],
            "source_refs": [],
        },
        "Refuted\n",
    )

    sources = load_project_sources(tmp_path)

    loaded = [e for e in sources.entities if e.canonical_id == "falsification:f01"]
    assert len(loaded) == 1
    assert isinstance(loaded[0], FalsificationEntity)
    assert loaded[0].falsifies == "proposition:p1"
