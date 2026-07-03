"""Shared markdown lexical helpers used by refs.py and markers.py.

Centralizes fenced-block detection, inline-code stripping, and frontmatter
line accounting so the two scanners agree on what counts as "in prose"
versus "in code/documentation".
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE_RE = re.compile(r"(`+).*?\1")


class UnterminatedHtmlCommentError(ValueError):
    """Raised when rendered-prose scanning encounters an unclosed HTML comment."""

    def __init__(self, offset: int) -> None:
        self.offset = offset
        super().__init__(f"unterminated HTML comment starting at character {offset}")


def is_fence_line(line: str) -> bool:
    """Return True if the line opens or closes a fenced code block."""
    return _FENCE_RE.match(line) is not None


def strip_inline_code(line: str) -> str:
    """Remove backticked inline-code spans from a line.

    Used to exclude tokens-as-documentation (e.g., `[UNVERIFIED]` discussed
    in prose about the convention itself) from prose-level scanning.
    """
    return _INLINE_CODE_RE.sub("", line)


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
    in_fence = False

    def flush() -> None:
        if not buffer:
            return
        block = "\n".join(buffer)
        buffer.clear()
        stash: list[str] = []

        def _protect(match: re.Match[str]) -> str:
            stash.append(match.group(0))
            return f"\x00{len(stash) - 1}\x00"

        protected = _INLINE_CODE_RE.sub(_protect, block)
        stripped = strip_html_comments(protected)
        restored = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], stripped)
        result.append(restored)

    for line in markdown.splitlines():
        if is_fence_line(line):
            flush()
            result.append(line)
            in_fence = not in_fence
            continue
        if in_fence:
            result.append(line)
            continue
        buffer.append(line)
    flush()
    return "\n".join(result)


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
