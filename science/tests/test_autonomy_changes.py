from __future__ import annotations

import pytest

from science_tool.autonomy.changes import (
    BODY_FIELD,
    ChangeSet,
    ChangeType,
    PathChange,
    entity_kind_for_path,
)


def test_a_paper_path_classifies_as_paper():
    assert entity_kind_for_path("entities/papers/smith2020.md") == "paper"


def test_a_hypothesis_path_classifies_as_hypothesis():
    assert entity_kind_for_path("entities/hypotheses/h01-thing.md") == "hypothesis"


def test_a_markdown_singleton_home_classifies():
    assert entity_kind_for_path("entities/research-question.md") == "research-question"


def test_a_non_markdown_singleton_home_is_not_an_entity():
    assert entity_kind_for_path("entities/claim-registry.yaml") is None


def test_a_non_entity_path_is_not_an_entity():
    assert entity_kind_for_path("core/decisions.md") is None
    assert entity_kind_for_path("data/raw/counts.tsv") is None
    assert entity_kind_for_path("science.yaml") is None
    assert entity_kind_for_path("runs/2026-07-25-sweep-a3f1.md") is None


def test_a_file_nested_below_a_kind_home_is_not_that_kind():
    """Only direct children of a home are that kind; a deeper file is unclassified and
    therefore denied by default."""
    assert entity_kind_for_path("entities/papers/attachments/fig1.md") is None


def test_an_archive_tier_path_is_not_an_entity():
    """`_`-prefixed segments are the archive tier (entities.py `_resolve_local_home`)."""
    assert entity_kind_for_path("entities/papers/_archived/old.md") is None


def test_a_non_markdown_file_in_a_markdown_home_is_not_an_entity():
    assert entity_kind_for_path("entities/papers/smith2020.pdf") is None


def test_a_project_local_kind_home_is_unclassified_and_therefore_denied():
    """Classification is derived from CORE_PROFILE only, so a project-local kind is
    never classified. That is safe by construction: a local kind has no allowlist entry,
    so classifying it could not have allowed anything. Denying more is the correct
    direction under default-deny."""
    assert entity_kind_for_path("entities/designs/d01-thing.md") is None


def test_classification_needs_no_project_root():
    """Guard for the import boundary: `science_tool.entities` cycles when it is the
    first `science_tool` import, so this module must stay profile-derived."""
    import inspect

    assert "project_root" not in inspect.signature(entity_kind_for_path).parameters


def test_path_change_is_frozen_and_closed():
    from pydantic import ValidationError

    change = PathChange(path="a.md", change_type=ChangeType.MODIFIED, entity_kind=None, fields=())
    with pytest.raises(ValidationError):
        change.path = "b.md"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        PathChange(path="a.md", change_type=ChangeType.MODIFIED, entity_kind=None, fields=(), extra=1)  # type: ignore[call-arg]


def test_body_field_is_a_pseudo_field_named_content():
    """Body prose is gated as a field so it is denied by default like any other."""
    assert BODY_FIELD == "content"


def test_change_set_holds_its_range():
    cs = ChangeSet(base_commit="a" * 40, head_commit="b" * 40, changes=())
    assert cs.base_commit.startswith("a")
    assert cs.changes == ()
