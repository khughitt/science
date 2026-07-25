from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from science_model.entities import Entity
from science_model.frontmatter import parse_entity_file

RUN_ID = "run:2026-07-24-curation-sweep-a3f1"


def _entity(**overrides: object) -> Entity:
    # Entity's required fields, verified against `Entity.model_fields`:
    # id, kind, title, project, ontology_terms, related, source_refs,
    # content_preview, file_path.
    payload: dict[str, object] = {
        "id": "topic:demo",
        "kind": "topic",
        "title": "Demo",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "entities/topics/demo.md",
    }
    payload.update(overrides)
    return Entity.model_validate(payload)


def test_field_defaults_to_none() -> None:
    assert _entity().autonomous_run is None


def test_valid_reference_is_kept() -> None:
    assert _entity(autonomous_run=RUN_ID).autonomous_run == RUN_ID


def test_reference_without_the_run_prefix_is_refused() -> None:
    with pytest.raises(ValidationError, match="run:<id>"):
        _entity(autonomous_run="2026-07-24-curation-sweep-a3f1")


def test_bare_prefix_is_refused() -> None:
    with pytest.raises(ValidationError, match="run:<id>"):
        _entity(autonomous_run="run:")


def test_whitespace_only_reference_is_refused() -> None:
    with pytest.raises(ValidationError, match="run:<id>"):
        _entity(autonomous_run="run:   ")


def test_workflow_run_reference_is_refused() -> None:
    # `run_refs` (workflow runs, belief-bearing) and `autonomous_run` (provenance) are
    # different fields with different targets. Neither accepts the other's values.
    with pytest.raises(ValidationError, match="run:<id>"):
        _entity(autonomous_run="workflow-run:wf-r1")


def test_added_by_is_unaffected() -> None:
    entity = _entity(added_by="user", autonomous_run=RUN_ID)
    assert entity.added_by == "user"
    assert entity.autonomous_run == RUN_ID


def test_field_survives_the_frontmatter_round_trip(tmp_path: Path) -> None:
    # The layer that silently drops an unwired field: without the entity_kwargs mapping
    # this returns an Entity whose autonomous_run is None, with no error anywhere.
    path = tmp_path / "demo.md"
    path.write_text(
        "---\n"
        "id: topic:demo\n"
        "kind: topic\n"
        "title: Demo\n"
        "status: active\n"
        f"autonomous_run: {RUN_ID}\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )
    entity = parse_entity_file(path, "demo")
    assert entity is not None
    assert entity.autonomous_run == RUN_ID


def test_a_commons_canonical_entity_may_not_carry_the_field() -> None:
    # A run names one repo's branch and one base..head commit range, so a commons record
    # carrying it would resolve against a `runs/` directory no consuming project owns —
    # failing every consumer's graph build over a reference only the author can fix.
    with pytest.raises(ValidationError, match="not permitted on a commons-canonical entity"):
        _entity(scope="shared", autonomous_run=RUN_ID)


def test_a_commons_canonical_entity_without_the_field_is_fine() -> None:
    # The rejection is scoped to the field, not to shared scope generally.
    assert _entity(scope="shared").autonomous_run is None


def test_a_project_entity_may_carry_the_field() -> None:
    # Guards against a validator that rejects the field regardless of scope: `project` is
    # the default, so an over-broad check would make every other test in this file fail —
    # but an explicit scope pins the intended contrast.
    assert _entity(scope="project", autonomous_run=RUN_ID).autonomous_run == RUN_ID
