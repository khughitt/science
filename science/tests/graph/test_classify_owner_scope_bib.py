from __future__ import annotations

from science_tool.graph.identity_table import classify_owner_scope


def test_classify_owner_scope_bib_is_non_deprecated_authority() -> None:
    assert classify_owner_scope("bib", project_name="demo") == ("bib", False)


def test_classify_owner_scope_markdown_unchanged() -> None:
    assert classify_owner_scope("markdown", project_name="demo") == ("demo", False)
