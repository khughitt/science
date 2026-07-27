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
import string
from collections.abc import Iterator
from dataclasses import dataclass

_FENCE_RE = re.compile(r"^(?P<indent> *)(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$")
# An unbalanced single backtick in prose can pair, via this lazy `.+?` under
# DOTALL, with a later fence delimiter across a block boundary, masking the span
# between them and dropping a live link that follows. That over-masks (safe: the
# result is a stale link the post-move audit surfaces, never a corrupted
# quotation), so it is left as a deliberate gap rather than fixed here.
_INLINE_CODE_RE = re.compile(r"(?P<ticks>`+)(?P<body>.+?)(?P=ticks)", re.DOTALL)
_LIST_ITEM_RE = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])\s")
_BLANK_RE = re.compile(r"^\s*$")
_ESCAPABLE_PUNCTUATION = frozenset(string.punctuation)
_DESTINATION_SCAN_WORK_FACTOR = 4


class MarkdownDestinationScanError(RuntimeError):
    """Destination parsing exceeded the documented per-span work bound."""


@dataclass(frozen=True)
class _ParsedDestination:
    destination: str | None
    suppress_until: int | None
    examined_until: int


@dataclass(frozen=True)
class _ReferenceTail:
    resume: int
    valid: bool
    examined_until: int


@dataclass
class _DestinationScanBudget:
    remaining: int

    def charge(self, start: int, stop: int) -> None:
        self.remaining -= max(0, stop - start)
        if self.remaining < 0:
            raise MarkdownDestinationScanError(
                "Markdown destination scan exceeded its bounded-work limit"
            )


@dataclass(frozen=True)
class _InlineWhitespace:
    end: int
    valid: bool
    consumed: bool


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

        if character == "\\" and _is_valid_escape(text, cursor, stop):
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


def _is_valid_escape(text: str, index: int, stop: int) -> bool:
    return index + 1 < stop and text[index + 1] in _ESCAPABLE_PUNCTUATION


def _is_whitespace_or_control(character: str) -> bool:
    return character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F


def _line_ending_width(text: str, index: int, stop: int) -> int:
    if text[index] == "\n":
        return 1
    if text[index] != "\r":
        return 0
    return 2 if index + 1 < stop and text[index + 1] == "\n" else 1


def _inline_whitespace(text: str, start: int, stop: int) -> _InlineWhitespace:
    """Horizontal whitespace plus at most one CR/LF line ending."""
    cursor = start
    line_endings = 0
    while cursor < stop:
        character = text[cursor]
        if character in " \t":
            cursor += 1
            continue
        width = _line_ending_width(text, cursor, stop)
        if width:
            if line_endings:
                return _InlineWhitespace(cursor, False, cursor > start)
            line_endings += 1
            cursor += width
            continue
        if _is_whitespace_or_control(character):
            return _InlineWhitespace(cursor, False, cursor > start)
        break
    return _InlineWhitespace(cursor, True, cursor > start)


def _angle_destination(
    text: str,
    start: int,
    stop: int,
) -> tuple[str, int, bool]:
    """Return destination, next offset, and whether the closing ``>`` was found."""
    cursor = start + 1
    while cursor < stop:
        character = text[cursor]
        if character == "\\" and _is_valid_escape(text, cursor, stop):
            cursor = _after_escape(cursor, stop)
            continue
        if character == ">":
            return text[start + 1 : cursor], cursor + 1, True
        if (
            character == "<"
            or _line_ending_width(text, cursor, stop)
            or (ord(character) < 0x20 and character != " ")
            or ord(character) == 0x7F
        ):
            break
        cursor += 1
    return text[start + 1 : cursor], cursor, False


