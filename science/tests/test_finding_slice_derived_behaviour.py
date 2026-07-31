"""Step 6 of the finding slice: what arming changed, through the REAL load path.

Every other test in this slice reaches the composed schema by monkeypatching
`PROJECT_MIXIN_NAMES` and `TYPE_MIXIN_NAMES`. This file patches nothing: it drives
`load_project_sources` and observes what production does now that `schema_closed=True`.

**The measured diff across the arming boundary was BYTE-IDENTICAL** -- same entity counts,
same SHA-256 over every finding's `model_dump(mode="json")`, for all three
finding-bearing projects:

    ~/d/natural-systems                     4172 entities, 172 findings, sha 287c783d...
    ~/d/protein-landscape                    639 entities,  26 findings, sha c3e92849...
    ~/d/cancer/cancer-types/multiple-myeloma 4040 entities,   3 findings, sha fb653948...

172 + 26 + 3 = 201, the whole corpus. That is the right outcome and it is also exactly what
a slice that armed NOTHING produces, so the `method` slice's rule applies: pair the diff
with a control in BOTH directions. The two-direction measurement was run on a REAL project
with the two REAL toolkits -- not one patched one, and not a synthetic stand-in, which is
what the `observation` and `search` slices had to settle for when their corpora's projects
would not load:

    this branch (finding ARMED):   REFUSED -- Unevaluated properties are not allowed
    main        (finding UNARMED): LOADED (4173 entities) -- shadow_key preserved unvouched

The unarmed half cannot survive as a test in this branch, because this branch IS the armed
toolkit. What survives here is the armed half plus the invariance of the clean-corpus
output.

These tests are marked `real_projects`: they read the actual project trees, and under that
marker a missing project FAILS rather than skips.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.sources import load_project_sources

pytestmark = pytest.mark.real_projects

# Measured on this branch AND on `main`, and identical on both -- see the module docstring.
EXPECTED: dict[str, tuple[int, int]] = {
    "natural-systems": (4172, 172),
    "protein-landscape": (639, 26),
    "cancer/cancer-types/multiple-myeloma": (4040, 3),
}

CORPUS_TOTAL = 201


def _project_root(relative: str) -> Path:
    root = Path.home() / "d" / relative
    assert (root / "science.yaml").is_file(), (
        f"expected Science project at {root}; this file's claims are per-project and "
        "cannot be partial"
    )
    return root


def _findings(root: Path) -> list[dict]:
    result = load_project_sources(root)
    out = [
        (item[0] if isinstance(item, tuple) else item).model_dump(mode="json")
        for item in result.entities
        if getattr(item[0] if isinstance(item, tuple) else item, "kind", None) == "finding"
    ]
    out.sort(key=lambda d: d.get("id", ""))
    return out


@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_the_project_still_loads_with_finding_armed(relative):
    """The whole point. `unevaluatedProperties: false` now runs for every one of these
    records on the real load path, and the corpus satisfies it."""
    root = _project_root(relative)
    result = load_project_sources(root)
    total, findings = EXPECTED[relative]
    assert len(result.entities) == total
    assert len(_findings(root)) == findings


def test_the_whole_corpus_loads_and_sums_to_201():
    """Catches the failure the per-project assertions cannot: a project silently dropping
    out of `EXPECTED`, which would leave the parametrized tests certifying a smaller tree."""
    assert sum(count for _, count in EXPECTED.values()) == CORPUS_TOTAL


@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_both_authoring_paths_survive_the_load(relative):
    """`finding` is the only core kind with two paths, so "it loads" is two claims.

    natural-systems is the only project holding both: 23 markdown records and 149 structured
    rows. The structured rows are identifiable by their authored `file_path`, which the
    markdown path declares injected and therefore never carries.
    """
    findings = _findings(_project_root(relative))
    structured = [f for f in findings if f.get("file_path", "").endswith("finding.yaml")]
    if relative == "natural-systems":
        assert len(structured) == 149
        assert len(findings) - len(structured) == 23
    else:
        assert not structured


def test_the_migrated_rows_carry_what_the_migration_gave_them():
    """The migration, observed through the load path rather than in the file.

    A source edit that satisfied the schema but did not reach the projection would pass
    every step-3 test and still be wrong.
    """
    findings = _findings(_project_root("natural-systems"))
    structured = [f for f in findings if f.get("file_path", "").endswith("finding.yaml")]
    assert len(structured) == 149
    assert {f["status"] for f in structured} == {"active"}
    assert {f["updated"] for f in structured} == {"2026-04-30"}
    assert all(f["updated"] == f["created"] for f in structured)


def test_no_loaded_finding_carries_a_refused_key():
    """The omissions, observed on real records after a real load.

    `consolidated_into` is refused and stripped by `unarchive`; a relation's `note` is
    refused and was migrated out of the 3 records that carried it.
    """
    for relative in EXPECTED:
        for finding in _findings(_project_root(relative)):
            assert "consolidated_into" not in finding, finding.get("id")
            for relation in finding.get("relations") or []:
                assert set(relation) <= {"predicate", "target", "graph_layer"}, finding.get("id")


def test_a_project_without_a_declared_generation_is_untouched(tmp_path):
    """The scope limit, asserted rather than assumed.

    `validate_against_schema` returns early when `project_schema is None`, so a project that
    declares no `entity_schema_version` is not leniently validated -- it is UNVALIDATED.
    This is what made the `observation` slice's fixture-breakage prediction wrong, and it
    bounds what arming can possibly have broken: only projects that pinned a generation.
    """
    root = tmp_path / "unpinned"
    (root / "entities" / "findings").mkdir(parents=True)
    (root / "science.yaml").write_text("name: unpinned\nprofile: research\n")
    (root / "entities" / "findings" / "0001-a.md").write_text(
        "---\n"
        'id: "finding:0001-a"\n'
        'kind: "finding"\n'
        'title: "A"\n'
        'status: "active"\n'
        'created: "2026-07-30"\n'
        'updated: "2026-07-30"\n'
        "shadow_key: unvouched\n"
        "---\n\n# A\n"
    )

    result = load_project_sources(root)

    loaded = [
        item[0] if isinstance(item, tuple) else item
        for item in result.entities
        if getattr(item[0] if isinstance(item, tuple) else item, "kind", None) == "finding"
    ]
    assert len(loaded) == 1
    assert loaded[0].model_dump(mode="json")["shadow_key"] == "unvouched"
