"""Tests for science-pkg JSON Schema family."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_DIR = Path(__file__).parent.parent / "src" / "science_model" / "schemas"


@pytest.fixture
def entity_schema() -> dict:
    return json.loads((SCHEMA_DIR / "science-pkg-entity-1.0.json").read_text())


def _valid_external_entity() -> dict:
    return {
        "profiles": ["science-pkg-entity-1.0"],
        "id": "dataset:example",
        "type": "dataset",
        "title": "Example",
        "status": "active",
        "origin": "external",
        "tier": "use-now",
        "access": {
            "level": "public",
            "verified": True,
            "verification_method": "retrieved",
            "last_reviewed": "2026-04-19",
            "verified_by": "claude",
            "source_url": "https://example.com/x",
            "credentials_required": "",
            "exception": {
                "mode": "",
                "decision_date": "",
                "followup_task": "",
                "superseded_by_dataset": "",
                "rationale": "",
            },
        },
    }


def test_external_entity_minimal_valid(entity_schema: dict) -> None:
    jsonschema.validate(_valid_external_entity(), entity_schema)


def test_entity_rejects_resources_field(entity_schema: dict) -> None:
    """Entity surface MUST NOT carry resources[] (single source of truth)."""
    e = _valid_external_entity()
    e["resources"] = [{"name": "x", "path": "data/x.csv"}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(e, entity_schema)
