"""Tests for `science entity migrate-specs` (S3b)."""

from __future__ import annotations

import json as _json
from pathlib import Path
from unittest import mock

import pytest
import yaml
from click.testing import CliRunner
from science_model.frontmatter import split_frontmatter

from science_tool.entities_cli import entity_group
from science_tool.entity_reservation import claim_number_in_dir
from science_tool.migrate_specs import (
    CANONICAL_SPEC_STATUS,
    JOURNAL_PATH,
    LEGACY_ALIAS,
    RUNTIME_ONLY,
    RefRecord,
    SpecMigrationRefused,
    _plan_transaction,
    allocate_ids,
    build_report,
    classify_references,
    discover_specs,
    migrate,
    project_legacy_frontmatter,
    resume,
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


def _by_group(records: list[RefRecord]) -> dict[str, list[RefRecord]]:
    out: dict[str, list[RefRecord]] = {}
    for record in records:
        out.setdefault(record.group, []).append(record)
    return out


def test_classification_two_axes(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(
        project / "doc/ref.md",
        {"id": "design:0001-r", "kind": "design", "title": "R", "related": ["spec:old-a"], "discusses": ["spec:old-a"], "same_as": ["spec:old-a"]},
        body="Prose mention of spec:old-a and spec:ghost and spec:0009-live here.\n",
    )
    _write(project / "entities/specs/0009-live.md", {"id": "spec:0009-live", "kind": "spec", "title": "Live"})
    records, skips = classify_references(
        project, id_substitutions={"spec:old-a": "spec:0001-a"}, live_spec_ids={"spec:0009-live"}, source_rels=frozenset()
    )
    assert skips == []
    groups = _by_group(records)
    assert any(r.surface == "related" for r in groups["rewritten"])
    assert any(r.surface == "same_as" for r in groups["alias_resolved"])
    assert any(r.surface == "discusses" for r in groups["manual_retarget"])
    assert any(r.ref == "spec:ghost" for r in groups["manual_retarget"])
    assert any(r.surface == "mention" and r.ref == "spec:old-a" for r in groups["identity_preserved"])
    assert any(r.ref == "spec:0009-live" for r in groups["unchanged"])


def test_classification_scalar_removable_key_is_rewritten(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/ref.md", {"id": "design:0001-r", "kind": "design", "title": "R", "superseded_by": "spec:old-a"})
    records, _ = classify_references(
        project, id_substitutions={"spec:old-a": "spec:0001-a"}, live_spec_ids=set(), source_rels=frozenset()
    )
    assert any(r.surface == "superseded_by" and r.group == "rewritten" for r in records)


def test_classification_token_boundary(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/b.md", {"id": "design:0001-b", "kind": "design", "title": "B"}, body="ignore science-spec:old-a here. But spec:old-a. ends a sentence.\n")
    records, _ = classify_references(project, id_substitutions={"spec:old-a": "spec:0001-a"}, live_spec_ids=set(), source_rels=frozenset())
    mentions = [r for r in records if r.surface == "mention"]
    assert {r.ref for r in mentions} == {"spec:old-a"}
    assert all(not r.ref.endswith(".") for r in mentions)


def test_classification_markdown_link_to_migrating_source_is_rewritten(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:old-a", "type": "spec", "title": "A"}, body="See [B](b.md#sec).\n")
    records, _ = classify_references(project, id_substitutions={}, live_spec_ids=set(), source_rels=frozenset({"doc/plans/b.md"}))
    assert any(r.surface == "markdown-link" and r.group == "rewritten" for r in records)


def test_classification_excludes_migrating_source_own_identity(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/src.md", {"id": "spec:old-a", "type": "spec", "title": "A", "aliases": ["spec:old-a-alias"]}, body="Body.\n")
    records, _ = classify_references(project, id_substitutions={"spec:old-a": "spec:0001-a"}, live_spec_ids=set(), source_rels=frozenset({"doc/plans/src.md"}))
    assert not any(r.ref in {"spec:old-a", "spec:old-a-alias"} for r in records)


def test_classification_reports_unreadable_scannable_file_as_skip(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src/bad.py").write_bytes(b"\xff\xfe spec:old-a")  # undecodable but scannable
    _records, skips = classify_references(project, id_substitutions={"spec:old-a": "spec:0001-a"}, live_spec_ids=set(), source_rels=frozenset())
    assert any(s.path == "src/bad.py" for s in skips)


def _plan(project: Path):
    disc = discover_specs(project)
    return _plan_transaction(project, disc, allocate_ids(project, disc.legacy))


def test_transaction_renders_new_id_and_old_id_alias(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    dest = next(d for d in _plan(project).destinations if d.old_id == "spec:date-a")
    fm, _body = split_frontmatter(dest.rendered_text)
    assert fm["id"] == "spec:0001-alpha"
    assert "spec:date-a" in fm["aliases"]
    assert dest.dest_rel == "entities/specs/0001-alpha.md"


def test_transaction_intra_batch_id_substitution_list_and_scalar(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha", related=["spec:date-b"], superseded_by="spec:date-b")
    _legacy_spec(project, "doc/plans/b.md", "spec:date-b", "Beta")
    dest_a = next(d for d in _plan(project).destinations if d.old_id == "spec:date-a")
    fm, _ = split_frontmatter(dest_a.rendered_text)
    assert fm["related"] == ["spec:0002-beta"]     # list value substituted
    assert fm["superseded_by"] == "spec:0002-beta"  # scalar value substituted


def test_transaction_intra_batch_path_substitution_with_anchor(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    (project / "doc/plans/a.md").write_text(
        "---\nid: spec:date-a\ntype: spec\ntitle: Alpha\ndate: '2026-01-01'\nstatus: draft\n---\n\nSee [B](b.md#sec).\n",
        encoding="utf-8",
    )
    _legacy_spec(project, "doc/plans/b.md", "spec:date-b", "Beta")
    dest_a = next(d for d in _plan(project).destinations if d.old_id == "spec:date-a")
    assert "0002-beta.md#sec" in dest_a.rendered_text


def test_transaction_collision_preflight_refuses_duplicate_old_ids(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:dup", "Alpha")
    _legacy_spec(project, "doc/specs/a.md", "spec:dup", "Alpha Two")
    with pytest.raises(SpecMigrationRefused, match="duplicate old id"):
        _plan(project)


def test_transaction_collision_preflight_uses_global_alias_authority(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    # an UNRELATED live spec entity (owned by ITS path, not a migrating source) already claims the
    # token the migrated spec's old-id alias would take
    _write(project / "entities/specs/0009-live.md", {"id": "spec:0009-live", "kind": "spec", "title": "Live", "aliases": ["spec:date-a"]})
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    with pytest.raises(SpecMigrationRefused, match="collides"):
        _plan(project)


def test_transaction_collision_preflight_uses_global_mappings_authority(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    # a project mappings.yaml (owned by the non-path mappings sentinel, never a migrating source)
    # already claims the token the migrated spec's old-id alias would take
    _write(project / "entities/specs/0009-live.md", {"id": "spec:0009-live", "kind": "spec", "title": "Live"})
    mappings = project / "knowledge/sources/local/mappings.yaml"
    mappings.parent.mkdir(parents=True, exist_ok=True)
    mappings.write_text(yaml.safe_dump({"aliases": {"spec:date-a": "spec:0009-live"}}), encoding="utf-8")
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    with pytest.raises(SpecMigrationRefused, match="collides"):
        _plan(project)


def test_transaction_collision_preflight_is_case_insensitive(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    # a live entity claims an UPPERCASE variant of the token the old-id alias would take; a case-blind
    # preflight would miss it and let build_alias_map raise an unnormalized AliasCollisionError
    _write(project / "entities/specs/0009-live.md", {"id": "spec:0009-live", "kind": "spec", "title": "Live", "aliases": ["SPEC:DATE-A"]})
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    with pytest.raises(SpecMigrationRefused, match="collides"):
        _plan(project)


def test_transaction_alias_dedup_avoids_false_self_collision(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    # doc already lists its own old id in aliases; appending it must not read as a collision
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha", aliases=["spec:date-a"])
    dest = next(d for d in _plan(project).destinations if d.old_id == "spec:date-a")
    fm, _ = split_frontmatter(dest.rendered_text)
    assert fm["aliases"] == ["spec:date-a"]  # deduped, single occurrence


_SCHEMA_KEYS = {"flip_ready", "legacy_spec_count", "singleton_count", "manual_retarget_count", "singletons", "migrated", "references", "manual_retarget", "scan_complete", "scan_skips"}


def test_report_dry_run_has_schema_and_is_not_flip_ready(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    report = build_report(project)
    assert set(report) == _SCHEMA_KEYS
    assert set(report["references"]) == {"rewritten", "alias_resolved", "identity_preserved", "unchanged", "manual_retarget"}
    assert report["legacy_spec_count"] == 1
    assert report["flip_ready"] is False
    assert report["migrated"][0]["old_id"] == "spec:date-a"
    assert report["manual_retarget_count"] == report["references"]["manual_retarget"]
    assert list((project / "entities/specs").glob("*.md")) == []  # dry run wrote nothing


def test_report_dry_run_refuses_where_apply_would(tmp_path: Path) -> None:
    # duplicate old ids must refuse in the DRY RUN, not only at apply
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:dup", "Alpha")
    _legacy_spec(project, "doc/specs/a.md", "spec:dup", "Alpha Two")
    with pytest.raises(SpecMigrationRefused, match="duplicate old id"):
        build_report(project)


def test_report_clean_project_is_flip_ready(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "entities/specs/0001-a.md", {"id": "spec:0001-a", "kind": "spec", "title": "A"})
    report = build_report(project)
    assert (report["legacy_spec_count"], report["singleton_count"], report["manual_retarget_count"]) == (0, 0, 0)
    assert report["scan_complete"] is True and report["flip_ready"] is True


def test_report_singleton_blocks_flip_ready(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "entities/research-question.md", {"id": "spec:research-question", "kind": "spec", "title": "RQ"})
    report = build_report(project)
    assert report["singleton_count"] == 1 and report["flip_ready"] is False


def test_report_manual_retarget_blocks_flip_ready(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "entities/specs/0001-a.md", {"id": "spec:0001-a", "kind": "spec", "title": "A"})
    _write(project / "doc/ref.md", {"id": "design:0001-r", "kind": "design", "title": "R", "discusses": ["spec:0001-a"]})
    report = build_report(project)
    assert report["manual_retarget_count"] >= 1 and report["flip_ready"] is False


def test_report_oversized_file_forces_scan_incomplete(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    from science_tool.text_scan import MAX_SCANNABLE_BYTES

    (project / "doc/plans").mkdir(parents=True, exist_ok=True)
    (project / "doc/plans/huge.md").write_text("x" * (MAX_SCANNABLE_BYTES + 1), encoding="utf-8")
    report = build_report(project)
    assert report["scan_complete"] is False and report["flip_ready"] is False
    assert any(s["path"] == "doc/plans/huge.md" for s in report["scan_skips"])


def test_report_refuses_unprojectable_legacy_doc(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "A", "date": "2026-01-01", "status": "approved"})
    with pytest.raises(SpecMigrationRefused, match="approved"):
        build_report(project)


def test_migrate_apply_relocates_rewrites_and_leaves_loadable_tree(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha", related=["spec:date-b"])
    _legacy_spec(project, "doc/plans/b.md", "spec:date-b", "Beta")
    (project / "doc/plans/b.md").write_text(
        "---\nid: spec:date-b\ntype: spec\ntitle: Beta\ndate: '2026-01-01'\nstatus: draft\n---\n\nSee [A](a.md).\n", encoding="utf-8"
    )
    _write(project / "doc/ref.md", {"id": "design:0001-r", "kind": "design", "title": "R", "related": ["spec:date-a"]})

    report = migrate(project, apply=True)

    assert not (project / "doc/plans/a.md").exists()
    assert (project / "entities/specs/0001-alpha.md").exists()
    assert (project / "entities/specs/0002-beta.md").exists()

    fm_a, _ = split_frontmatter((project / "entities/specs/0001-alpha.md").read_text(encoding="utf-8"))
    assert fm_a["related"] == ["spec:0002-beta"] and "spec:date-a" in fm_a["aliases"]
    fm_ref, _ = split_frontmatter((project / "doc/ref.md").read_text(encoding="utf-8"))
    assert fm_ref["related"] == ["spec:0001-alpha"]
    assert "0001-alpha.md" in (project / "entities/specs/0002-beta.md").read_text(encoding="utf-8")

    assert not (project / JOURNAL_PATH).exists()
    assert report["legacy_spec_count"] == 0  # recomputed post-apply

    # loadable: the migrated tree builds with its aliases and no AliasCollisionError
    from science_tool.graph.sources import load_project_sources

    ids = {e.id for e in load_project_sources(project).entities}
    assert {"spec:0001-alpha", "spec:0002-beta"} <= ids


def test_migrate_apply_rolls_back_on_injected_claim_failure(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    _legacy_spec(project, "doc/plans/b.md", "spec:date-b", "Beta")

    from science_tool import migrate_specs

    real_claim = migrate_specs.claim_number_in_dir
    calls = {"n": 0}

    def _flaky(*args: object, **kwargs: object):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        return real_claim(*args, **kwargs)  # type: ignore[arg-type]

    with mock.patch.object(migrate_specs, "claim_number_in_dir", _flaky):
        with pytest.raises(OSError, match="disk full"):
            migrate(project, apply=True)

    assert (project / "doc/plans/a.md").exists() and (project / "doc/plans/b.md").exists()
    assert not list((project / "entities/specs").glob("*.md"))
    assert not (project / JOURNAL_PATH).exists()


def test_migrate_apply_rolls_back_on_collision_drift(tmp_path: Path) -> None:
    # a 0001 entity appears at the canonical home between plan and apply -> claim refuses -> rollback
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    from science_tool.entities import EntityCommandError
    from science_tool.migrate_specs import _apply_transaction, _plan_transaction, allocate_ids, discover_specs

    disc = discover_specs(project)
    txn = _plan_transaction(project, disc, allocate_ids(project, disc.legacy))
    _write(project / "entities/specs/0001-drift.md", {"id": "spec:0001-drift", "kind": "spec", "title": "Drift"})  # drift
    with pytest.raises(EntityCommandError):
        _apply_transaction(project, txn)
    assert (project / "doc/plans/a.md").exists()  # source restored
    assert not (project / JOURNAL_PATH).exists()


def test_migrate_refuses_when_journal_exists(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    journal = project / JOURNAL_PATH
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text("{}", encoding="utf-8")
    with pytest.raises(SpecMigrationRefused, match="INTERRUPTED"):
        migrate(project, apply=True)


def test_migrate_apply_refuses_incomplete_scan_before_any_mutation(tmp_path: Path) -> None:
    # an unreadable/oversized reference surface -> scan_complete false -> --apply refuses, writing NOTHING
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    ref = _write(project / "doc/ref.md", {"id": "design:0001-r", "kind": "design", "title": "R", "related": ["spec:date-a"]})
    ref_pre = ref.read_text(encoding="utf-8")
    from science_tool.text_scan import MAX_SCANNABLE_BYTES

    (project / "doc/plans/huge.md").write_text("x" * (MAX_SCANNABLE_BYTES + 1), encoding="utf-8")

    with pytest.raises(SpecMigrationRefused, match="incomplete"):
        migrate(project, apply=True)

    assert (project / "doc/plans/a.md").exists()                    # source untouched
    assert not list((project / "entities/specs").glob("*.md"))      # no destination minted
    assert ref.read_text(encoding="utf-8") == ref_pre               # referrer untouched
    assert not (project / JOURNAL_PATH).exists()                    # no journal written


def _journal(project: Path, entries: list[dict]) -> None:
    journal = project / JOURNAL_PATH
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(_json.dumps({"entries": entries}, indent=2) + "\n", encoding="utf-8")


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_DEST_TEXT = "---\nid: spec:0001-alpha\nkind: spec\ntitle: Alpha\naliases:\n- spec:date-a\ncreated: '2026-01-01'\nupdated: '2026-01-01'\n---\n\nBody.\n"


def test_resume_finishes_interrupted_pass(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    src = _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    src_text = src.read_text(encoding="utf-8")
    ref = _write(project / "doc/ref.md", {"id": "design:0001-r", "kind": "design", "title": "R", "related": ["spec:date-a"]})
    ref_pre = ref.read_text(encoding="utf-8")
    ref_post = ref_pre.replace("spec:date-a", "spec:0001-alpha")
    _journal(project, [
        {"role": "moved-source", "rel": "doc/plans/a.md", "preimage_sha256": _sha(src_text), "postimage": None},
        {"role": "moved-dest", "rel": "entities/specs/0001-alpha.md", "preimage_sha256": None, "postimage": _DEST_TEXT, "number": 1, "local_part": "0001-alpha"},
        {"role": "referrer", "rel": "doc/ref.md", "preimage_sha256": _sha(ref_pre), "postimage": ref_post},
    ])

    resume(project)

    assert not (project / "doc/plans/a.md").exists()
    assert (project / "entities/specs/0001-alpha.md").read_text(encoding="utf-8") == _DEST_TEXT
    assert (project / "doc/ref.md").read_text(encoding="utf-8") == ref_post
    assert not (project / JOURNAL_PATH).exists()


def test_resume_replays_dest_before_source_so_source_survives_claim_failure(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    src = _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    src_text = src.read_text(encoding="utf-8")
    _journal(project, [
        {"role": "moved-source", "rel": "doc/plans/a.md", "preimage_sha256": _sha(src_text), "postimage": None},
        {"role": "moved-dest", "rel": "entities/specs/0001-alpha.md", "preimage_sha256": None, "postimage": _DEST_TEXT, "number": 1, "local_part": "0001-alpha"},
    ])

    from science_tool import migrate_specs

    with mock.patch.object(migrate_specs, "claim_number_in_dir", mock.Mock(side_effect=OSError("boom"))):
        with pytest.raises(OSError, match="boom"):
            resume(project)

    # the source must NOT have been unlinked before the (failed) dest claim
    assert (project / "doc/plans/a.md").read_text(encoding="utf-8") == src_text


def test_resume_refuses_partial_moved_dest_third_state(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    partial = project / "entities/specs/0001-alpha.md"
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text("PARTIAL", encoding="utf-8")
    _journal(project, [{"role": "moved-dest", "rel": "entities/specs/0001-alpha.md", "preimage_sha256": None, "postimage": "FULL", "number": 1, "local_part": "0001-alpha"}])
    with pytest.raises(SpecMigrationRefused, match="neither"):
        resume(project)


def test_resume_clears_sentinel_when_dest_already_committed(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    (project / "entities/specs").mkdir(parents=True, exist_ok=True)
    (project / "entities/specs/0001-alpha.md").write_text(_DEST_TEXT, encoding="utf-8")  # already at postimage
    (project / "entities/specs/.0001.reserving").write_text("", encoding="utf-8")  # dest-committed + sentinel
    _journal(project, [{"role": "moved-dest", "rel": "entities/specs/0001-alpha.md", "preimage_sha256": None, "postimage": _DEST_TEXT, "number": 1, "local_part": "0001-alpha"}])
    resume(project)
    assert not (project / "entities/specs/.0001.reserving").exists()  # cleared at the dest-committed crash point
    assert not (project / JOURNAL_PATH).exists()


def test_resume_reclaims_dest_when_absent_with_sentinel(tmp_path: Path) -> None:
    # the OTHER crash point: sentinel created but the dest was never written. Resume clears the
    # sentinel and re-claims the dest (claim's own `finally` removes the sentinel it re-creates).
    project = _spec_project(tmp_path)
    (project / "entities/specs").mkdir(parents=True, exist_ok=True)
    (project / "entities/specs/.0001.reserving").write_text("", encoding="utf-8")  # dest-absent + sentinel
    _journal(project, [{"role": "moved-dest", "rel": "entities/specs/0001-alpha.md", "preimage_sha256": None, "postimage": _DEST_TEXT, "number": 1, "local_part": "0001-alpha"}])
    resume(project)
    assert (project / "entities/specs/0001-alpha.md").read_text(encoding="utf-8") == _DEST_TEXT
    assert not (project / "entities/specs/.0001.reserving").exists()
    assert not (project / JOURNAL_PATH).exists()


def test_resume_retains_journal_when_post_move_audit_fails(tmp_path: Path) -> None:
    # a NON-empty post-move audit must NOT delete the journal: the operator fixes the tree and re-resumes.
    project = _spec_project(tmp_path)
    src = _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    src_text = src.read_text(encoding="utf-8")
    _journal(project, [
        {"role": "moved-source", "rel": "doc/plans/a.md", "preimage_sha256": _sha(src_text), "postimage": None},
        {"role": "moved-dest", "rel": "entities/specs/0001-alpha.md", "preimage_sha256": None, "postimage": _DEST_TEXT, "number": 1, "local_part": "0001-alpha"},
    ])

    from science_tool import migrate_specs

    with mock.patch.object(migrate_specs, "audit_moved_references", mock.Mock(return_value=["boom"])):
        with pytest.raises(SpecMigrationRefused, match="audit"):
            resume(project)

    assert (project / JOURNAL_PATH).exists()  # retained for a retry


def test_resume_refuses_with_no_journal(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    with pytest.raises(SpecMigrationRefused, match="no interrupted"):
        resume(project)


def test_resume_refuses_stray_sentinel_for_non_journaled_number(tmp_path: Path) -> None:
    project = _spec_project(tmp_path)
    (project / "entities/specs").mkdir(parents=True, exist_ok=True)
    (project / "entities/specs/.0009.reserving").write_text("", encoding="utf-8")
    _journal(project, [{"role": "moved-dest", "rel": "entities/specs/0001-a.md", "preimage_sha256": None, "postimage": "FULL", "number": 1, "local_part": "0001-a"}])
    with pytest.raises(SpecMigrationRefused, match="does not own"):
        resume(project)


def test_cli_json_dry_run_emits_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    monkeypatch.chdir(project)
    result = CliRunner().invoke(entity_group, ["migrate-specs", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = _json.loads(result.output)
    assert payload["flip_ready"] is False and payload["legacy_spec_count"] == 1
    assert list((project / "entities/specs").glob("*.md")) == []


def test_cli_apply_then_flip_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _spec_project(tmp_path)
    _legacy_spec(project, "doc/plans/a.md", "spec:date-a", "Alpha")
    monkeypatch.chdir(project)
    applied = CliRunner().invoke(entity_group, ["migrate-specs", "--apply", "--format", "json"])
    assert applied.exit_code == 0, applied.output
    assert _json.loads(applied.output)["flip_ready"] is True
    assert (project / "entities/specs/0001-alpha.md").exists()


def test_cli_refusal_becomes_click_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _spec_project(tmp_path)
    _write(project / "doc/plans/a.md", {"id": "spec:date-a", "type": "spec", "title": "A", "date": "2026-01-01", "status": "approved"})
    monkeypatch.chdir(project)
    result = CliRunner().invoke(entity_group, ["migrate-specs", "--format", "json"])
    assert result.exit_code != 0 and "approved" in result.output


def test_cli_apply_and_resume_mutually_exclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _spec_project(tmp_path)
    monkeypatch.chdir(project)
    result = CliRunner().invoke(entity_group, ["migrate-specs", "--apply", "--resume"])
    assert result.exit_code != 0 and "mutually exclusive" in result.output


def test_spec_remains_annotation_only() -> None:
    """S3b ships the migration only; the resolution flip is a separate later effort."""
    from science_tool.graph.sources import _ANNOTATION_REF_PREFIXES

    assert _ANNOTATION_REF_PREFIXES == frozenset({"meta", "spec"})
