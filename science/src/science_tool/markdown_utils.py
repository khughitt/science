"""Shared markdown lexical helpers used by refs.py and markers.py.

Centralizes fenced-block detection, inline-code stripping, and frontmatter
line accounting so the two scanners agree on what counts as "in prose"
versus "in code/documentation".
"""

from __future__ import annotations

import re
from pathlib import Path

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


def is_fence_line(line: str) -> bool:
    """Return True if the line opens or closes a fenced code block."""
    return _FENCE_RE.match(line) is not None


def strip_inline_code(line: str) -> str:
    """Remove backticked inline-code spans from a line.

    Used to exclude tokens-as-documentation (e.g., `[UNVERIFIED]` discussed
    in prose about the convention itself) from prose-level scanning.
    """
    return _INLINE_CODE_RE.sub("", line)


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
