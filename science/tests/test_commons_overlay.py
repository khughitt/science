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
