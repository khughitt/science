from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from science_tool.entities import (
    EntityCommandError,
    default_status,
    generate_entity_id,
    local_part_conforms,
    path_for_entity,
    resolve_path_policy,
    valid_statuses,
    validate_entity_id,
)


def test_concept_is_a_core_slug_policy() -> None:
    policy = resolve_path_policy("concept")
    assert policy.strategy == "slug"
    assert policy.root == Path("entities/concepts")


def test_concept_has_a_status_vocabulary() -> None:
    # A core kind without a status entry makes plan_migration -> synthesize_frontmatter
    # -> default_status/valid_statuses raise KeyError mid-migration (Task 2 depends on this).
    assert default_status("concept") == "active"
    assert valid_statuses("concept") is not None
    assert "active" in valid_statuses("concept")


def test_slug_local_part_conforms() -> None:
    assert local_part_conforms("concept", "1q-gain") is True
    assert local_part_conforms("concept", "age") is True
    assert local_part_conforms("concept", "Not A Slug") is False
    assert local_part_conforms("concept", "trailing-") is False


def test_validate_entity_id_accepts_slug_rejects_garbage() -> None:
    assert validate_entity_id("concept", "concept:1q-gain") == "concept:1q-gain"
    with pytest.raises(EntityCommandError):
        validate_entity_id("concept", "concept:Bad Slug")


def test_generate_slug_id_uses_title_slug_not_number(tmp_path: Path) -> None:
    # No NNNN- prefix: slug strategy preserves the title-slug directly.
    got = generate_entity_id(tmp_path, "concept", "Chromosome 1q Gain", None, None)
    assert got == "concept:chromosome-1q-gain"


def test_path_for_concept_lands_under_entities_concepts() -> None:
    p = path_for_entity("concept", "concept:1q-gain", date(2026, 6, 8))
    assert p == Path("entities/concepts/1q-gain.md")


def test_numeric_and_citekey_unchanged() -> None:
    # Regression: existing strategies are untouched.
    assert local_part_conforms("question", "0001-foo") is True
    assert local_part_conforms("question", "1q-gain") is False
    assert validate_entity_id("question", "question:0001-foo") == "question:0001-foo"
    assert validate_entity_id("paper", "paper:Adams2025") == "paper:Adams2025"
    with pytest.raises(EntityCommandError):
        validate_entity_id("question", "question:1q-gain")