def _title_end(text: str, start: int, stop: int) -> int | None:
    """Offset after one syntactically closed supported Markdown title."""
    delimiter = text[start]
    cursor = start
    line_only_horizontal = False
    if delimiter in {'"', "'"}:
        cursor += 1
        while cursor < stop:
            if text[cursor] == "\\" and _is_valid_escape(text, cursor, stop):
                cursor = _after_escape(cursor, stop)
                line_only_horizontal = False
                continue
            if text[cursor] == delimiter:
                cursor += 1
                break
            width = _line_ending_width(text, cursor, stop)
            if width:
                if line_only_horizontal:
                    return None
                line_only_horizontal = True
                cursor += width
                continue
            if _is_whitespace_or_control(text[cursor]) and text[cursor] not in " \t":
                return None
            if text[cursor] not in " \t":
                line_only_horizontal = False
            cursor += 1
        else:
            return None
    elif delimiter == "(":
        cursor += 1
        while cursor < stop:
            if text[cursor] == "\\" and _is_valid_escape(text, cursor, stop):
                cursor = _after_escape(cursor, stop)
                line_only_horizontal = False
                continue
            if text[cursor] == "(":
                return None
            if text[cursor] == ")":
                cursor += 1
                break
            width = _line_ending_width(text, cursor, stop)
            if width:
                if line_only_horizontal:
                    return None
                line_only_horizontal = True
                cursor += width
                continue
            if _is_whitespace_or_control(text[cursor]) and text[cursor] not in " \t":
                return None
            if text[cursor] not in " \t":
                line_only_horizontal = False
            cursor += 1
        else:
            return None
    else:
        return None
    return cursor


def _inline_close_after_destination(text: str, start: int, stop: int) -> int | None:
    """Return the offset after an outer ``)`` following whitespace/title."""
    whitespace = _inline_whitespace(text, start, stop)
    if not whitespace.valid:
        return None
    cursor = whitespace.end
    if cursor >= stop:
        return None
    if text[cursor] == ")":
        return cursor + 1
    if not whitespace.consumed:
        return None

    title_end = _title_end(text, cursor, stop)
    if title_end is None:
        return None
    trailing = _inline_whitespace(text, title_end, stop)
    if not trailing.valid:
        return None
    cursor = trailing.end
    return cursor + 1 if cursor < stop and text[cursor] == ")" else None


def _reference_tail(
    text: str,
    destination_end: int,
    line_end: int,
) -> _ReferenceTail:
    """Validate the whole definition tail and return its safe resume boundary."""
    cursor = destination_end
    while cursor < line_end and text[cursor] in " \t":
        cursor += 1
    if cursor == line_end:
        return _ReferenceTail(line_end, True, line_end)
    if cursor == destination_end:
        return _ReferenceTail(
            destination_end,
            False,
            min(cursor + 1, line_end),
        )

    title_end = _title_end(text, cursor, line_end)
    if title_end is None:
        return _ReferenceTail(destination_end, False, line_end)
    cursor = title_end
    while cursor < line_end and text[cursor] in " \t":
        cursor += 1
    if cursor == line_end:
        return _ReferenceTail(line_end, True, line_end)
    return _ReferenceTail(
        destination_end,
        False,
        min(cursor + 1, line_end),
    )


def _inline_destination(
    text: str,
    start: int,
    stop: int,
) -> _ParsedDestination | None:
    leading = _inline_whitespace(text, start, stop)
    if not leading.valid:
        return None
    cursor = leading.end
    if cursor >= stop:
        return None
    if text[cursor] == ")":
        return _ParsedDestination(None, cursor + 1, cursor + 1)

    if leading.consumed and text[cursor] in {'"', "'", "("}:
        title_end = _title_end(text, cursor, stop)
        if title_end is not None:
            trailing = _inline_whitespace(text, title_end, stop)
            if (
                trailing.valid
                and trailing.end < stop
                and text[trailing.end] == ")"
            ):
                return _ParsedDestination(
                    None,
                    trailing.end + 1,
                    trailing.end + 1,
                )

    if text[cursor] == "<":
        destination, after_destination, complete = _angle_destination(
            text,
            cursor,
            stop,
        )
        if complete:
            close = _inline_close_after_destination(text, after_destination, stop)
            if close is not None:
                return _ParsedDestination(destination or None, close, close)
        return _ParsedDestination(
            destination or None,
            None,
            stop if complete else after_destination,
        )

    destination_start = cursor
    depth = 0
    while cursor < stop:
        character = text[cursor]
        if character == "\\" and _is_valid_escape(text, cursor, stop):
            cursor = _after_escape(cursor, stop)
            continue
        if _is_whitespace_or_control(character):
            destination = text[destination_start:cursor]
            if not destination:
                return None
            if depth == 0:
                close = _inline_close_after_destination(text, cursor, stop)
                return _ParsedDestination(
                    destination,
                    close,
                    close if close is not None else stop,
                )
            return _ParsedDestination(destination, None, cursor)
        if character == "(":
            depth += 1
            cursor += 1
            continue
        if character == ")":
            if depth == 0:
                destination = text[destination_start:cursor]
                return (
                    _ParsedDestination(destination, cursor + 1, cursor + 1)
                    if destination
                    else _ParsedDestination(None, cursor + 1, cursor + 1)
                )
            depth -= 1
            cursor += 1
            continue
        cursor += 1

    destination = text[destination_start:cursor]
    return _ParsedDestination(destination, None, cursor) if destination else None


