"""LintIssue.match field is populated correctly by all four detectors."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.prose_lint import (
    LintIssue,
    detect_bare_author_year,
    detect_frontmatter_inline_gaps,
    detect_numeric_anchor,
    detect_short_form_ids,
)


def test_lint_issue_match_is_required() -> None:
    """match is required (no default) so detectors cannot forget it."""
    with pytest.raises(TypeError):
        LintIssue(  # type: ignore[call-arg]
            file=Path("x.md"),
            line=1,
            col=1,
            check="bare-author-year",
            severity="warn",
            message="msg",
        )


def test_bare_author_year_match_value(tmp_path: Path) -> None:
    md = tmp_path / "f.md"
    md.write_text("Some background. Brunton 2022 wrote about modes.\n")
    issues = detect_bare_author_year(md)
    assert len(issues) == 1
    assert issues[0].match == "Brunton 2022"


def test_short_form_ids_match_value(tmp_path: Path) -> None:
    md = tmp_path / "f.md"
    md.write_text("Bare reference: h04 needs canonicalization.\n")
    issues = detect_short_form_ids(md)
    assert len(issues) == 1
    assert issues[0].match == "h04"


def test_numeric_anchor_match_value(tmp_path: Path) -> None:
    md = tmp_path / "f.md"
    md.write_text("Some discovery rate of 42% was claimed here.\n")
    issues = detect_numeric_anchor(md, anchor_patterns=[])
    assert len(issues) >= 1
    assert any(i.match == "42%" for i in issues)


def test_frontmatter_inline_gap_match_value(tmp_path: Path) -> None:
    md = tmp_path / "f.md"
    md.write_text(
        "---\nrelated:\n  - hypothesis:h99-missing\n---\nBody text.\n"
    )
    issues = detect_frontmatter_inline_gaps(md)
    assert len(issues) == 1
    assert issues[0].match == "hypothesis:h99-missing"
