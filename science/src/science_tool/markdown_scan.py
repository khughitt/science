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


def _reference_indent_at_span_start(text: str, index: int) -> int | None:
    """Leading-space count when ``index`` is still in a reference prefix."""
    spaces = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == " ":
        spaces += 1
        if spaces > 3:
            return None
        cursor -= 1
    return spaces if cursor < 0 or text[cursor] == "\n" else None


def _bracket_pairs(
    text: str,
    start: int,
    stop: int,
) -> tuple[dict[int, int], set[int]]:
    """Pair live brackets and identify reference-definition label openers.

    One forward pass handles escaping, nesting, and the at-most-three-space
    reference prefix. Callers can then inspect any opener in O(1), including an
    inner opener whose enclosing bracket group is not itself a link.
    """
    pairs: dict[int, int] = {}
    reference_openers: set[int] = set()
    stack: list[int] = []
    reference_indent = _reference_indent_at_span_start(text, start)
    escaped = False

    cursor = start
    while cursor < stop:
        character = text[cursor]
        if escaped:
            escaped = False
            if character == "\n":
                reference_indent = 0
            cursor += 1
            continue

        if character == "\\":
            escaped = True
            reference_indent = None
        elif character == "\n":
            reference_indent = 0
        elif character == "[":
            if reference_indent is not None:
                reference_openers.add(cursor)
            stack.append(cursor)
            reference_indent = None
        elif character == "]":
            if stack:
                pairs[stack.pop()] = cursor
            reference_indent = None
        elif character == " " and reference_indent is not None:
            reference_indent += 1
            if reference_indent > 3:
                reference_indent = None
        else:
            reference_indent = None
        cursor += 1
    return pairs, reference_openers


def _after_escape(index: int, stop: int) -> int:
    """Skip an escape pair without crossing the current prose span."""
    return min(index + 2, stop)


def _angle_destination(
    text: str,
    start: int,
    stop: int,
) -> tuple[str, int, bool]:
    """Return destination, next offset, and whether the closing ``>`` was found."""
    cursor = start + 1
    while cursor < stop:
        character = text[cursor]
        if character == "\\":
            cursor = _after_escape(cursor, stop)
            continue
        if character == ">":
            return text[start + 1 : cursor].strip(), cursor + 1, True
        if character == "\n":
            break
        cursor += 1
    return text[start + 1 : cursor].strip(), cursor, False


def _title_end(text: str, start: int, stop: int) -> int | None:
    """Offset after one syntactically closed supported Markdown title."""
    delimiter = text[start]
    cursor = start
    if delimiter in {'"', "'"}:
        cursor += 1
        while cursor < stop:
            if text[cursor] == "\\":
                cursor = _after_escape(cursor, stop)
                continue
            if text[cursor] == delimiter:
                cursor += 1
                break
            cursor += 1
        else:
            return None
    elif delimiter == "(":
        depth = 1
        cursor += 1
        while cursor < stop:
            if text[cursor] == "\\":
                cursor = _after_escape(cursor, stop)
                continue
            if text[cursor] == "(":
                depth += 1
            elif text[cursor] == ")":
                depth -= 1
                if depth == 0:
                    cursor += 1
                    break
            cursor += 1
        else:
            return None
    else:
        return None
    return cursor


def _inline_close_after_destination(text: str, start: int, stop: int) -> int | None:
    """Return the offset after an outer ``)`` following whitespace/title."""
    cursor = start
    while cursor < stop and text[cursor].isspace():
        cursor += 1
    if cursor >= stop:
        return None
    if text[cursor] == ")":
        return cursor + 1
    if cursor == start:
        return None

    title_end = _title_end(text, cursor, stop)
    if title_end is None:
        return None
    cursor = title_end
    while cursor < stop and text[cursor].isspace():
        cursor += 1
    return cursor + 1 if cursor < stop and text[cursor] == ")" else None


def _reference_resume_offset(
    text: str,
    destination_end: int,
    line_end: int,
) -> int:
    """Skip only whitespace or one valid attached title after a destination."""
    cursor = destination_end
    while cursor < line_end and text[cursor] in " \t":
        cursor += 1
    if cursor == line_end:
        return line_end
    if cursor == destination_end:
        return destination_end

    title_end = _title_end(text, cursor, line_end)
    if title_end is None:
        return destination_end
    cursor = title_end
    while cursor < line_end and text[cursor] in " \t":
        cursor += 1
    return line_end if cursor == line_end else destination_end


