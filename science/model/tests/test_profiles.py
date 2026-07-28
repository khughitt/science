import pytest

from science_model.profiles.schema import EntityKind, ProfileManifest, RelationKind


def test_profile_manifest_requires_imports_for_extension_profiles() -> None:
    manifest = ProfileManifest(
        name="local",
        imports=["core"],
        entity_kinds=[],
        relation_kinds=[],
        strictness="typed-extension",
    )
    assert manifest.imports == ["core"]


def test_external_profile_manifest_round_trip_does_not_manufacture_reserved_fields() -> None:
    manifest = ProfileManifest(
        name="core",
        imports=[],
        entity_kinds=[
            EntityKind(
                name="hypothesis",
                canonical_prefix="hypothesis",
                layer="layer/core",
                description="Testable project hypothesis",
            )
        ],
        relation_kinds=[
            RelationKind(
                name="supports",
                predicate="cito:supports",
                source_kinds=["claim", "evidence"],
                target_kinds=["claim", "hypothesis"],
                layer="layer/core",
            )
        ],
        strictness="core",
    )
    dumped = manifest.model_dump()
    assert "schema_closed" not in dumped["entity_kinds"][0]
    round_tripped = ProfileManifest.model_validate(dumped)
    assert round_tripped == manifest


@pytest.mark.parametrize("schema_closed", [True, False])
def test_entity_kind_dump_does_not_strip_an_explicit_toolkit_declaration(
    schema_closed: bool,
) -> None:
    kind = EntityKind(
        name="hypothesis",
        canonical_prefix="hypothesis",
        layer="layer/core",
        description="Testable project hypothesis",
        schema_closed=schema_closed,
    )

    assert kind.model_dump()["schema_closed"] is schema_closed


def test_profile_manifest_serialization_schema_retains_the_entity_kind_contract() -> None:
    manifest_schema = ProfileManifest.model_json_schema(mode="serialization")
    entity_kind_schema = manifest_schema["$defs"]["EntityKind"]

    assert set(entity_kind_schema["properties"]) == {
        "canonical_prefix",
        "category",
        "curation_scope",
        "default_status",
        "description",
        "entity_class",
        "home",
        "layer",
        "name",
        "schema_closed",
        "shortform",
        "statuses",
        "strategy",
        "structured_source",
        "structured_source_root_key",
        "supersedable",
        "template_ready",
    }
    assert entity_kind_schema.get("additionalProperties") is not True
