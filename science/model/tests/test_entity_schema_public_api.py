from __future__ import annotations


def test_public_api_exports() -> None:
    from science_model.entity_schema import (
        EntityValidator,
        EntityValidationError,
        MergePolicy,
        ProfileString,
        SharedEntity,
        parse_profile,
        read_merge_policy,
        read_overlay_merge_policy,
    )

    assert EntityValidator is not None
    assert EntityValidationError is not None
    assert MergePolicy.REPLACE.value == "replace"
    assert callable(parse_profile)
    assert callable(read_merge_policy)
    assert callable(read_overlay_merge_policy)
    assert ProfileString is not None
    assert SharedEntity is not None


def test_top_level_export() -> None:
    import science_model

    assert hasattr(science_model, "EntityValidator")
    assert hasattr(science_model, "SharedEntity")


def test_top_level_all_contains_entity_schema_exports() -> None:
    import science_model

    for name in ("EntityValidator", "EntityValidationError", "MergePolicy", "SharedEntity"):
        assert name in science_model.__all__, f"{name!r} missing from science_model.__all__"
