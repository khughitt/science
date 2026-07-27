"""Render a BoundaryConfig into the managed .gitignore block, and splice it in.

Pure string transforms; no filesystem access. Two invariants the tests pin:
every generated pattern is anchored, and a manifest root never emits a bare
directory exclude (which would stop git descending and silently disable its own
negations).
"""

from __future__ import annotations

from dataclasses import dataclass

from science_tool.boundary.config import BoundaryConfig, BoundaryRoot, StorageClass

MANAGED_BEGIN = "# BEGIN science-managed boundary — edit science.yaml, not this block"
MANAGED_END = "# END science-managed boundary"


class ManagedBlockError(Exception):
    """Raised when managed-block markers are malformed or ambiguous."""


@dataclass(frozen=True)
class _PhysicalLine:
    number: int
    start: int
    content_end: int
    end: int


@dataclass(frozen=True)
class _ManagedBlockBounds:
    begin: _PhysicalLine
    end: _PhysicalLine


def _render_root(root: BoundaryRoot) -> list[str]:
    if root.storage_class is StorageClass.PAYLOAD:
        return [f"/{root.path}/"]
    # manifest: `**` + directory re-inclusion keeps git descending so the
    # per-glob negations below actually apply.
    lines = [f"/{root.path}/**", f"!/{root.path}/**/"]
    lines.extend(f"!/{root.path}/**/{glob}" for glob in sorted(root.tracked))
    return lines


def render_managed_block(cfg: BoundaryConfig) -> str:
    """Deterministic: roots sorted by path, tracked globs sorted within a root."""
    lines: list[str] = []
    for root in sorted(cfg.roots, key=lambda r: r.path):
        lines.extend(_render_root(root))
    return "".join(f"{line}\n" for line in lines)


def _physical_lines(text: str) -> list[_PhysicalLine]:
    """Return LF-delimited physical lines using Git's terminal-CR semantics."""
    lines: list[_PhysicalLine] = []
    start = 0
    number = 1
    while start < len(text):
        newline = text.find("\n", start)
        raw_end = len(text) if newline == -1 else newline
        end = raw_end if newline == -1 else raw_end + 1
        content_end = raw_end - 1 if raw_end > start and text[raw_end - 1] == "\r" else raw_end
        lines.append(
            _PhysicalLine(
                number=number,
                start=start,
                content_end=content_end,
                end=end,
            )
        )
        if newline == -1:
            break
        start = end
        number += 1
    return lines


def _managed_block_bounds(text: str) -> _ManagedBlockBounds | None:
    lines = _physical_lines(text)
    begins = [line for line in lines if text[line.start : line.content_end] == MANAGED_BEGIN]
    ends = [line for line in lines if text[line.start : line.content_end] == MANAGED_END]
    if not begins and not ends:
        return None
    if not begins:
        raise ManagedBlockError("unmatched END science-managed boundary marker")
    if not ends:
        raise ManagedBlockError("unmatched BEGIN science-managed boundary marker")
    if len(begins) > 1 and len(ends) > 1:
        raise ManagedBlockError("multiple blocks use science-managed boundary markers")
    if len(begins) > 1:
        raise ManagedBlockError("duplicate BEGIN science-managed boundary marker")
    if len(ends) > 1:
        raise ManagedBlockError("duplicate END science-managed boundary marker")

    begin = begins[0]
    end = ends[0]
    if end.start < begin.start:
        raise ManagedBlockError("reversed science-managed boundary markers")
    return _ManagedBlockBounds(begin=begin, end=end)


def managed_block_line_numbers(text: str) -> frozenset[int]:
    """Physical line numbers owned by the one valid root managed block."""
    bounds = _managed_block_bounds(text)
    if bounds is None:
        return frozenset()
    return frozenset(range(bounds.begin.number, bounds.end.number + 1))


def extract_managed_block(text: str) -> str | None:
    """Return the block body between the markers, or None if not present."""
    bounds = _managed_block_bounds(text)
    if bounds is None:
        return None
    return text[bounds.begin.end : bounds.end.start]


def splice_managed_block(text: str, block: str) -> str:
    """Replace the managed block in `text`, or append it if absent."""
    rendered = f"{MANAGED_BEGIN}\n{block}{MANAGED_END}\n"
    bounds = _managed_block_bounds(text)
    if bounds is not None:
        return text[: bounds.begin.start] + rendered + text[bounds.end.end :]
    prefix = text if text.endswith("\n") or not text else text + "\n"
    separator = "\n" if prefix else ""
    return f"{prefix}{separator}{rendered}"
