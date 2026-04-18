from __future__ import annotations

from pathlib import Path

from science_tool.big_picture.frontmatter import read_frontmatter


def test_parses_valid_frontmatter(tmp_path: Path) -> None:
    f = tmp_path / "q.md"
    f.write_text('---\nid: "question:q01"\nrelated:\n  - "hypothesis:h1"\n---\nBody text.\n')
    assert read_frontmatter(f) == {"id": "question:q01", "related": ["hypothesis:h1"]}


def test_returns_none_when_no_frontmatter(tmp_path: Path) -> None:
    f = tmp_path / "q.md"
    f.write_text("No frontmatter here.\n")
    assert read_frontmatter(f) is None


def test_returns_none_when_unterminated(tmp_path: Path) -> None:
    f = tmp_path / "q.md"
    f.write_text("---\nid: broken\n(no closing)\n")
    assert read_frontmatter(f) is None


def test_returns_empty_dict_when_frontmatter_is_empty(tmp_path: Path) -> None:
    f = tmp_path / "q.md"
    f.write_text("---\n---\nBody.\n")
    assert read_frontmatter(f) == {}


def test_returns_none_on_invalid_yaml(tmp_path: Path) -> None:
    f = tmp_path / "q.md"
    f.write_text("---\nid: [unclosed\n---\n")
    assert read_frontmatter(f) is None
