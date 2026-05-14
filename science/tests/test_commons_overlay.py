"""Tests for science_tool.commons.overlay."""
from __future__ import annotations

from pathlib import Path

import pytest


_OVERLAYS = Path(__file__).parent / "fixtures" / "overlays"


def test_read_markdown_body_returns_text_after_frontmatter(tmp_path: Path) -> None:
    from science_tool.commons.overlay import _read_markdown_body

    md = tmp_path / "doc.md"
    md.write_text(
        "---\n"
        "id: \"paper:X\"\n"
        "---\n"
        "\n"
        "# Heading\n"
        "\n"
        "Body text.\n",
        encoding="utf-8",
    )
    body = _read_markdown_body(md)
    assert body == "\n# Heading\n\nBody text.\n"


def test_read_markdown_body_no_frontmatter_returns_whole_file(tmp_path: Path) -> None:
    from science_tool.commons.overlay import _read_markdown_body

    md = tmp_path / "plain.md"
    md.write_text("# Just a heading\n\ntext\n", encoding="utf-8")
    assert _read_markdown_body(md) == "# Just a heading\n\ntext\n"


def test_overlay_adapter_load_hit() -> None:
    from science_tool.commons.overlay import OverlayAdapter, OverlayRecord

    root = _OVERLAYS / "proj-alpha"
    rec = OverlayAdapter(root, "proj-alpha").load("paper:Adams2025")
    assert isinstance(rec, OverlayRecord)
    assert rec.canonical_id == "paper:Adams2025"
    assert rec.type == "paper"
    assert rec.slug == "Adams2025"
    assert rec.project == "proj-alpha"
    assert rec.project_root == root
    assert rec.overlay_path == root / "doc" / "papers" / "Adams2025.md"
    assert rec.frontmatter["relevance"].startswith("H2")
    assert "Project-Specific Notes" in rec.body
    assert rec.pin_version is None
    assert rec.pin_effective_version is None


def test_overlay_adapter_load_miss_returns_none() -> None:
    from science_tool.commons.overlay import OverlayAdapter

    root = _OVERLAYS / "proj-alpha"
    assert OverlayAdapter(root, "proj-alpha").load("paper:NoSuchPaper") is None


def test_overlay_adapter_load_schema_failure_raises_with_cause() -> None:
    from science_tool.commons.errors import OverlayValidationError
    from science_tool.commons.overlay import OverlayAdapter

    root = _OVERLAYS / "proj-broken"
    with pytest.raises(OverlayValidationError) as excinfo:
        OverlayAdapter(root, "proj-broken").load("paper:Adams2025")
    assert excinfo.value.canonical_id == "paper:Adams2025"
    assert excinfo.value.cause is not None


@pytest.mark.parametrize(
    "canonical_id",
    [
        "not-a-canonical-id",
        "paper:",
        "paper:bad/name",
        "paper:Adams2025:extra",
    ],
)
def test_overlay_adapter_load_malformed_id_raises(canonical_id: str) -> None:
    from science_tool.commons.errors import OverlayValidationError
    from science_tool.commons.overlay import OverlayAdapter

    root = _OVERLAYS / "proj-alpha"
    with pytest.raises(OverlayValidationError) as excinfo:
        OverlayAdapter(root, "proj-alpha").load(canonical_id)
    assert excinfo.value.cause is not None
    if ":" in canonical_id:
        assert excinfo.value.canonical_id == canonical_id


def test_overlay_adapter_scan_yields_records() -> None:
    from science_tool.commons.overlay import OverlayAdapter, OverlayRecord

    root = _OVERLAYS / "proj-alpha"
    items = list(OverlayAdapter(root, "proj-alpha").scan())
    assert all(isinstance(i, OverlayRecord) for i in items)
    ids = sorted(i.canonical_id for i in items)
    assert ids == ["dataset:cath-domains", "paper:Adams2025"]


def test_overlay_adapter_scan_yields_errors_for_broken_files() -> None:
    from science_tool.commons.errors import OverlayValidationError
    from science_tool.commons.overlay import OverlayAdapter, OverlayRecord

    root = _OVERLAYS / "proj-broken"
    items = list(OverlayAdapter(root, "proj-broken").scan())
    # proj-broken/doc/papers/Adams2025.md fails the overlay schema;
    # proj-broken/doc/topics/nonexistent-topic.md is schema-valid here
    # (the dangling overlay_of check belongs to validate_project_overlays).
    errors = [i for i in items if isinstance(i, OverlayValidationError)]
    records = [i for i in items if isinstance(i, OverlayRecord)]
    assert len(errors) == 1
    assert errors[0].canonical_id == "paper:Adams2025"
    assert len(records) == 1
    assert records[0].canonical_id == "topic:nonexistent-topic"


