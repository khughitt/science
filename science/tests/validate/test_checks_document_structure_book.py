from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.document_structure import check_document_structure
from science_tool.validate.context import ValidateContext


def _project(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )


def _write_book(tmp_path: Path, body: str) -> None:
    d = tmp_path / "entities" / "books"
    d.mkdir(parents=True, exist_ok=True)
    (d / "Kelly1982.md").write_text(
        '---\nid: "book:Kelly1982"\ntype: book\nstatus: active\n---\n# Book\n' + body,
        encoding="utf-8",
    )


def test_book_missing_section_is_flagged(tmp_path: Path) -> None:
    _project(tmp_path)
    _write_book(tmp_path, "\n## Overview\n\ntext\n")  # missing the other 6 sections
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_document_structure(ctx))
    assert any("missing section: ## Whole-Book Synthesis" in str(r.message) for r in results)


def test_book_with_all_sections_has_no_missing_warning(tmp_path: Path) -> None:
    _project(tmp_path)
    sections = (
        "## Overview",
        "## Whole-Book Synthesis",
        "## Chapter Map",
        "## Key Themes",
        "## Relevance",
        "## Limitations",
        "## Follow-up",
    )
    _write_book(tmp_path, "\n" + "\n\ntext\n".join(sections) + "\n\ntext\n")
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_document_structure(ctx))
    assert not any("missing section" in str(r.message) for r in results)
