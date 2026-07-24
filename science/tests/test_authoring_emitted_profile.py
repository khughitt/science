"""Witnesses that the dataset authoring writers EMIT the shared default profile.

`test_identity_authoring.py` asserts the constant is derived from `default_profile_for_kind`.
That is necessary and not sufficient: it examines the declaration, not the emission. A writer
that stopped consuming the constant -- inlining `science-entity-base/1.0+dataset/1.0` back into
its own signature -- would re-create the `status: REPLACE` crash (fb-2026-07-12-006) for every
newly authored dataset while the constant, and every test that only reads the constant, stayed
green. These tests read what actually lands on disk.

Each exercises the writer's DEFAULT path (no `schema_profile` argument), because the default is
the only thing the shared constant governs. Explicit `schema_profile` arguments remain the
mechanism for pinned semantics and are covered by the pinned-1.0 controls.
"""
from __future__ import annotations

from pathlib import Path

from science_model.entity_schema.profile import default_profile_for_kind

from science_tool.datasets_catalog import add_dataset
from science_tool.datasets_register import _entity_yaml_block

EXPECTED = "science-entity-base/1.0+dataset/2.0"


def test_expected_profile_tracks_the_shared_default() -> None:
    """Pins this module's literal to the one authority.

    Without this, the literal below is a third declaration of the dataset default and would
    drift exactly the way the authoring constant already did.
    """
    assert EXPECTED == default_profile_for_kind("dataset").render()


def test_project_dataset_authoring_emits_the_default_profile(tmp_path: Path) -> None:
    _entity_id, path, _warnings = add_dataset(
        tmp_path,
        "mock-cohort",
        title="Mock cohort",
        source_url="https://example.org/mock",
    )

    assert f"schema_profile: {EXPECTED}" in path.read_text(encoding="utf-8")


def test_register_run_renderer_emits_the_given_profile() -> None:
    block = _entity_yaml_block(
        slug="mock-derived",
        title="Mock derived",
        workflow_id="workflow:mock",
        workflow_run_id="run-1",
        git_commit="abc1234",
        config_snapshot="{}",
        produced_at="2026-07-16T00:00:00Z",
        inputs=["dataset:mock-cohort"],
        transformations=None,
        dp_path_rel="data/mock-derived/datapackage.yaml",
        ontology_terms=[],
        schema_profile=EXPECTED,
    )

    assert f'schema_profile: "{EXPECTED}"' in block
