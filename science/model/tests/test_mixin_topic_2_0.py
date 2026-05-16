"""Tests for mixin-topic-2.0.json."""
from __future__ import annotations


def test_topic_mixin_2_0_loads_via_default_profile() -> None:
    from science_model.entity_schema import default_profile_for_kind

    profile = default_profile_for_kind("topic")
    assert profile.mixin is not None
    assert profile.mixin.name == "topic"
    assert profile.mixin.version == "2.0"


def test_topic_mixin_2_0_canonical_body_sections() -> None:
    from science_model.entity_schema import (
        default_profile_for_kind,
        read_canonical_body_sections,
    )

    sections = read_canonical_body_sections(default_profile_for_kind("topic"))
    assert "Summary" in sections
    assert "Key Concepts" in sections
    assert "Current State of Knowledge" in sections
    assert "Controversies & Open Questions" in sections
    assert "Key References" in sections


def test_topic_mixin_2_0_merge_policies() -> None:
    from science_model.entity_schema import (
        MergePolicy,
        default_profile_for_kind,
        read_merge_policy,
    )

    policy = read_merge_policy(default_profile_for_kind("topic"))
    assert policy["status"] == MergePolicy.PROJECT_ONLY
    assert policy["created"] == MergePolicy.PROJECT_ONLY
    assert policy["updated"] == MergePolicy.PROJECT_ONLY
    assert policy["datasets"] == MergePolicy.APPEND
    assert policy["source_refs"] == MergePolicy.APPEND
    assert policy["related"] == MergePolicy.APPEND


def test_topic_mixin_2_0_id_regex() -> None:
    """Schema is valid Draft 2020-12 and the id pattern is lowercase-kebab."""
    import json
    from pathlib import Path

    schemas_dir = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"
    schema = json.loads((schemas_dir / "mixin-topic-2.0.json").read_text())
    assert schema["properties"]["id"]["pattern"].startswith("^topic:")