def _reference_destination(
    text: str,
    start: int,
    stop: int,
) -> _ParsedDestination | None:
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
        if not complete:
            return _ParsedDestination(
                destination or None,
                None,
                after_destination,
            )
        tail = _reference_tail(text, after_destination, line_end)
        return _ParsedDestination(
            destination or None,
            tail.resume if tail.valid else None,
            tail.examined_until,
        )

    destination_start = cursor
    depth = 0
    while cursor < line_end:
        character = text[cursor]
        if character == "\\" and _is_valid_escape(text, cursor, line_end):
            cursor = _after_escape(cursor, line_end)
            continue
        if _is_whitespace_or_control(character):
            break
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
        cursor += 1
    destination = text[destination_start:cursor]
    if not destination:
        return None
    if depth != 0:
        return _ParsedDestination(destination, None, cursor)
    tail = _reference_tail(text, cursor, line_end)
    return _ParsedDestination(
        destination,
        tail.resume if tail.valid else None,
        tail.examined_until,
    )


def iter_markdown_destinations(text: str) -> Iterator[str]:
    """Yield source destinations from live Markdown prose.

    This is an intentionally small CommonMark-oriented scanner, not a renderer.
    It pairs escaped/nested brackets once per prose span, then scans forward
    without rescanning label suffixes: within each prose span, destination
    scanning work is linear in the span length plus emitted destination slices.
    It recognises inline links and images with balanced, escaped, or multiline
    labels; reference definitions indented by at most three spaces; angle
    destinations; and ordinary destinations with escaped or balanced
    parentheses. Ordinary destinations stop at whitespace/control regardless of
    parenthesis depth; angle destinations allow spaces but reject controls, line
    endings, and unescaped ``<``. Only ASCII punctuation is backslash-escapable.
    Escaped opening brackets and every existing code mask are literal and
    therefore ignored.

    Reference uses are not resolved because their definition is scanned
    directly. A reference tail is consumed only when it is whitespace or one
    syntactically closed double-quoted, single-quoted, or parenthesized title
    followed by whitespace; parentheses inside the last form must be escaped.
    Label openers remain scan territory, while parsed destination and valid-title
    ranges are skipped. Incomplete or malformed destination syntax yields a
    safely readable destination prefix for fail-closed classification but does
    not suppress paired inner label openers. Inline component whitespace is
    horizontal plus at most one line ending, titles may span nonblank lines, and
    valid empty/omitted destinations still suppress their syntax and title.
    Angle destination interiors are returned byte-for-byte; surrounding
    component whitespace remains outside the angle brackets. Continuation-line
    reference titles, autolinks, and raw HTML are outside this interface.

    Cumulative destination ranges examined within one prose span are limited to
    four times that span's length. Exceeding that bound raises
    ``MarkdownDestinationScanError`` instead of silently stopping or yielding a
    synthetic destination; callers that require a complete result must consume
    the iterator under that exception boundary.
    """
    for span_start, span_stop in prose_spans(text):
        bracket_pairs, reference_openers = _bracket_pairs(
            text,
            span_start,
            span_stop,
        )
        budget = _DestinationScanBudget(
            (span_stop - span_start) * _DESTINATION_SCAN_WORK_FACTOR
        )
        suppressed_ranges: dict[int, int] = {}
        cursor = span_start
        while cursor < span_stop:
            suppressed_until = suppressed_ranges.get(cursor)
            if suppressed_until is not None:
                cursor = max(cursor + 1, suppressed_until)
                continue

            end = bracket_pairs.get(cursor)
            if end is None:
                cursor += 1
                continue

            after_label = end + 1
            parsed: _ParsedDestination | None = None
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
            budget.charge(after_label + 1, parsed.examined_until)
            if parsed.destination is not None:
                yield parsed.destination
            if parsed.suppress_until is not None:
                suppressed_ranges[after_label] = max(
                    suppressed_ranges.get(after_label, after_label + 1),
                    parsed.suppress_until,
                )
            # Labels remain active scan territory: in CommonMark an inner link
            # makes an enclosing link opener inactive, and the migration gate
            # must still see that inner destination. The registered range begins
            # only after this label, covering parsed syntax/destination/title.
            cursor += 1
