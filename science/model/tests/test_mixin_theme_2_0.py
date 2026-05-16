"""Tests for mixin-theme-2.0.json."""
from __future__ import annotations


def test_theme_mixin_2_0_loads_via_default_profile() -> None:
    from science_model.entity_schema import default_profile_for_kind

    profile = default_profile_for_kind("theme")
    assert profile.mixin is not None
    assert profile.mixin.name == "theme"
    assert profile.mixin.version == "2.0"


def test_theme_mixin_2_0_canonical_body_sections() -> None:
    from science_model.entity_schema import (
        default_profile_for_kind,
        read_canonical_body_sections,
    )

    sections = read_canonical_body_sections(default_profile_for_kind("theme"))
    assert sections == [
        "Definition",
        "Why It Matters",
        "Boundaries",
        "Guardrails",
        "Open Questions",
        "Update Triggers",
    ]


def test_theme_mixin_2_0_merge_policies() -> None:
    from science_model.entity_schema import (
        MergePolicy,
        default_profile_for_kind,
        read_merge_policy,
    )

    policy = read_merge_policy(default_profile_for_kind("theme"))
    assert policy["status"] == MergePolicy.PROJECT_ONLY
    assert policy["created"] == MergePolicy.PROJECT_ONLY
    assert policy["updated"] == MergePolicy.PROJECT_ONLY
    assert policy["source_refs"] == MergePolicy.APPEND
    assert policy["evidence_refs"] == MergePolicy.APPEND
    assert policy["related"] == MergePolicy.APPEND


def test_theme_mixin_2_0_keeps_required_kind_and_scope() -> None:
    import json
    from pathlib import Path

    schemas_dir = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"
    schema = json.loads((schemas_dir / "mixin-theme-2.0.json").read_text())
    assert "theme_kind" in schema["required"]
    assert "theme_scope" in schema["required"]


def test_theme_mixin_2_0_keeps_theme_kind_enum_canonical() -> None:
    import json
    from pathlib import Path

    schemas_dir = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"
    schema = json.loads((schemas_dir / "mixin-theme-2.0.json").read_text())
    assert schema["properties"]["theme_kind"]["enum"] == [
        "methodological",
        "conceptual",
        "empirical",
        "domain",
    ]
    assert "biological" not in schema["properties"]["theme_kind"]["enum"]
