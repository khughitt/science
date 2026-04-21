"""Tests for EntityRecord schema + _normalize_record helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.entity_providers.record import EntityRecord, _normalize_record


def _ctx() -> EntityDiscoveryContext:
    return EntityDiscoveryContext(
        project_root=Path("/tmp/x"),
        project_slug="x",
        local_profile="local",
    )


def test_entity_record_minimal_construction() -> None:
    r = EntityRecord(
        canonical_id="hypothesis:h01",
        kind="hypothesis",
        title="Test",
        source_path="doc/hypotheses/h01.md",
    )
    assert r.canonical_id == "hypothesis:h01"
    assert r.description == ""
    assert r.related == []
    assert r.aliases == []


def test_entity_record_with_description() -> None:
    r = EntityRecord(
        canonical_id="topic:t1",
        kind="topic",
        title="T1",
        source_path="doc/topics/topics.json",
        description="Some prose about t1.",
    )
    assert r.description == "Some prose about t1."


def test_normalize_record_produces_source_entity_with_provider_set() -> None:
    record = EntityRecord(
        canonical_id="hypothesis:h01",
        kind="hypothesis",
        title="Test hypothesis",
        source_path="doc/hypotheses/h01.md",
    )
    se = _normalize_record(record, _ctx(), provider_name="markdown")
    assert se.canonical_id == "hypothesis:h01"
    assert se.kind == "hypothesis"
    assert se.title == "Test hypothesis"
    assert se.provider == "markdown"


def test_normalize_record_canonicalizes_paper_ids() -> None:
    """kind=='paper' triggers canonical_paper_id() rewriting."""
    record = EntityRecord(
        canonical_id="article:doe2024",  # `article:` gets rewritten to `paper:`
        kind="paper",
        title="Doe 2024",
        source_path="entities.yaml",
    )
    se = _normalize_record(record, _ctx(), provider_name="aggregate")
    assert se.canonical_id == "paper:doe2024"


def test_normalize_record_derives_aliases() -> None:
    record = EntityRecord(
        canonical_id="hypothesis:h01",
        kind="hypothesis",
        title="Test",
        source_path="doc/hypotheses/h01.md",
        aliases=["H01"],
    )
    se = _normalize_record(record, _ctx(), provider_name="markdown")
    # Explicit alias preserved.
    assert "H01" in se.aliases
    # hypothesis/question/task short-token expansion: upper-case variant and bare tokens.
    assert "hypothesis:H01" in se.aliases
    assert "h01" in se.aliases


def test_normalize_record_defaults_profile_when_unset() -> None:
    """When EntityRecord.profile is None, the normalizer applies _default_profile_for_kind."""
    record = EntityRecord(
        canonical_id="hypothesis:h01",
        kind="hypothesis",
        title="Test",
        source_path="doc/hypotheses/h01.md",
        profile=None,
    )
    se = _normalize_record(record, _ctx(), provider_name="markdown")
    # hypothesis is a core kind → default profile is "core".
    assert se.profile == "core"
