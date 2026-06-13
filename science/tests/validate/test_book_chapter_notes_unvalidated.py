from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.document_structure import check_document_structure
from science_tool.validate.checks.entity_conformance import (
    check_entity_frontmatter_completeness,
    check_entity_location_coherence,
)
from science_tool.validate.context import ValidateContext


def _project_with_chapter_note(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    d = tmp_path / "doc" / "books" / "Kelly1982"
    d.mkdir(parents=True, exist_ok=True)
    # Lightweight chapter note: provenance frontmatter, but NO registered `type:`.
    (d / "ch01-intro.md").write_text(
        "---\nbook: Kelly1982\nchapter: 1\npages: '1-24'\n---\n"
        "## Summary\n\ntext\n## Key Concepts\n\ntext\n",
        encoding="utf-8",
    )


def test_chapter_note_raises_no_validation_warnings(tmp_path: Path) -> None:
    _project_with_chapter_note(tmp_path)
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = (
        list(check_document_structure(ctx))
        + list(check_entity_frontmatter_completeness(ctx))
        + list(check_entity_location_coherence(ctx))
    )
    offenders = [r for r in results if "ch01-intro" in str(r.path) and r.severity.name != "INFO"]
    assert offenders == [], f"chapter note should not be validated, got: {offenders}"
