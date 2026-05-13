from __future__ import annotations

import pytest

from science_model.entity_schema.validator import (
    EntityValidationError,
    EntityValidator,
)


def test_overlay_minimal_validates() -> None:
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
    }
    EntityValidator().validate_overlay(overlay)


def test_overlay_with_project_only_fields_validates() -> None:
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
        "pin_version": "1.2.0",
        "relevance": "H2 — supports homology-split argument",
        "hypothesis_links": ["H2", "H4"],
        "task_links": ["t087"],
        "project_tags": ["high-priority"],
    }
    EntityValidator().validate_overlay(overlay)


def test_overlay_with_pin_effective_version_validates() -> None:
    overlay = {
        "id": "dataset:cath-domains",
        "overlay_of": "dataset:cath-domains",
        "pin_effective_version": "1.2.0+abc1234",
    }
    EntityValidator().validate_overlay(overlay)


def test_overlay_rejects_canonical_field() -> None:
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
        "title": "I'm trying to override the title",  # base merge: replace — forbidden in overlay
    }
    with pytest.raises(EntityValidationError, match="title"):
        EntityValidator().validate_overlay(overlay)


def test_overlay_rejects_mismatched_overlay_of() -> None:
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Different",
    }
    with pytest.raises(EntityValidationError, match="overlay_of"):
        EntityValidator().validate_overlay(overlay)


def test_overlay_permits_append_fields() -> None:
    # tags + ontology_terms have merge: append on the canonical schema, so
    # overlays must be allowed to add to them.
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
        "tags": ["project-relevant", "discussed-in-meeting-3"],
        "ontology_terms": ["EFO:0000400"],
    }
    EntityValidator().validate_overlay(overlay)


def test_overlay_rejects_dataset_id_with_uppercase() -> None:
    # Dataset canonical IDs are lowercase-kebab. Overlay ids reference
    # canonical ids, so the same per-type slug rules apply.
    overlay = {
        "id": "dataset:NotKebab",
        "overlay_of": "dataset:NotKebab",
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate_overlay(overlay)


def test_overlay_accepts_paper_id_with_bibkey_casing() -> None:
    # Paper bibkey IDs allow mixed case (e.g. Adams2025); the per-type
    # oneOf must accept this form.
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
    }
    EntityValidator().validate_overlay(overlay)
