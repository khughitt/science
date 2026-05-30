"""Promote-side normalization of heavyweight derived-dataset derivation blocks.

Regression for fb-2026-05-30-003: a derived dataset (`origin: derived`) could not
be both project-local validate-clean AND commons-promotable. Project-local
`DerivationBlock` requires the heavyweight register-run form (workflow,
workflow_run, git_commit, config_snapshot, produced_at, inputs); the commons
`mixin-dataset-1.0` "workflow derivation" requires the lightweight form
(workflow_recipe, inputs). `commons promote` now normalizes the heavyweight form
into the commons workflow_recipe form so a single authored state satisfies both.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from science_tool.commons.promote import _normalize_derivation_for_commons

_HEAVYWEIGHT = {
    "workflow": "workflow:cohort-assemble",
    "workflow_run": "workflow-run:2026-05-04-cohort-assemble",
    "git_commit": "abc123",
    "config_snapshot": "config/cohort.lock.yaml",
    "produced_at": "2026-05-04",
    "inputs": ["dataset:raw-cohort", "dataset:treatment-status"],
}


def _commons_derivation_schema() -> dict:
    schema_path = (
        Path(__file__).parent.parent
        / "model/src/science_model/schemas/mixin-dataset-1.0.json"
    )
    full = json.loads(schema_path.read_text(encoding="utf-8"))
    return {"$defs": full["$defs"], "$ref": "#/$defs/derivation"}


def test_heavyweight_derivation_normalized_to_workflow_recipe():
    out = _normalize_derivation_for_commons(_HEAVYWEIGHT)
    assert out["kind"] == "workflow"
    assert out["workflow_recipe"] == "workflow:cohort-assemble"
    assert out["inputs"] == ["dataset:raw-cohort", "dataset:treatment-status"]
    assert out["recipe_lockfile"] == "config/cohort.lock.yaml"
    # Run-specific provenance fields are dropped from the commons recipe form.
    assert "workflow_run" not in out
    assert "git_commit" not in out
    assert "produced_at" not in out


def test_normalized_heavyweight_validates_against_commons_schema():
    out = _normalize_derivation_for_commons(_HEAVYWEIGHT)
    jsonschema.validate(out, _commons_derivation_schema())


def test_already_commons_form_is_unchanged():
    commons_form = {
        "kind": "workflow",
        "workflow_recipe": "workflow:cohort-assemble",
        "inputs": ["dataset:raw-cohort"],
    }
    assert _normalize_derivation_for_commons(commons_form) == commons_form


def test_member_of_derivation_is_unchanged():
    member = {
        "kind": "member_of",
        "parent_dataset": "dataset:cohort-collection",
        "member_key": "g2",
    }
    assert _normalize_derivation_for_commons(member) == member