def _inline_destination(
    text: str,
    start: int,
    stop: int,
) -> tuple[str, int] | None:
    cursor = start
    while cursor < stop and text[cursor].isspace():
        cursor += 1
    if cursor >= stop:
        return None

    if text[cursor] == "<":
        destination, after_destination, complete = _angle_destination(
            text,
            cursor,
            stop,
        )
        if not destination:
            return None
        if complete:
            close = _inline_close_after_destination(text, after_destination, stop)
            if close is not None:
                return destination, close
        return destination, after_destination

    destination_start = cursor
    depth = 0
    while cursor < stop:
        character = text[cursor]
        if character == "\\":
            cursor = _after_escape(cursor, stop)
            continue
        if character == "(":
            depth += 1
            cursor += 1
            continue
        if character == ")":
            if depth == 0:
                destination = text[destination_start:cursor]
                return (destination, cursor + 1) if destination else None
            depth -= 1
            cursor += 1
            continue
        if character.isspace() and depth == 0:
            destination = text[destination_start:cursor]
            if not destination:
                return None
            close = _inline_close_after_destination(text, cursor, stop)
            return destination, close if close is not None else cursor
        cursor += 1

    destination = text[destination_start:cursor]
    return (destination, cursor) if destination else None


def _reference_destination(
    text: str,
    start: int,
    stop: int,
) -> tuple[str, int] | None:
    cursor = start
    while cursor < stop and text[cursor] in " \t":
        cursor += 1
    if cursor >= stop or text[cursor] == "\n":
        return None

    line_end = text.find("\n", cursor, stop)
    if line_end == -1:
        line_end = stop
    if text[cursor] == "<":
        destination, after_destination, complete = _angle_destination(
            text,
            cursor,
            line_end,
        )
        if not destination:
            return None
        next_cursor = (
            _reference_resume_offset(text, after_destination, line_end)
            if complete
            else after_destination
        )
        return destination, next_cursor

    destination_start = cursor
    depth = 0
    while cursor < line_end:
        character = text[cursor]
        if character == "\\":
            cursor = _after_escape(cursor, line_end)
            continue
        if character == "(":
            depth += 1
            cursor += 1
            continue
        if character == ")":
            if depth == 0:
                break
            depth -= 1
            cursor += 1
            continue
        if character.isspace() and depth == 0:
            break
        cursor += 1
    destination = text[destination_start:cursor]
    if not destination:
        return None
    return destination, _reference_resume_offset(text, cursor, line_end)


def iter_markdown_destinations(text: str) -> Iterator[str]:
    """Yield source destinations from live Markdown prose.

    This is an intentionally small CommonMark-oriented scanner, not a renderer.
    It pairs escaped/nested brackets once per prose span, then scans forward
    without rescanning label suffixes: within each prose span, destination
    scanning work is linear in the span length plus emitted destination slices.
    It recognises inline links and images with balanced, escaped, or multiline
    labels; reference definitions indented by at most three spaces; angle
    destinations; and ordinary destinations with escaped or balanced
    parentheses. Escaped opening brackets and every existing code mask are
    literal and therefore ignored.

    Reference uses are not resolved because their definition is scanned
    directly. A reference tail is consumed only when it is whitespace or one
    syntactically closed double-quoted, single-quoted, or parenthesized title
    followed by whitespace. Continuation-line reference titles, autolinks, and
    raw HTML are outside this interface. Malformed live syntax yields any safely
    readable destination prefix so callers can fail closed.
    """
    for span_start, span_stop in prose_spans(text):
        bracket_pairs, reference_openers = _bracket_pairs(
            text,
            span_start,
            span_stop,
        )
        cursor = span_start
        while cursor < span_stop:
            end = bracket_pairs.get(cursor)
            if end is None:
                cursor += 1
                continue

            after_label = end + 1
            parsed: tuple[str, int] | None = None
            if (
                cursor in reference_openers
                and after_label < span_stop
                and text[after_label] == ":"
            ):
                parsed = _reference_destination(text, after_label + 1, span_stop)
            elif after_label < span_stop and text[after_label] == "(":
                parsed = _inline_destination(text, after_label + 1, span_stop)

            if parsed is None:
                cursor += 1
                continue
            destination, next_cursor = parsed
            yield destination
            cursor = max(after_label + 1, next_cursor)
