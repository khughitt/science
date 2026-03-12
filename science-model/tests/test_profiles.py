from science_model.profiles.schema import EntityKind, ProfileManifest, RelationKind


def test_profile_manifest_requires_imports_for_extension_profiles() -> None:
    manifest = ProfileManifest(
        name="project_specific",
        imports=["core"],
        entity_kinds=[],
        relation_kinds=[],
        strictness="typed-extension",
    )
    assert manifest.imports == ["core"]


def test_profile_manifest_round_trip() -> None:
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
    round_tripped = ProfileManifest.model_validate(dumped)
    assert round_tripped == manifest
