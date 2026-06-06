from __future__ import annotations

from science_model.profiles.schema import EntityKind


def test_entity_kind_accepts_optional_layout_and_status_fields() -> None:
    ek = EntityKind(
        name="design",
        canonical_prefix="design",
        layer="layer/local",
        description="Project-local design spec.",
        home="entities/designs",
        strategy="numeric",
        default_status="active",
        statuses=["active", "superseded"],
    )
    assert ek.home == "entities/designs"
    assert ek.strategy == "numeric"
    assert ek.default_status == "active"
    assert ek.statuses == ["active", "superseded"]


def test_entity_kind_overrides_default_to_none() -> None:
    ek = EntityKind(name="note", canonical_prefix="note", layer="layer/local", description="Note.")
    assert ek.home is None
    assert ek.strategy is None
    assert ek.default_status is None
    assert ek.statuses is None
