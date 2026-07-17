# science/tests/test_markdown_scan.py
"""Prose vs literal: a link in a code fence is a quotation, not a reference."""
from __future__ import annotations

import re

from science_tool.markdown_scan import iter_prose_matches, prose_spans

LINK = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)\)")


def _targets(text: str) -> list[str]:
    return [m.group("target") for m in iter_prose_matches(LINK, text)]


def test_plain_prose_link_is_matched() -> None:
    assert _targets("See [x](./a.md) here.\n") == ["./a.md"]


def test_fenced_block_link_is_not_matched() -> None:
    text = "Before.\n\n```python\nlink = \"[x](./nope.md)\"\n```\n\nAfter [y](./b.md).\n"

    assert _targets(text) == ["./b.md"]


def test_tilde_fence_is_honoured() -> None:
    text = "~~~\n[x](./nope.md)\n~~~\n\n[y](./b.md)\n"

    assert _targets(text) == ["./b.md"]


def test_fence_with_info_string_is_honoured() -> None:
    text = "```markdown title=example\n[x](./nope.md)\n```\n[y](./b.md)\n"

    assert _targets(text) == ["./b.md"]


def test_longer_fence_is_not_closed_by_a_shorter_one() -> None:
    """A ```` fence survives an inner ``` line -- nested-fence examples are real."""
    text = "````\n```\n[x](./nope.md)\n```\n````\n\n[y](./b.md)\n"

    assert _targets(text) == ["./b.md"]


def test_indented_code_block_is_not_matched() -> None:
    text = "Before.\n\n    [x](./nope.md)\n\nAfter [y](./b.md).\n"

    assert _targets(text) == ["./b.md"]


def test_list_continuation_is_not_an_indented_code_block() -> None:
    """4-space indent under a list item is prose, not code; over-masking loses live refs."""
    text = "- item\n\n    See [y](./b.md) for detail.\n"

    assert _targets(text) == ["./b.md"]


def test_code_block_nested_in_a_list_item_is_not_prose() -> None:
    """4+ spaces PAST the item's content column is a code block, not continuation.

    Regression for the single-`in_list`-boolean bug: this 8-space block sits under
    a `- ` item (content column 2), so its threshold is 6; 8 >= 6 masks it.
    """
    text = "- item\n\n        [x](./nope.md)\n\nAfter [y](./b.md).\n"

    assert _targets(text) == ["./b.md"]


def test_deeply_indented_link_under_a_numbered_item_is_masked() -> None:
    """`1. ` content column is 3; an 8-space link clears the +4 code threshold."""
    text = "1. step\n\n        link = \"[x](./nope.md)\"\n"

    assert _targets(text) == []


def test_inline_code_link_is_not_matched() -> None:
    text = "Write `[x](./nope.md)` to link. Real: [y](./b.md).\n"

    assert _targets(text) == ["./b.md"]


def test_inline_code_with_double_backticks() -> None:
    text = "Use ``[x](./nope.md)`` here. Real: [y](./b.md).\n"

    assert _targets(text) == ["./b.md"]


def test_unterminated_fence_masks_to_end_of_document() -> None:
    """Fail closed: an unclosed fence means we do not know where code ends."""
    text = "Before [y](./b.md).\n\n```\n[x](./nope.md)\n"

    assert _targets(text) == ["./b.md"]


def test_tilde_fence_indented_under_numbered_item_is_masked() -> None:
    """F1 regression: a ~~~ fence at a numbered list item's content column masks."""
    text = "10. step\n\n    ~~~\n    [x](./nope.md)\n    ~~~\n\nAfter [y](./b.md).\n"
    assert _targets(text) == ["./b.md"]


def test_tilde_fence_indented_under_nested_bullet_is_masked() -> None:
    """F1 regression: fence at a nested-bullet content column, not via accidental backtick pairing."""
    text = "- outer\n\n  - inner\n\n    ~~~\n    [x](./nope.md)\n    ~~~\n\nAfter [y](./b.md).\n"
    assert _targets(text) == ["./b.md"]


def test_prose_spans_cover_prose_and_exclude_code() -> None:
    text = "a [x](./a.md)\n```\ncode\n```\nb\n"
    spans = prose_spans(text)

    joined = "".join(text[s:e] for s, e in spans)
    assert "code" not in joined
    assert "[x](./a.md)" in joined
    assert "b" in joined


def test_scans_this_repositorys_own_plan_corpus() -> None:
    """The regression that fixtures cannot state: 73 fenced example links live here.

    This plan document contains ./nope.md inside its own Python fences as test
    fixture data. If the scanner sees them, the audit fails on every import.
    """
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3] / "natural-systems"
    if not repo.exists():  # upstream CI has no consumer checkout
        return
    doc = repo / "doc/plans/2026-07-17-plan-corpus-curation-upstream-capabilities-plan.md"
    if not doc.exists():
        return

    targets = _targets(doc.read_text(encoding="utf-8"))

    assert "./nope.md" not in targets, "fenced fixture link leaked into the prose scan"
    assert "./never-existed.md" not in targets
