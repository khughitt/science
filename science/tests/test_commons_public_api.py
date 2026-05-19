"""Public API surface of science_tool.commons."""
from __future__ import annotations


def test_public_api_exports() -> None:
    import science_tool.commons as pkg
    expected = {
        "CommonsEntityAdapter",
        "CommonsEntityError",
        "CommonsEntityRecord",
        "CommonsError",
        "CommonsLayoutError",
        "CommonsRegistryError",
        "CommonsRootMalformedError",
        "CommonsRootNotFoundError",
        "CommonsQuery",
        "CommonsSettings",
        "CommonsValidator",
        "RebuildReport",
        "RegistryBuilder",
        "ValidationReport",
        "commons_group",
        "init_commons",
        "resolve_commons_root",
        # Phase C
        "CommonsDatapackageError",
        "DataLogicalPathError",
        "DataResourceNotFoundError",
        "DataIntegrityError",
        "resolve_commons_data_root",
        "load_data_overrides",
        "DataResource",
        "DatapackageDescriptor",
        "read_datapackage",
        "validate_logical_path",
        "parse_resource_hash",
        "ResolvedDataResource",
        "resolve",
        # Phase D1
        "OverlayAdapter",
        "OverlayRecord",
        "MergedEntity",
        "OverlayValidationReport",
        "merge_entity",
        "resolve_entity",
        "validate_project_overlays",
        "resolve_project_root",
        "ProjectNotRegisteredError",
        "ProjectDirectoryMissingError",
        "OverlayValidationError",
        "OverlayMergeError",
        # Phase D2
        "build_commons_inventory",
        # Phase G
        "PromoteOverrideConflictError",
        # Phase H
        "PromoteMixinResolutionError",
        "PromoteMixinStackingError",
    }
    assert expected.issubset(set(pkg.__all__))
    for name in expected:
        assert hasattr(pkg, name), f"missing public name: {name}"
