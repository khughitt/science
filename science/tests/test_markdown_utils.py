"""Shared markdown lexical helpers."""
from pathlib import Path

from science_tool.markdown_utils import (
    frontmatter_line_numbers,
    is_fence_line,
    strip_inline_code,
)


def test_strip_inline_code_removes_backticked_spans() -> None:
    assert strip_inline_code("plain `code` rest") == "plain  rest"


def test_strip_inline_code_leaves_bare_text() -> None:
    assert strip_inline_code("no code here") == "no code here"


def test_strip_inline_code_handles_multiple_spans() -> None:
    assert strip_inline_code("a `b` c `d` e") == "a  c  e"


def test_is_fence_line_triple_backtick() -> None:
    assert is_fence_line("```")
    assert is_fence_line("```python")
    assert is_fence_line("    ```")


def test_is_fence_line_tilde_fence() -> None:
    assert is_fence_line("~~~")


def test_is_fence_line_rejects_inline_backtick() -> None:
    assert not is_fence_line("plain `inline` text")


def test_frontmatter_line_numbers_basic(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("---\ntitle: foo\n---\n\nbody line\n")
    assert frontmatter_line_numbers(p) == {1, 2, 3}


def test_frontmatter_line_numbers_no_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("# heading\nbody\n")
    assert frontmatter_line_numbers(p) == set()


def test_frontmatter_line_numbers_unterminated(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("---\ntitle: foo\nno closing fence\n")
    assert frontmatter_line_numbers(p) == set()
