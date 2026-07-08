"""Tests for mixin-theme-2.0.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args


def _load_theme_schema() -> dict[str, object]:
    schemas_dir = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"
    return json.loads((schemas_dir / "mixin-theme-2.0.json").read_text())


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
    schema = _load_theme_schema()
    assert schema["$id"] == "https://schemas.science/mixin-theme-2.0.json"
    assert schema["required"] == ["id", "kind", "theme_kind", "theme_scope"]


def test_theme_mixin_2_0_keeps_theme_kind_enum_canonical() -> None:
    from science_model.entities import ThemeEntity

    schema = _load_theme_schema()
    properties = schema["properties"]
    assert isinstance(properties, dict)
    theme_kind = properties["theme_kind"]
    assert isinstance(theme_kind, dict)
    assert theme_kind["enum"] == list(get_args(ThemeEntity.model_fields["theme_kind"].annotation))


def test_theme_mixin_2_0_keeps_theme_scope_enum_canonical() -> None:
    schema = _load_theme_schema()
    properties = schema["properties"]
    assert isinstance(properties, dict)
    theme_scope = properties["theme_scope"]
    assert isinstance(theme_scope, dict)
    assert theme_scope["enum"] == ["project", "cross-project"]
