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


@pytest.fixture
def runtime_schema() -> dict:
    return json.loads((SCHEMA_DIR / "science-pkg-runtime-1.0.json").read_text())


def _valid_runtime_pkg() -> dict:
    return {
        "profiles": ["science-pkg-runtime-1.0"],
        "name": "example",
        "resources": [
            {
                "name": "table",
                "path": "data/table.csv",
                "format": "csv",
                "mediatype": "text/csv",
                "bytes": 1234,
                "hash": "sha256:abc",
            }
        ],
    }


def test_runtime_pkg_minimal_valid(runtime_schema: dict) -> None:
    jsonschema.validate(_valid_runtime_pkg(), runtime_schema)


def test_runtime_rejects_top_level_access(runtime_schema: dict) -> None:
    """Runtime surface MUST NOT carry top-level access: (entity-only block)."""
    pkg = _valid_runtime_pkg()
    pkg["access"] = {"level": "public", "verified": True}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(pkg, runtime_schema)


def test_runtime_rejects_top_level_derivation(runtime_schema: dict) -> None:
    pkg = _valid_runtime_pkg()
    pkg["derivation"] = {"workflow_run": "workflow-run:x"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(pkg, runtime_schema)


def test_runtime_rejects_top_level_origin(runtime_schema: dict) -> None:
    """Runtime surface MUST NOT carry top-level origin: (entity-only discriminator)."""
    pkg = _valid_runtime_pkg()
    pkg["origin"] = "external"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(pkg, runtime_schema)


def test_invariant_7_external_with_derivation_rejects(entity_schema: dict) -> None:
    """origin: external + derivation: -> reject (#7)."""
    e = _valid_external_entity()
    e["derivation"] = {
        "workflow_run": "workflow-run:x",
        "workflow": "workflow:x",
        "git_commit": "abc",
        "config_snapshot": "",
        "produced_at": "",
        "inputs": [],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(e, entity_schema)


def _valid_derived_entity() -> dict:
    return {
        "profiles": ["science-pkg-entity-1.0"],
        "id": "dataset:wf-r1-out1",
        "type": "dataset",
        "title": "Derived",
        "status": "active",
        "origin": "derived",
        "tier": "use-now",
        "datapackage": "results/wf/r1/out1/datapackage.yaml",
        "derivation": {
            "workflow": "workflow:wf",
            "workflow_run": "workflow-run:wf-r1",
            "git_commit": "abc1234",
            "config_snapshot": "results/wf/r1/config.yaml",
            "produced_at": "2026-04-19T12:00:00Z",
            "inputs": ["dataset:upstream"],
        },
    }


def test_invariant_8_derived_with_access_rejects(entity_schema: dict) -> None:
    """origin: derived + access: -> reject (#8)."""
    e = _valid_derived_entity()
    e["access"] = {"level": "public", "verified": True}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(e, entity_schema)


def test_invariant_8_derived_with_accessions_rejects(entity_schema: dict) -> None:
    """origin: derived + accessions: -> reject (#8: external accession IDs forbidden on derived)."""
    e = _valid_derived_entity()
    e["accessions"] = ["EGAD00001"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(e, entity_schema)


def test_derived_entity_minimal_valid(entity_schema: dict) -> None:
    """A minimal valid origin: derived entity (with required derivation block) passes validation."""
    jsonschema.validate(_valid_derived_entity(), entity_schema)
