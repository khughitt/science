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
    }
    assert expected.issubset(set(pkg.__all__))
    for name in expected:
        assert hasattr(pkg, name), f"missing public name: {name}"
