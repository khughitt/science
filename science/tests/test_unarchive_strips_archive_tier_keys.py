"""`unarchive` must not restore archive-tier bookkeeping into the live corpus.

Found by the schema-closure `observation` slice (step 1), as a defect in ALREADY-SHIPPED
slices rather than in that one. `consolidate.py` stamps `consolidated_into` onto each
member's frontmatter and relocates it under `entities/_archive/`, which is safe:
`entity_scan.iter_entity_markdown` skips `_`-prefixed segments, so the archived file is
never loaded, and `--include-archived` reads the archive INDEX, not the files.

`unarchive_entities` was a bare `shutil.move`. It restored the file to its live, scanned,
SCHEMA-VALIDATED path with the key still present -- and no closed kind's mixin admits it,
so `unevaluatedProperties: false` failed the whole project load.

The reproduction below is the one that found it, kept as a regression test because the
unit-level assertions alone would not have shown that the blast radius is the project
rather than the record.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from science_tool.archive import (
    ARCHIVE_TIER_FRONTMATTER_KEYS,
    _restore_live_frontmatter,
    archive_entities,
    derive_archive_path,
    unarchive_entities,
)
from science_tool.consolidate import apply_consolidation, scaffold_digest
from science_tool.entities import _parse_markdown_file, create_entity
from science_tool.graph.sources import load_project_sources

# `search` is used throughout because it is ARMED today: its mixin composes with
# `unevaluatedProperties: false`, so it can actually demonstrate the refusal. An unarmed
# kind would pass every assertion here for the wrong reason.
ARMED_KIND = "search"
ARMED_HOME = "searches"


def _project(tmp_path: Path, *, generation: int | None = 3) -> Path:
    """A project pinned to an entity_schema_version, which is what turns schema
    validation ON: `validate_against_schema` returns early when `project_schema` is None,
    so an unpinned project would load a bad record happily and prove nothing."""
    lines = ["name: t"]
    if generation is not None:
        lines.append(f"entity_schema_version: {generation}")
    lines += ["knowledge_profiles:", "  local: local", ""]
    (tmp_path / "science.yaml").write_text("\n".join(lines), encoding="utf-8")
    return tmp_path


def _consolidated(root: Path) -> str:
    create_entity(root, ARMED_KIND, "A", entity_id=f"{ARMED_KIND}:0001-a")
    create_entity(root, ARMED_KIND, "B", entity_id=f"{ARMED_KIND}:0002-b")
    scaffold_digest(
        root,
        digest_id="synthesis:0001-d",
        member_ids=[f"{ARMED_KIND}:0001-a", f"{ARMED_KIND}:0002-b"],
        title="Digest",
    )
    apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")
    return "synthesis:0001-d"


def test_the_archived_file_still_carries_the_breadcrumb(tmp_path: Path) -> None:
    """The strip is on RESTORE, not on write.

    While archived, the frontmatter copy is a breadcrumb for a human reading the file in
    `_archive/`, and nothing loads it. Asserting this pins which half of the round trip
    the fix belongs to -- deleting the write instead would be a different, larger change.
    """
    root = _project(tmp_path)
    digest = _consolidated(root)
    archived = root / derive_archive_path(f"entities/{ARMED_HOME}/0001-a.md")
    frontmatter, _ = _parse_markdown_file(archived)
    assert frontmatter["consolidated_into"] == digest
    assert frontmatter["status"] == "archived"


def test_unarchive_strips_consolidated_into(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _consolidated(root)
    unarchive_entities(root, [f"{ARMED_KIND}:0001-a"], apply=True, now="T2")

    restored = root / f"entities/{ARMED_HOME}/0001-a.md"
    frontmatter, _ = _parse_markdown_file(restored)
    assert "consolidated_into" not in frontmatter


def test_unarchive_strips_nothing_else(tmp_path: Path) -> None:
    """The strip is a named key, not a scrub.

    `status` is deliberately NOT restored to its pre-archive value: it is a declared field
    with real meaning, `archived` is in this kind's vocabulary, and rewriting it would be a
    behaviour change this ruling did not make.
    """
    root = _project(tmp_path)
    _consolidated(root)
    before, before_body = _parse_markdown_file(
        root / derive_archive_path(f"entities/{ARMED_HOME}/0001-a.md")
    )
    unarchive_entities(root, [f"{ARMED_KIND}:0001-a"], apply=True, now="T2")
    after, after_body = _parse_markdown_file(root / f"entities/{ARMED_HOME}/0001-a.md")

    assert set(before) - set(after) == {"consolidated_into"}
    assert all(after[key] == before[key] for key in after)
    assert after["status"] == "archived"
    assert after_body == before_body


def test_the_restored_project_loads(tmp_path: Path) -> None:
    """The regression, at the blast radius that makes it matter.

    Before the strip this raised
    `ValueError: entities/searches/0001-a.md: search frontmatter does not satisfy its
    schema ... Unevaluated properties are not allowed ('consolidated_into' was
    unexpected)` -- failing the WHOLE project load. The surviving sibling and the digest
    are asserted too: a load that returned only the restored record would also satisfy a
    weaker assertion.
    """
    root = _project(tmp_path)
    _consolidated(root)
    unarchive_entities(root, [f"{ARMED_KIND}:0001-a"], apply=True, now="T2")

    ids = {entity.canonical_id for entity in load_project_sources(root).entities}
    assert f"{ARMED_KIND}:0001-a" in ids
    assert "synthesis:0001-d" in ids


def test_the_reproduction_fails_without_the_strip(tmp_path: Path, monkeypatch) -> None:
    """The control, in the direction that proves the other tests are not vacuous.

    With the key set emptied, `unarchive` reverts to the bare `shutil.move` it was, and
    the project load fails again. Without this, every assertion above would still pass if
    the schema had quietly stopped closing -- which is exactly how a slice certifies its
    own accident.
    """
    root = _project(tmp_path)
    _consolidated(root)
    monkeypatch.setattr("science_tool.archive.ARCHIVE_TIER_FRONTMATTER_KEYS", frozenset())
    unarchive_entities(root, [f"{ARMED_KIND}:0001-a"], apply=True, now="T2")

    with pytest.raises(ValueError, match="consolidated_into"):
        load_project_sources(root)


def test_a_plainly_archived_entity_round_trips_untouched(tmp_path: Path) -> None:
    """`entities archive` performs no frontmatter edits, so its files carry none of these
    keys and `_restore_live_frontmatter` must not rewrite them at all."""
    root = _project(tmp_path)
    create_entity(root, ARMED_KIND, "A", entity_id=f"{ARMED_KIND}:0001-a")
    path = root / f"entities/{ARMED_HOME}/0001-a.md"
    path.write_text(path.read_text().replace("status: active", "status: archived"))
    original = path.read_bytes()

    archive_entities(root, ids=frozenset({f"{ARMED_KIND}:0001-a"}), apply=True, now="T1")
    unarchive_entities(root, [f"{ARMED_KIND}:0001-a"], apply=True, now="T2")

    assert path.read_bytes() == original


def test_the_key_set_names_exactly_what_a_mutator_writes() -> None:
    """A guard that LISTS its scope has a hole by construction, so the list is pinned to
    the one writer that puts a bookkeeping key in an archived record's frontmatter.

    `apply_consolidation` writes `consolidated_into` (and `status`, which is a declared
    field, not bookkeeping). `ArchiveRow`'s other P4-reserved fields -- `digest_insight`,
    `cluster_id` -- travel on the INDEX only and never reach frontmatter. Widening this
    set means finding a new writer, and this assertion is what forces that to be a
    deliberate edit.

    Scoped to `apply_consolidation` specifically, not to `consolidate.py`: the module also
    holds `scaffold_digest`, which writes `report_kind` and `relations` onto the DIGEST --
    a `synthesis` that stays live and is never archived. A file-wide scan conflates the two
    write sites and reports keys no member ever carries.
    """
    assert ARCHIVE_TIER_FRONTMATTER_KEYS == frozenset({"consolidated_into"})

    written = {
        line.split('fm["', 1)[1].split('"]', 1)[0]
        for line in inspect.getsource(apply_consolidation).splitlines()
        if 'fm["' in line
    }
    assert written == {"status", "consolidated_into"}, (
        f"apply_consolidation now writes {sorted(written)} to member frontmatter; "
        "re-rule each new key before widening ARCHIVE_TIER_FRONTMATTER_KEYS"
    )


# --- the `finding` slice's inheritance claim, pinned rather than reasoned about ---


def test_the_strip_is_kind_agnostic_by_construction() -> None:
    """The `finding` slice (step 1) claimed it inherits this fix. This is that claim.

    `_restore_live_frontmatter` takes a path and nothing else -- no kind argument, no kind
    branch -- so every consolidatable kind is covered by construction rather than by a list
    someone has to remember to extend. A guard that LISTS its scope has a hole; this one
    cannot, and that is asserted here instead of being read off the source once.
    """
    signature = inspect.signature(_restore_live_frontmatter)
    assert list(signature.parameters) == ["path"]
    source = inspect.getsource(_restore_live_frontmatter)
    assert "kind" not in source, (
        "_restore_live_frontmatter now mentions `kind`; if the strip has become "
        "kind-dependent, every closed kind needs re-checking individually"
    )


def test_a_consolidated_finding_is_stripped_on_restore(tmp_path: Path) -> None:
    """The same round trip, driven through `finding` -- the kind this slice closes.

    `finding` declares `archived` among its statuses and is therefore consolidatable, so
    it reaches the same writer that produced the defect. Run at step 3, while `finding` is
    still dormant: what this shows is that the STRIP fires for this kind. That the
    unstripped key would fail the whole project load is demonstrated for armed kinds by
    `test_the_reproduction_fails_without_the_strip` above, and for `finding` itself by the
    step-6 derived-behaviour probes once arming makes it reachable.
    """
    root = _project(tmp_path)
    create_entity(root, "finding", "A", entity_id="finding:0001-a")
    create_entity(root, "finding", "B", entity_id="finding:0002-b")
    scaffold_digest(
        root,
        digest_id="synthesis:0001-d",
        member_ids=["finding:0001-a", "finding:0002-b"],
        title="Digest",
    )
    apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")
    path = root / "entities/findings/0001-a.md"

    unarchive_entities(root, ["finding:0001-a"], apply=True, now="T2")

    restored = path.read_text()
    assert "consolidated_into" not in restored
    assert "id: finding:0001-a" in restored
