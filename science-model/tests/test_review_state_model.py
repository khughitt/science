"""Unit tests for EntityClass, EpistemicReviewState, and review_state frontmatter parsing."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from science_model.entities import Entity, EntityClass, EpistemicReviewState, core_entity_type_for_kind
from science_model.frontmatter import parse_entity_file


def test_entity_class_values():
    assert EntityClass.EPISTEMIC.value == "epistemic"
    assert EntityClass.OPERATIONAL.value == "operational"
    assert EntityClass.REFERENCE.value == "reference"


def test_review_state_defaults():
    rs = EpistemicReviewState()
    assert rs.last_reviewed is None
    assert rs.last_review_note == ""
    assert rs.review_horizon_days is None


def test_review_state_with_values():
    rs = EpistemicReviewState(
        last_reviewed=date(2026, 5, 1),
        last_review_note="Re-checked after Lee2026 dataset added",
        review_horizon_days=90,
    )
    assert rs.last_reviewed == date(2026, 5, 1)
    assert rs.last_review_note == "Re-checked after Lee2026 dataset added"
    assert rs.review_horizon_days == 90


def test_review_state_rejects_negative_horizon():
    with pytest.raises(ValidationError, match="review_horizon_days"):
        EpistemicReviewState(review_horizon_days=-1)


def test_review_state_rejects_zero_horizon():
    with pytest.raises(ValidationError, match="review_horizon_days"):
        EpistemicReviewState(review_horizon_days=0)


def test_entity_default_review_state_is_unset(tmp_path: Path):
    p = tmp_path / "h01.md"
    p.write_text(
        '---\n'
        'id: "hypothesis:h01"\n'
        'kind: "hypothesis"\n'
        'title: "Test hypothesis"\n'
        'created: "2026-04-01"\n'
        '---\n\nBody.\n'
    )
    entity = parse_entity_file(p, project_slug="demo")
    assert entity is not None
    assert entity.review_state is None


def test_entity_parses_review_state_block(tmp_path: Path):
    p = tmp_path / "h01.md"
    p.write_text(
        '---\n'
        'id: "hypothesis:h01"\n'
        'kind: "hypothesis"\n'
        'title: "Test hypothesis"\n'
        'created: "2026-04-01"\n'
        'review_state:\n'
        '  last_reviewed: "2026-05-01"\n'
        '  last_review_note: "Re-checked after Lee2026 added"\n'
        '  review_horizon_days: 90\n'
        '---\n\nBody.\n'
    )
    entity = parse_entity_file(p, project_slug="demo")
    assert entity is not None
    assert entity.review_state is not None
    assert entity.review_state.last_reviewed == date(2026, 5, 1)
    assert entity.review_state.last_review_note == "Re-checked after Lee2026 added"
    assert entity.review_state.review_horizon_days == 90


def test_entity_review_state_partial_block(tmp_path: Path):
    p = tmp_path / "h01.md"
    p.write_text(
        '---\n'
        'id: "hypothesis:h01"\n'
        'kind: "hypothesis"\n'
        'title: "Test hypothesis"\n'
        'created: "2026-04-01"\n'
        'review_state:\n'
        '  last_reviewed: "2026-05-01"\n'
        '---\n\nBody.\n'
    )
    entity = parse_entity_file(p, project_slug="demo")
    assert entity is not None
    assert entity.review_state is not None
    assert entity.review_state.last_reviewed == date(2026, 5, 1)
    assert entity.review_state.last_review_note == ""
    assert entity.review_state.review_horizon_days is None


NON_EPISTEMIC_KINDS = ["task", "dataset", "workflow-run", "data-package", "paper", "experiment"]


def _baseline_kwargs(kind: str) -> dict:
    return {
        "id": f"{kind}:t",
        "kind": kind,
        "type": core_entity_type_for_kind(kind),
        "title": "T",
        "project": "p",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "x.md",
    }


@pytest.mark.parametrize("kind", NON_EPISTEMIC_KINDS)
def test_review_state_rejected_on_non_epistemic_kinds(kind: str) -> None:
    rs = EpistemicReviewState(last_reviewed=None)
    with pytest.raises(ValidationError, match="review_state"):
        Entity(**_baseline_kwargs(kind), review_state=rs)


@pytest.mark.parametrize("kind", NON_EPISTEMIC_KINDS)
def test_no_review_state_still_valid_on_non_epistemic_kinds(kind: str) -> None:
    Entity(**_baseline_kwargs(kind))


def test_review_state_allowed_on_open_kinds() -> None:
    # Kinds outside the closed list (incl. extension kinds) keep accepting review_state.
    rs = EpistemicReviewState(last_reviewed=None)
    Entity(**_baseline_kwargs("hypothesis"), review_state=rs)
    Entity(**_baseline_kwargs("custom-extension-kind"), review_state=rs)
