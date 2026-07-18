from __future__ import annotations

from pathlib import Path

from science_tool.validate.context import ValidateContext


def _ctx(root: Path) -> ValidateContext:
    (root / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def test_body_returns_content_after_frontmatter(tmp_path: Path):
    p = tmp_path / "e.md"
    p.write_text('---\nkind: plan\nstatus: "draft"\n---\n\nHello `src/a.py`.\n', encoding="utf-8")
    assert _ctx(tmp_path).body(p) == "\nHello `src/a.py`.\n"


def test_body_of_a_file_without_frontmatter_is_the_whole_text(tmp_path: Path):
    p = tmp_path / "e.md"
    p.write_text("no frontmatter here\n", encoding="utf-8")
    assert _ctx(tmp_path).body(p) == "no frontmatter here\n"


def test_frontmatter_still_parses(tmp_path: Path):
    p = tmp_path / "e.md"
    p.write_text('---\nkind: plan\nstatus: "draft"\n---\n\nBody\n', encoding="utf-8")
    assert _ctx(tmp_path).frontmatter(p) == {"kind": "plan", "status": "draft"}
