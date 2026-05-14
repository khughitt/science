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


def test_overlay_adapter_load_malformed_id_raises() -> None:
    from science_tool.commons.errors import OverlayValidationError
    from science_tool.commons.overlay import OverlayAdapter

    root = _OVERLAYS / "proj-alpha"
    with pytest.raises(OverlayValidationError):
        OverlayAdapter(root, "proj-alpha").load("not-a-canonical-id")
