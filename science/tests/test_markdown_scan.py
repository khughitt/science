# science/tests/test_markdown_scan.py
"""Prose vs literal: a link in a code fence is a quotation, not a reference."""
from __future__ import annotations

import re

import pytest

from science_tool import markdown_scan
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


def test_markdown_destinations_support_complex_inline_links_and_images() -> None:
    text = (
        "See [outer [inner]](../docs/nested.md), "
        r"[escaped \] label](../docs/escaped-label.md), and "
        "[multi\nline](../docs/multiline.md).\n"
        "![plot [preview]](images/plot(2).png) or "
        r"[escaped parens](../docs/part\(one\).md)."
    )

    assert list(markdown_scan.iter_markdown_destinations(text)) == [
        "../docs/nested.md",
        "../docs/escaped-label.md",
        "../docs/multiline.md",
        "images/plot(2).png",
        r"../docs/part\(one\).md",
    ]


def test_markdown_destinations_support_complex_reference_definitions() -> None:
    text = (
        "[nested [reference]]: ./nested-ref.md\n"
        r"[escaped \] reference]: <../reference files/escaped.md>" "\n"
    )

    assert list(markdown_scan.iter_markdown_destinations(text)) == [
        "./nested-ref.md",
        "../reference files/escaped.md",
    ]


@pytest.mark.parametrize(
    ("first_destination", "live_destination"),
    [
        ("https://example.test", "external-tail.md"),
        ("/root.md", "root-tail.md"),
        ("#anchor", "anchor-tail.md"),
    ],
)
def test_invalid_reference_tail_does_not_hide_later_inline_destination(
    first_destination: str,
    live_destination: str,
) -> None:
    text = (
        f"[ref]: {first_destination} trailing "
        f"[live]({live_destination})\n"
    )

    assert list(markdown_scan.iter_markdown_destinations(text)) == [
        first_destination,
        live_destination,
    ]


@pytest.mark.parametrize(
    "title",
    [
        '"title [literal](double-quoted.md)"',
        "'title [literal](single-quoted.md)'",
        r"(title \(escaped\) [literal]\(hidden.md\))",
    ],
)
def test_valid_reference_title_hides_link_like_title_text(title: str) -> None:
    text = f"[ref]: https://example.test {title}   \n"

    assert list(markdown_scan.iter_markdown_destinations(text)) == [
        "https://example.test",
    ]


def test_nested_parentheses_invalidate_reference_title_and_expose_inner_link() -> None:
    text = (
        "[ref]: https://example.test "
        "(title [literal](parenthesized.md))\n"
    )

    assert list(markdown_scan.iter_markdown_destinations(text)) == [
        "https://example.test",
        "parenthesized.md",
    ]


@pytest.mark.parametrize("outer_prefix", ["", "!"])
@pytest.mark.parametrize(
    "outer_destination",
    ["https://example.test", "/root.md", "#anchor"],
)
def test_nested_link_in_outer_label_is_scanned(
    outer_prefix: str,
    outer_destination: str,
) -> None:
    text = (
        f"{outer_prefix}[outer [inner](nested.md)]"
        f"({outer_destination})"
    )

    assert list(markdown_scan.iter_markdown_destinations(text)) == [
        outer_destination,
        "nested.md",
    ]


def test_nested_label_scan_excludes_outer_destination_and_valid_title() -> None:
    outer_destination = "https://example.test/[destination](hidden.md)"
    text = (
        "[outer [inner](nested.md)]"
        f"(<{outer_destination}> "
        '"title [literal](hidden-title.md)")'
    )

    assert list(markdown_scan.iter_markdown_destinations(text)) == [
        outer_destination,
        "nested.md",
    ]


def test_markdown_destinations_ignore_escaped_literals_and_code() -> None:
    text = (
        r"\[literal](escaped-literal.md)" "\n"
        r"!\[literal image](escaped-image.png)" "\n"
        r"\[literal reference]: escaped-reference.md" "\n"
        "`[inline code](inline-code.md)`\n"
        "```markdown\n"
        "[fenced](fenced.md)\n"
        "[fenced-ref]: fenced-ref.md\n"
        "```\n"
        "[live](live.md)\n"
    )

    assert list(markdown_scan.iter_markdown_destinations(text)) == ["live.md"]


def test_markdown_destinations_fail_closed_on_unclosed_live_destination() -> None:
    text = "[live](../ambiguous.md\n" r"\[literal](../escaped.md"

    assert list(markdown_scan.iter_markdown_destinations(text)) == [
        "../ambiguous.md",
    ]


def test_markdown_destination_prefix_never_crosses_a_code_mask() -> None:
    text = "[ambiguous](../prefix\\`code`suffix.md)"

    assert list(markdown_scan.iter_markdown_destinations(text)) == [
        "../prefix\\",
    ]


def test_nested_inner_link_is_found_when_outer_bracket_group_is_not_a_link() -> None:
    text = "[outer [inner](nested.md) suffix]"

    assert list(markdown_scan.iter_markdown_destinations(text)) == ["nested.md"]


class _CountingText(str):
    indexed_reads = 0

    def __getitem__(self, key: object) -> str:
        if isinstance(key, int):
            self.indexed_reads += 1
        return super().__getitem__(key)  # type: ignore[call-overload]


def test_deeply_nested_non_link_brackets_have_linear_scanner_work() -> None:
    text = _CountingText("[" * 512 + "label" + "]" * 512)

    assert list(markdown_scan.iter_markdown_destinations(text)) == []
    assert text.indexed_reads <= 4 * len(text)


def test_deeply_nested_link_labels_preserve_linear_work_and_inner_detection() -> None:
    value = "[inner](nested.md)"
    for _ in range(128):
        value = f"[outer {value}](https://example.test)"
    text = _CountingText(value)

    assert list(markdown_scan.iter_markdown_destinations(text)) == [
        *(["https://example.test"] * 128),
        "nested.md",
    ]
    assert text.indexed_reads <= 8 * len(text)


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
