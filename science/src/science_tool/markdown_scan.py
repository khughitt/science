# science/src/science_tool/markdown_scan.py
"""Which parts of a markdown document are prose, and which are literal.

A link inside a code fence is a QUOTATION. Rewriting it changes what the
document says; auditing it reports a broken link that was never a link. Both
matter here because a plan corpus is documents about documents: this repository
carries 73 unresolvable .md links inside fences, purely as examples.

Deliberately a scanner and not a CommonMark parser. markdown-it-py would be more
correct, but it is a runtime dependency for one predicate and its inline offsets
need mapping work regardless. The constructs below are the ones this corpus uses.
Unmodelled constructs are listed in the plan's deliberate-gaps section.

The bias is to mask MORE on ambiguity. The two failure modes are not equal: an
unmasked literal is rewritten, silently corrupting a quotation, while a masked
live reference is only left un-rewritten -- a stale link, which the post-move
audit surfaces far more readily than altered prose. Masking is NOT flagging,
though: a reference hidden inside a masked construct is neither rewritten nor
reported, because prose_only manual-hit scanning skips masked regions by design
(so fenced examples do not become per-run noise). That residual -- a genuinely
live reference buried in a code construct -- is listed in the deliberate-gaps
section, not silently assumed away.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

_FENCE_RE = re.compile(r"^(?P<indent> *)(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$")
# An unbalanced single backtick in prose can pair, via this lazy `.+?` under
# DOTALL, with a later fence delimiter across a block boundary, masking the span
# between them and dropping a live link that follows. That over-masks (safe: the
# result is a stale link the post-move audit surfaces, never a corrupted
# quotation), so it is left as a deliberate gap rather than fixed here.
_INLINE_CODE_RE = re.compile(r"(?P<ticks>`+)(?P<body>.+?)(?P=ticks)", re.DOTALL)
_LIST_ITEM_RE = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])\s")
_BLANK_RE = re.compile(r"^\s*$")


def _block_code_flags(text: str) -> list[bool]:
    """One flag per line: True where the line is block code (fenced or indented).

    Fence and indented-code detection are folded into ONE list-context-aware pass
    because the two rules share a baseline: inside a list item whose content
    begins at column C, a fenced code block may be indented C..C+3 and an indented
    code block begins at C+4. At the top level C=0, recovering the plain 0-3 fence
    / 4-space code rules. Detecting fences independently of the list context (the
    prior split, where only the indented pass tracked the list) missed a fence
    indented AT a list item's content column: recognised by neither mechanism, its
    content leaked into prose.
    """
    lines = text.split("\n")
    flags = [False] * len(lines)
    open_fence: str | None = None
    fence_base_indent = 0
    list_content_indent = 0  # 0 => top level (not inside a list item)
    for i, line in enumerate(lines):
        match = _FENCE_RE.match(line)
        indent = len(line) - len(line.lstrip(" "))

        if open_fence is not None:
            # Opaque fence body: mask, and only look for the matching close.
            flags[i] = True
            if (
                match is not None
                and match.group("fence")[0] == open_fence[0]
                and len(match.group("fence")) >= len(open_fence)
                and not match.group("info").strip()
                and indent - fence_base_indent <= 3
            ):
                open_fence = None
            continue

        if _BLANK_RE.match(line):
            continue  # a blank line neither starts code nor closes the list item

        item = _LIST_ITEM_RE.match(line)
        if item is not None:
            # Column where the item's content begins (marker + its trailing space).
            list_content_indent = len(item.group(0))
            continue

        if indent < list_content_indent:
            # Dedented out of the list: fall back to the plain top-level rules.
            list_content_indent = 0

        if (
            match is not None
            and list_content_indent <= indent <= list_content_indent + 3
        ):
            # A fence opens at the list content baseline (C..C+3); C..C is exactly
            # the column the prior fence pass could not see.
            open_fence = match.group("fence")
            fence_base_indent = list_content_indent
            flags[i] = True
            continue

        # Indented code begins 4 columns past the list content baseline.
        flags[i] = indent >= list_content_indent + 4
    # An unterminated fence leaves open_fence set; those lines stay masked. Fail
    # closed: we do not know where the code ended, so we do not rewrite past it.
    return flags


def prose_spans(text: str) -> list[tuple[int, int]]:
    """Half-open [start, end) offsets of prose, excluding code of every kind."""
    lines = text.split("\n")
    block_code = _block_code_flags(text)

    masked: list[tuple[int, int]] = []
    offset = 0
    for i, line in enumerate(lines):
        end = offset + len(line)
        if block_code[i]:
            masked.append((offset, end))
        offset = end + 1  # the "\n"

    # Inline code, but only where the line survived block masking.
    for match in _INLINE_CODE_RE.finditer(text):
        if not any(start <= match.start() < stop for start, stop in masked):
            masked.append((match.start(), match.end()))

    masked.sort()
    spans: list[tuple[int, int]] = []
    cursor = 0
    for start, stop in masked:
        if start > cursor:
            spans.append((cursor, start))
        cursor = max(cursor, stop)
    if cursor < len(text):
        spans.append((cursor, len(text)))
    return spans


def iter_prose_matches(pattern: re.Pattern[str], text: str) -> Iterator[re.Match[str]]:
    """Matches of `pattern` lying ENTIRELY within prose.

    Entirely, not merely starting there: a match that runs from prose into a code
    span is not a construct either reading recognises, and rewriting half of it
    would corrupt both.
    """
    spans = prose_spans(text)
    for match in pattern.finditer(text):
        if any(start <= match.start() and match.end() <= stop for start, stop in spans):
            yield match
