from __future__ import annotations

from science_model.entities import EntityClass as EntityClassFromEntities
from science_model.identity import EntityClass
from science_model.profiles.schema import EntityFilenameStrategy, EntityKind, KindCategory


def test_entity_class_defined_in_identity_and_reexported() -> None:
    assert EntityClassFromEntities is EntityClass
    assert {e.value for e in EntityClass} == {"epistemic", "operational", "reference"}


def test_kind_category_values() -> None:
    assert {c.value for c in KindCategory} == {"authored-core", "reserved", "source-only"}


def test_entity_kind_new_fields_default_to_neutral() -> None:
    ek = EntityKind(name="x", canonical_prefix="x", layer="layer/core", description="d")
    assert ek.entity_class is None
    assert ek.category is None
    assert ek.template_ready is False
    assert ek.shortform is None
    assert ek.strategy is None


def test_entity_kind_typed_fields_coerce() -> None:
    ek = EntityKind(
        name="hypothesis", canonical_prefix="hypothesis", layer="layer/core", description="d",
        entity_class="epistemic", category="authored-core", template_ready=True,
        shortform="h", home="entities/hypotheses", strategy="numeric",
    )
    assert ek.entity_class is EntityClass.EPISTEMIC
    assert ek.category is KindCategory.AUTHORED_CORE
    assert ek.strategy == "numeric"


def test_entity_filename_strategy_is_the_relocated_literal() -> None:
    from science_model.kinds import EntityFilenameStrategy as FromKinds
    assert FromKinds is EntityFilenameStrategy