def test_overlay_adapter_scan_missing_doc_dir_yields_nothing(tmp_path: Path) -> None:
    from science_tool.commons.overlay import OverlayAdapter

    # tmp_path exists but has no doc/ subtree.
    assert list(OverlayAdapter(tmp_path, "empty-proj").scan()) == []


def _canonical_record(tmp_path: Path, slug: str = "Adams2025"):
    """Copy the commons paper fixture into tmp_path and return its CommonsEntityRecord."""
    import shutil

    from science_tool.commons.adapter import CommonsEntityAdapter

    src = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(src, root)
    return CommonsEntityAdapter(root).load(f"paper:{slug}")


def _merge_policy_for(record):
    from science_model.entity_schema import parse_profile, read_merge_policy

    return read_merge_policy(parse_profile(record.schema_profile))


def test_merge_entity_no_overlay_is_canonical_only(tmp_path: Path) -> None:
    from science_tool.commons.overlay import MergedEntity, merge_entity

    record = _canonical_record(tmp_path)
    merged = merge_entity(record, None, _merge_policy_for(record))
    assert isinstance(merged, MergedEntity)
    assert merged.overlay is None
    assert merged.merged_frontmatter == record.frontmatter
    assert "representative paper" in merged.merged_body
    assert set(merged.field_sources.values()) == {"canonical"}


def test_merge_entity_append_field_dedups_and_orders(tmp_path: Path) -> None:
    from science_tool.commons.overlay import OverlayAdapter, merge_entity

    record = _canonical_record(tmp_path)  # tags == ["evaluation", "homology"]
    overlay = OverlayAdapter(
        _OVERLAYS / "proj-alpha", "proj-alpha"
    ).load("paper:Adams2025")  # tags == ["overlay-added"]
    merged = merge_entity(record, overlay, _merge_policy_for(record))
    assert merged.merged_frontmatter["tags"] == [
        "evaluation",
        "homology",
        "overlay-added",
    ]
    assert merged.field_sources["tags"] == "canonical+overlay"


def test_merge_entity_project_only_field_copied_from_overlay(tmp_path: Path) -> None:
    from science_tool.commons.overlay import OverlayAdapter, merge_entity

    record = _canonical_record(tmp_path)
    overlay = OverlayAdapter(
        _OVERLAYS / "proj-alpha", "proj-alpha"
    ).load("paper:Adams2025")
    merged = merge_entity(record, overlay, _merge_policy_for(record))
    assert merged.merged_frontmatter["hypothesis_links"] == ["H2", "H4"]
    assert merged.merged_frontmatter["relevance"].startswith("H2")
    assert merged.field_sources["hypothesis_links"] == "overlay"
    assert merged.field_sources["relevance"] == "overlay"


def test_merge_entity_body_appends_overlay_sections(tmp_path: Path) -> None:
    from science_tool.commons.overlay import OverlayAdapter, merge_entity

    record = _canonical_record(tmp_path)
    overlay = OverlayAdapter(
        _OVERLAYS / "proj-alpha", "proj-alpha"
    ).load("paper:Adams2025")
    merged = merge_entity(record, overlay, _merge_policy_for(record))
    assert "representative paper" in merged.merged_body
    assert "Project-Specific Notes" in merged.merged_body
    assert merged.merged_body.index("representative paper") < merged.merged_body.index(
        "Project-Specific Notes"
    )


def test_merge_entity_rejects_forbidden_overlay_field(tmp_path: Path) -> None:
    from science_model.entity_schema import MergePolicy

    from science_tool.commons.errors import OverlayMergeError
    from science_tool.commons.overlay import OverlayRecord, merge_entity

    record = _canonical_record(tmp_path)
    # Hand-craft an OverlayRecord that smuggles a `replace`-policy field past
    # validation — exercises the defense-in-depth guard.
    bad = OverlayRecord(
        canonical_id="paper:Adams2025",
        type="paper",
        slug="Adams2025",
        project="x",
        project_root=tmp_path,
        overlay_path=tmp_path / "x.md",
        frontmatter={
            "id": "paper:Adams2025",
            "overlay_of": "paper:Adams2025",
            "title": "smuggled",
        },
        body="",
        pin_version=None,
        pin_effective_version=None,
    )
    policy = _merge_policy_for(record)
    assert policy["title"] == MergePolicy.REPLACE  # sanity
    with pytest.raises(OverlayMergeError, match="title"):
        merge_entity(record, bad, policy)
