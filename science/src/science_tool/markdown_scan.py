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

_FENCE_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$")
_INLINE_CODE_RE = re.compile(r"(?P<ticks>`+)(?P<body>.+?)(?P=ticks)", re.DOTALL)
_LIST_ITEM_RE = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])\s")
_BLANK_RE = re.compile(r"^\s*$")


def _fenced_line_flags(text: str) -> list[bool]:
    """One flag per line: True where the line is inside (or is) a fence."""
    lines = text.split("\n")
    flags = [False] * len(lines)
    open_fence: str | None = None
    for i, line in enumerate(lines):
        match = _FENCE_RE.match(line)
        if open_fence is None:
            if match is not None:
                open_fence = match.group("fence")
                flags[i] = True
            continue
        flags[i] = True
        # A closing fence must be the same char and at least as long, with no info.
        if (
            match is not None
            and match.group("fence")[0] == open_fence[0]
            and len(match.group("fence")) >= len(open_fence)
            and not match.group("info").strip()
        ):
            open_fence = None
    # An unterminated fence leaves open_fence set; those lines stay masked. Fail
    # closed: we do not know where the code ended, so we do not rewrite past it.
    return flags


def _indented_code_flags(text: str, fenced: list[bool]) -> list[bool]:
    """Lines that are indented code blocks, excluding list-paragraph continuations.

    A 4-space indent under a list item is that item's own paragraph, not code --
    but an indent of 4 or more BEYOND the item's content column IS a code block
    nested inside the item, and masking it is what stops a rewrite from editing a
    fence-free code sample that happens to sit under a bullet. So the threshold is
    relative to the enclosing list item, not the absolute column 4: a single
    `in_list` boolean masked nothing indented under a list, however deep, which
    left an 8-space code block below a bullet fully rewritable.
    """
    lines = text.split("\n")
    flags = [False] * len(lines)
    list_content_indent: int | None = None  # None => not inside a list item
    for i, line in enumerate(lines):
        if fenced[i]:
            continue
        if _BLANK_RE.match(line):
            continue  # a blank line neither starts code nor closes the list item
        item = _LIST_ITEM_RE.match(line)
        if item is not None:
            # Column where the item's content begins (marker + its trailing space).
            list_content_indent = len(item.group(0))
            continue
        indent = len(line) - len(line.lstrip(" "))
        if list_content_indent is not None and indent >= list_content_indent:
            # Inside the current item: code only once indented 4+ past its content.
            flags[i] = indent >= list_content_indent + 4
            continue
        # Dedented out of any list (or never in one): the plain 4-space rule.
        list_content_indent = None
        flags[i] = indent >= 4
    return flags


def prose_spans(text: str) -> list[tuple[int, int]]:
    """Half-open [start, end) offsets of prose, excluding code of every kind."""
    lines = text.split("\n")
    fenced = _fenced_line_flags(text)
    indented = _indented_code_flags(text, fenced)

    masked: list[tuple[int, int]] = []
    offset = 0
    for i, line in enumerate(lines):
        end = offset + len(line)
        if fenced[i] or indented[i]:
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
