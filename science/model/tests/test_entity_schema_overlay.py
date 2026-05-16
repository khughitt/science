from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from science_model.entity_schema import MergePolicy, read_overlay_merge_policy
from science_model.entity_schema.validator import (
    EntityValidationError,
    EntityValidator,
)

_SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"


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


def test_overlay_1_1_schema_loads():
    schema = json.loads((_SCHEMAS / "overlay-1.1.json").read_text(encoding="utf-8"))
    assert schema["$id"].endswith("overlay-1.1.json")
    for field in ("status", "source", "related", "source_refs", "created", "updated"):
        assert field in schema["properties"], f"{field} missing"
    assert schema["additionalProperties"] is False


def test_overlay_1_1_canonical_id_regex_permits_hyphens_for_papers():
    schema = json.loads((_SCHEMAS / "overlay-1.1.json").read_text(encoding="utf-8"))
    patterns = [arm["pattern"] for arm in schema["$defs"]["canonicalId"]["oneOf"]]
    paper_pattern = next(p for p in patterns if "paper" in p)
    assert re.match(paper_pattern, "paper:categorical-composition-trio-2023-2025")
    assert re.match(paper_pattern, "paper:Adams2025")


def test_read_overlay_merge_policy_uses_1_1_and_returns_project_only_for_new_fields():
    policy = read_overlay_merge_policy()
    # New 1.1 fields default to project_only (no annotation):
    for field in ("status", "source", "related", "source_refs", "created", "updated"):
        assert policy[field] == MergePolicy.PROJECT_ONLY, f"{field} should be project_only"
    # Pre-existing annotations preserved:
    assert policy["tags"] == MergePolicy.APPEND
    assert policy["ontology_terms"] == MergePolicy.APPEND


def test_validate_overlay_accepts_paper_overlay_with_new_fields():
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
        "pin_version": "1.0.0",
        "status": "active",
        "source": "manual",
        "related": ["question:q1"],
        "source_refs": ["doi:10.1/abc"],
        "created": "2026-01-15",
        "updated": "2026-05-15",
    }
    EntityValidator().validate_overlay(overlay)  # should not raise


def test_validate_overlay_rejects_unknown_field():
    overlay = {
        "id": "paper:Adams2025",
        "overlay_of": "paper:Adams2025",
        "bogus_field": "x",
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate_overlay(overlay)


def test_validate_overlay_accepts_hyphenated_paper_id():
    overlay = {
        "id": "paper:categorical-composition-trio-2023-2025",
        "overlay_of": "paper:categorical-composition-trio-2023-2025",
    }
    EntityValidator().validate_overlay(overlay)  # should not raise
