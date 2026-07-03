"""Shared markdown lexical helpers used by refs.py and markers.py.

Centralizes fenced-block detection, inline-code stripping, and frontmatter
line accounting so the two scanners agree on what counts as "in prose"
versus "in code/documentation".
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_INLINE_CODE_RE = re.compile(r"(`+)[\s\S]*?\1")


class UnterminatedHtmlCommentError(ValueError):
    """Raised when rendered-prose scanning encounters an unclosed HTML comment."""

    def __init__(self, offset: int) -> None:
        self.offset = offset
        super().__init__(f"unterminated HTML comment starting at character {offset}")


def is_fence_line(line: str) -> bool:
    """Return True if the line opens or closes a fenced code block."""
    return _FENCE_RE.match(line) is not None


def fence_marker(line: str) -> tuple[str, int, str] | None:
    """Return fenced-code marker character, length, and trailing text."""
    match = _FENCE_RE.match(line)
    if match is None:
        return None
    marker = match.group(1)
    return marker[0], len(marker), match.group(2)


def strip_inline_code(text: str) -> str:
    """Remove backticked inline-code spans from text.

    Used to exclude tokens-as-documentation (e.g., `[UNVERIFIED]` discussed
    in prose about the convention itself) from prose-level scanning.
    """
    return _INLINE_CODE_RE.sub("", text)


def _strip_comments_and_inline_code(text: str, *, preserve_inline_code: bool) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith("<!--", index):
            end = text.find("-->", index + 4)
            if end == -1:
                raise UnterminatedHtmlCommentError(index)
            out.extend(char for char in text[index : end + 3] if char == "\n")
            index = end + 3
            continue
        if text[index] == "`" and not _is_escaped(text, index):
            end = index + 1
            while end < len(text) and text[end] == "`":
                end += 1
            delimiter = text[index:end]
            close = _find_unescaped(text, delimiter, end)
            if close != -1:
                span = text[index : close + len(delimiter)]
                if preserve_inline_code:
                    out.append(span)
                else:
                    out.extend(char for char in span if char == "\n")
                index = close + len(delimiter)
                continue
        out.append(text[index])
        index += 1
    return "".join(out)


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def _find_unescaped(text: str, needle: str, start: int) -> int:
    cursor = start
    while True:
        found = text.find(needle, cursor)
        if found == -1:
            return -1
        if not _is_escaped(text, found):
            return found
        cursor = found + len(needle)


def strip_html_comments_and_inline_code(text: str) -> str:
    """Remove rendered-prose comments and inline-code spans from text."""
    return _strip_comments_and_inline_code(text, preserve_inline_code=False)


def strip_html_comments(text: str) -> str:
    """Remove balanced HTML comments from rendered-prose text.

    Stray ``-->`` tokens outside comment mode are visible prose and are preserved.
    An unclosed ``<!--`` fails closed because treating the rest of the file as a
    comment would hide real citations from validation.
    """
    out: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("<!--", index)
        if start == -1:
            out.append(text[index:])
            break
        out.append(text[index:start])
        end = text.find("-->", start + 4)
        if end == -1:
            raise UnterminatedHtmlCommentError(start)
        out.extend(char for char in text[start : end + 3] if char == "\n")
        index = end + 3
    return "".join(out)


def strip_html_comments_preserving_code(markdown: str) -> str:
    """Remove HTML comments from displayed Markdown while keeping code verbatim.

    Fenced-code delimiters and their contents pass through unchanged; within
    non-fenced regions, inline-code spans are protected before comment removal.
    Used for exported prose text, not the citation scan.
    """
    result: list[str] = []
    buffer: list[str] = []
    fence: tuple[str, int] | None = None

    def flush() -> None:
        if not buffer:
            return
        block = "\n".join(buffer)
        buffer.clear()
        result.append(_strip_comments_and_inline_code(block, preserve_inline_code=True))

    for line in markdown.splitlines():
        marker = fence_marker(line)
        if fence is None and marker is not None:
            flush()
            result.append(line)
            fence = (marker[0], marker[1])
            continue
        if fence is not None:
            result.append(line)
            if marker is not None and marker[0] == fence[0] and marker[1] >= fence[1] and not marker[2].strip():
                fence = None
            continue
        buffer.append(line)
    flush()
    return "\n".join(result)


def strip_fenced_code(markdown: str) -> str:
    """Remove fenced-code blocks while preserving line positions."""
    result: list[str] = []
    fence: tuple[str, int] | None = None
    for line in markdown.splitlines():
        marker = fence_marker(line)
        if fence is None and marker is not None:
            result.append("")
            fence = (marker[0], marker[1])
            continue
        if fence is not None:
            result.append("")
            if marker is not None and marker[0] == fence[0] and marker[1] >= fence[1] and not marker[2].strip():
                fence = None
            continue
        result.append(line)
    return "\n".join(result)


def rendered_prose(markdown: str) -> str:
    """Return Markdown text visible to prose-level scanners."""
    return strip_html_comments_and_inline_code(strip_fenced_code(markdown))


def frontmatter_line_numbers(path: Path) -> set[int]:
    """Return the 1-based line numbers occupied by the YAML frontmatter block.

    Returns an empty set when the file has no frontmatter or the block is
    unterminated. Callers use this to skip frontmatter during prose scans.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return set()
    if not lines or lines[0].strip() != "---":
        return set()
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return set(range(1, index + 1))
    return set()


def parse_frontmatter(path: Path) -> tuple[dict, int]:
    """Return ``(frontmatter_data, body_start_line)`` for a markdown file.

    `body_start_line` is the 1-based line number of the first body line
    (or 1 if the file has no parseable frontmatter).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ({}, 1)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ({}, 1)
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            yaml_block = "\n".join(lines[1 : index - 1])
            try:
                data = yaml.safe_load(yaml_block) or {}
            except yaml.YAMLError:
                return ({}, 1)
            if not isinstance(data, dict):
                return ({}, 1)
            return (data, index + 1)
    return ({}, 1)
