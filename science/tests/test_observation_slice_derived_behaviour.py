"""Step 6 of the observation slice: what arming changed, through the REAL load path.

Every other test in this slice reaches the composed schema by monkeypatching
`PROJECT_MIXIN_NAMES` and `TYPE_MIXIN_NAMES`. This file does not patch anything: it drives
`load_project_sources` on a real project directory and observes what production does now
that `schema_closed=True`.

**Why this file exists in the form it does.** The measured graph diff across the arming
boundary was BYTE-IDENTICAL -- which is exactly what a slice that armed nothing produces.
The `method` slice recorded that lesson: pair the diff with a control in BOTH directions,
or step 6 proves only that the sweep ran. The two-direction measurement was:

    this branch (observation ARMED):  REFUSED -- Unevaluated properties are not allowed
                                      ('shadow_key' was unexpected)
    main        (observation UNARMED): LOADED (22 entities) -- shadow_key preserved unvouched

run with the two real toolkits rather than one patched one. The unarmed half cannot be kept
as a test in this branch, because this branch IS the armed toolkit; what survives here is
the armed half plus the invariance of the clean-corpus output.

**The corpus's own project could not be used.** `~/d/health/processes/cycles` holds all 21
records and cannot be loaded at all: `tasks/active.md predates the storage split`. Verified
to fail identically with `main`'s toolkit, so it is a pre-existing condition and not
something this slice introduced -- the same situation the `search` slice hit with
`~/d/health/processes/post-acute-infection`. That project's records are certified at the
schema boundary in `test_observation_slice_certification_real_projects.py`; the end-to-end
path is exercised here on a synthetic project of the same shape instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.sources import load_project_sources

# 21 records, 14 carrying `promoted_from` -- the corpus proportions, so the load path
# exercises the one admitted-but-undeclared field a real record actually has.
_RECORD_COUNT = 21
_PROMOTED_COUNT = 14


def _observation(slug: str, *, promoted: bool, extra: str = "") -> str:
    promoted_line = "promoted_from: doc/observations/observations.yaml\n" if promoted else ""
    return (
        "---\n"
        f'id: "observation:{slug}"\n'
        'kind: "observation"\n'
        f'title: "Observation {slug}"\n'
        'status: "active"\n'
        "related: []\n"
        "source_refs: []\n"
        f"{promoted_line}{extra}"
        'created: "2026-04-01"\n'
        'updated: "2026-04-01"\n'
        "---\n\n"
        "Body.\n"
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A gen-3 project, because `entity_schema_version` is what turns validation ON.

    `validate_against_schema` returns early when `project_schema` is None, so an unpinned
    project is untouched by arming. That is not a detail: it is why arming this kind broke
    ZERO fixtures, where the `method` slice broke one. 20 test files declare a generation
    and none of them authors an observation; the two that author observations declare none.
    """
    (tmp_path / "science.yaml").write_text(
        "name: obs-probe\nentity_schema_version: 3\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )
    home = tmp_path / "entities" / "observations"
    home.mkdir(parents=True)
    for index in range(_RECORD_COUNT):
        slug = f"probe-{index:02d}"
        (home / f"{slug}.md").write_text(
            _observation(slug, promoted=index < _PROMOTED_COUNT), encoding="utf-8"
        )
    return tmp_path


def test_the_corpus_shape_loads_through_production(project: Path) -> None:
    """No patching. If arming refused a shape the real corpus has, this is where it shows."""
    entities = load_project_sources(project).entities
    observations = [entity for entity in entities if entity.kind == "observation"]
    assert len(observations) == _RECORD_COUNT


def test_promoted_from_survives_the_real_load_path(project: Path) -> None:
    """The admitted-but-undeclared field, end to end rather than at the model boundary.

    `ProjectEntity` does not declare `promoted_from`; it survives on `extra="allow"` per
    D3.3. `test_observation_slice_contract_reconciliation.py` checks that at the projection
    boundary with a hand-built payload. This checks the same property for records that went
    through the adapter, the composed schema, and the projection in sequence -- which is the
    only arrangement any of them ever runs in.
    """
    entities = load_project_sources(project).entities
    carried = [
        entity
        for entity in entities
        if entity.kind == "observation"
        and (entity.model_extra or {}).get("promoted_from")
        == "doc/observations/observations.yaml"
    ]
    assert len(carried) == _PROMOTED_COUNT


def test_an_undeclared_key_is_refused_through_production(project: Path) -> None:
    """The armed half of the two-direction control, as a durable regression.

    On `main` before this slice the same record LOADED and `shadow_key` was preserved
    unvouched -- measured, quoted in the module docstring. Note the blast radius: the whole
    project fails to load, not just the offending record, which is what makes the byte-
    identical graph diff above safe to report as "nothing else changed" rather than as
    "nothing happened".
    """
    (project / "entities" / "observations" / "probe-bad.md").write_text(
        _observation("probe-bad", promoted=False, extra='shadow_key: "unvouched"\n'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="shadow_key"):
        load_project_sources(project)


def test_the_omitted_writer_keys_are_refused_through_production(project: Path) -> None:
    """The slice's two rulings, at the surface where they have consequences.

    `consolidated_into` is refused because step 3 made `unarchive` strip it, so no live
    record can carry it. `superseded_by` is refused because `observation` is
    `supersedable=False` -- there the schema is enforcing the descriptor.
    """
    home = project / "entities" / "observations"
    for key, value in (
        ("consolidated_into", "synthesis:0001-d"),
        ("superseded_by", "observation:probe-00"),
    ):
        bad = home / "probe-bad.md"
        bad.write_text(
            _observation("probe-bad", promoted=False, extra=f'{key}: "{value}"\n'),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match=key):
            load_project_sources(project)
        bad.unlink()


def test_a_project_without_a_declared_generation_is_untouched(tmp_path: Path) -> None:
    """The boundary of what arming changed, asserted rather than assumed.

    An unpinned project keeps loading an undeclared key exactly as before, because
    `validate_against_schema` returns early when `project_schema` is None. This is the
    control for the fixture claim in the `project` fixture's docstring -- and it explains
    why "budget for fixtures that enumerate the armed set" is too coarse a rule: a fixture
    is exposed only if its project declares `entity_schema_version`.
    """
    (tmp_path / "science.yaml").write_text(
        "name: unpinned\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    home = tmp_path / "entities" / "observations"
    home.mkdir(parents=True)
    (home / "probe.md").write_text(
        _observation("probe", promoted=False, extra='shadow_key: "unvouched"\n'),
        encoding="utf-8",
    )

    entities = load_project_sources(tmp_path).entities
    assert len(entities) == 1
    assert (entities[0].model_extra or {}).get("shadow_key") == "unvouched"
