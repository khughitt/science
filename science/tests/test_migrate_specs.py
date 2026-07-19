"""Tests for `science entity migrate-specs` (S3b)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
import yaml

from science_tool.entity_reservation import claim_number_in_dir
from science_tool.migrate_specs import (
    CANONICAL_SPEC_STATUS,
    LEGACY_ALIAS,
    RUNTIME_ONLY,
    SpecMigrationRefused,
    allocate_ids,
    discover_specs,
    project_legacy_frontmatter,
)


def _spec_project(tmp_path: Path) -> Path:
    """A minimal project root — verified audit-capable for `_validate_prospective_write`/load."""
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "p", "id": "p"}), encoding="utf-8")
    (tmp_path / "entities/specs").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_claim_number_unlinks_its_own_partial_on_write_failure(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    dest = project / "entities/specs" / "0001-x.md"
    boom = OSError("disk full")

    real_open = open

    def _open(path: object, *args: object, **kwargs: object):  # noqa: ANN002
        handle = real_open(path, *args, **kwargs)  # type: ignore[call-overload]
        if Path(str(path)) == dest:
            handle.write = mock.Mock(side_effect=boom)  # type: ignore[method-assign]
        return handle

    with mock.patch("builtins.open", _open):
        with pytest.raises(OSError, match="disk full"):
            claim_number_in_dir(project, "spec", 1, "0001-x", "body")

    assert not dest.exists(), "a caught write failure must leave no partial destination"
    assert not (project / "entities/specs" / ".0001.reserving").exists(), "sentinel cleared"


def test_runtime_only_set_is_exact() -> None:
    assert RUNTIME_ONLY == frozenset({"project", "file_path", "content", "content_preview", "canonical_id"})
    assert LEGACY_ALIAS == frozenset({"type", "date", "related_questions", "related_specs"})
    assert CANONICAL_SPEC_STATUS == frozenset(
        {"draft", "active", "complete", "superseded", "retired", "archived"}
    )


def test_projection_maps_type_date_status_related_and_preserves_supersedes() -> None:
    old_id, fm = project_legacy_frontmatter(
        {
            "id": "spec:2026-03-16-meta-model-design",
            "type": "spec",
            "title": "Meta-Model Design",
            "date": "2026-03-16",
            "status": "design",
            "related": ["question:0001-x"],
            "related_questions": ["question:0005-y"],
            "aliases": ["spec:old-alias"],
            "supersedes": ["spec:2026-01-01-older"],
        },
        source_rel="doc/plans/meta-model.md",
    )
    assert old_id == "spec:2026-03-16-meta-model-design"
    assert fm["kind"] == "spec"
    assert "type" not in fm
    assert fm["created"] == "2026-03-16" and fm["updated"] == "2026-03-16"
    assert fm["status"] == "draft"
    assert fm["related"] == ["question:0001-x", "question:0005-y"]
    assert "related_questions" not in fm
    assert fm["aliases"] == ["spec:old-alias"]  # old id NOT appended here
    assert fm["supersedes"] == ["spec:2026-01-01-older"]
    assert fm["id"] == old_id


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [("proposed", "draft"), ("in-progress", "active"), ("implemented", "complete"), ("superseded", "superseded"), ("active", "active")],
)
def test_projection_status_adjudication(legacy: str, canonical: str) -> None:
    _old, fm = project_legacy_frontmatter(
        {"id": "spec:x", "type": "spec", "title": "T", "created": "2026-01-01", "updated": "2026-01-01", "status": legacy},
        source_rel="doc/x.md",
    )
    assert fm["status"] == canonical


def test_projection_refuses_unmappable_status() -> None:
    with pytest.raises(SpecMigrationRefused, match="approved"):
        project_legacy_frontmatter(
            {"id": "spec:x", "type": "spec", "title": "T", "date": "2026-01-01", "status": "approved"},
            source_rel="doc/x.md",
        )


def test_projection_refuses_runtime_only_key() -> None:
    with pytest.raises(SpecMigrationRefused, match="content"):
        project_legacy_frontmatter(
            {"id": "spec:x", "type": "spec", "title": "T", "date": "2026-01-01", "content": "x"}, source_rel="doc/x.md"
        )


def test_projection_refuses_authored_canonical_id() -> None:
    with pytest.raises(SpecMigrationRefused, match="canonical_id"):
        project_legacy_frontmatter(
            {"id": "spec:x", "type": "spec", "title": "T", "date": "2026-01-01", "canonical_id": "spec:x"}, source_rel="doc/x.md"
        )


def test_projection_refuses_created_without_updated_or_date() -> None:
    with pytest.raises(SpecMigrationRefused, match="updated"):
        project_legacy_frontmatter(
            {"id": "spec:x", "type": "spec", "title": "T", "created": "2026-01-01"}, source_rel="doc/x.md"
        )


def test_projection_refuses_kind_type_disagreement() -> None:
    with pytest.raises(SpecMigrationRefused, match="disagree"):
        project_legacy_frontmatter(
            {"id": "spec:x", "kind": "design", "type": "spec", "title": "T", "date": "2026-01-01"}, source_rel="doc/x.md"
        )


def test_projection_refuses_missing_id_or_title() -> None:
    with pytest.raises(SpecMigrationRefused, match="id"):
        project_legacy_frontmatter({"type": "spec", "title": "T", "date": "2026-01-01"}, source_rel="doc/x.md")
    with pytest.raises(SpecMigrationRefused, match="title"):
        project_legacy_frontmatter({"id": "spec:x", "type": "spec", "date": "2026-01-01"}, source_rel="doc/x.md")


def _write(path: Path, frontmatter: dict, body: str = "Body.\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n{body}", encoding="utf-8")
    return path


def _legacy_spec(project: Path, rel: str, spec_id: str, title: str, **extra: object) -> Path:
    """A canonical legacy spec doc — always carries `date` and a mappable `status` so projection
    accepts it. Use everywhere a migrating doc must survive `_plan_all`."""
    fm: dict[str, object] = {"id": spec_id, "type": "spec", "title": title, "date": "2026-01-01", "status": "draft"}
    fm.update(extra)
    return _write(project / rel, fm)


def test_discovery_finds_loose_specs_and_skips_conforming(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:2026-01-01-a", "type": "spec", "title": "A"})
    _write(project / "doc/specs/b.md", {"id": "spec:semantic-b", "kind": "spec", "title": "B"})
    _write(project / "entities/specs/0009-c.md", {"id": "spec:0009-c", "kind": "spec", "title": "C"})  # conforming
    _write(project / "doc/plans/d.md", {"id": "design:0001-d", "kind": "design", "title": "D"})  # not a spec

    disc = discover_specs(project)
    assert {ls.old_id for ls in disc.legacy} == {"spec:2026-01-01-a", "spec:semantic-b"}
    assert disc.singletons == []
    assert disc.scan_skips == []


def test_discovery_reports_singleton_home(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "entities/research-question.md", {"id": "spec:research-question", "kind": "spec", "title": "RQ"})
    disc = discover_specs(project)
    assert [s.rel_path for s in disc.singletons] == ["entities/research-question.md"]
    assert disc.legacy == []


def test_discovery_already_numeric_out_of_home_carries_number(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/keep.md", {"id": "spec:0007-keep", "type": "spec", "title": "Keep"})
    disc = discover_specs(project)
    assert len(disc.legacy) == 1 and disc.legacy[0].already_numeric == 7


def test_discovery_iso_date_prefixed_id_is_not_already_numeric(tmp_path: Path) -> None:
    # A date-slug id (the dominant legacy convention) has a calendar-YEAR head, not a sequence number,
    # so it is discovered as a MINT candidate (already_numeric is None), never a preserved relocation.
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/dated.md", {"id": "spec:2026-03-16-meta-model-design", "type": "spec", "title": "Meta Model"})
    disc = discover_specs(project)
    assert len(disc.legacy) == 1 and disc.legacy[0].already_numeric is None


def test_discovery_refuses_spec_doc_without_id(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/noid.md", {"type": "spec", "title": "No Id"})
    with pytest.raises(SpecMigrationRefused, match="without a declared"):
        discover_specs(project)


def test_discovery_refuses_malformed_spec_id_with_separators(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/evil.md", {"id": "spec:0007-x/../../outside", "type": "spec", "title": "Evil"})
    with pytest.raises(SpecMigrationRefused, match="malformed"):
        discover_specs(project)


def test_discovery_refuses_in_home_stem_id_mismatch(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    # conforming filename stem 0009-c, but the declared id says 0008 — do not silently skip
    _write(project / "entities/specs/0009-c.md", {"id": "spec:0008-c", "kind": "spec", "title": "C"})
    with pytest.raises(SpecMigrationRefused, match="disagree"):
        discover_specs(project)


def test_discovery_oversized_markdown_becomes_scan_skip(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    from science_tool.text_scan import MAX_SCANNABLE_BYTES

    (project / "doc/plans").mkdir(parents=True, exist_ok=True)
    (project / "doc/plans/huge.md").write_text("x" * (MAX_SCANNABLE_BYTES + 1), encoding="utf-8")
    assert any(s.path == "doc/plans/huge.md" for s in discover_specs(project).scan_skips)


def test_discovery_oversized_non_markdown_becomes_scan_skip(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    from science_tool.text_scan import MAX_SCANNABLE_BYTES

    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src/huge.py").write_text("x" * (MAX_SCANNABLE_BYTES + 1), encoding="utf-8")
    assert any(s.path == "src/huge.py" for s in discover_specs(project).scan_skips)


def test_discovery_unreadable_markdown_becomes_scan_skip(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    (project / "doc/plans").mkdir(parents=True, exist_ok=True)
    (project / "doc/plans/bad.md").write_bytes(b"\xff\xfe not utf-8")
    assert any(s.path == "doc/plans/bad.md" for s in discover_specs(project).scan_skips)


def test_allocation_mints_distinct_sequential_numbers(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "Alpha Title"})
    _write(project / "doc/plans/b.md", {"id": "spec:date-b", "type": "spec", "title": "Beta Title"})
    alloc = allocate_ids(project, discover_specs(project).legacy)
    assert alloc.id_substitutions == {"spec:date-a": "spec:0001-alpha-title", "spec:date-b": "spec:0002-beta-title"}
    assert alloc.dest_rel["spec:date-a"] == "entities/specs/0001-alpha-title.md"
    assert alloc.aliased == frozenset({"spec:date-a", "spec:date-b"})


def test_allocation_slug_is_from_title_not_id(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    # An ISO-date-prefixed legacy id (the dominant convention) whose local part disagrees with the
    # title. The leading 4 digits are a calendar YEAR, so this must be MINTED (not preserved as an
    # already-numeric relocation), and its slug must come from the title, not the old id.
    _write(project / "doc/plans/drift.md", {"id": "spec:2026-01-01-old-filename", "type": "spec", "title": "A Wholly Different Title"})
    alloc = allocate_ids(project, discover_specs(project).legacy)
    assert alloc.new_local_part["spec:2026-01-01-old-filename"] == "0001-a-wholly-different-title"


def test_allocation_preserves_already_numeric_relocation(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/keep.md", {"id": "spec:0007-keep", "type": "spec", "title": "Keep It"})
    alloc = allocate_ids(project, discover_specs(project).legacy)
    assert alloc.id_substitutions == {}
    assert alloc.preserved_ids == frozenset({"spec:0007-keep"})
    assert alloc.dest_rel["spec:0007-keep"] == "entities/specs/0007-keep.md"
    assert "spec:0007-keep" not in alloc.aliased


def test_allocation_refuses_relocation_number_taken_at_home(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "entities/specs/0007-existing.md", {"id": "spec:0007-existing", "kind": "spec", "title": "Existing"})
    _write(project / "doc/plans/keep.md", {"id": "spec:0007-keep", "type": "spec", "title": "Keep It"})
    with pytest.raises(SpecMigrationRefused, match="0007"):
        allocate_ids(project, discover_specs(project).legacy)


def test_allocation_mixed_batch_skips_preserved_number(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/keep.md", {"id": "spec:0001-keep", "type": "spec", "title": "Keep It"})
    _write(project / "doc/plans/mint.md", {"id": "spec:date-mint", "type": "spec", "title": "Mint Me"})
    alloc = allocate_ids(project, discover_specs(project).legacy)
    assert alloc.id_substitutions == {"spec:date-mint": "spec:0002-mint-me"}
    assert alloc.preserved_ids == frozenset({"spec:0001-keep"})
