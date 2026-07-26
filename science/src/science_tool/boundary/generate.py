"""Render a BoundaryConfig into the managed .gitignore block, and splice it in.

Pure string transforms; no filesystem access. Two invariants the tests pin:
every generated pattern is anchored, and a manifest root never emits a bare
directory exclude (which would stop git descending and silently disable its own
negations).
"""

from __future__ import annotations

from science_tool.boundary.config import BoundaryConfig, BoundaryRoot, StorageClass

MANAGED_BEGIN = "# BEGIN science-managed boundary — edit science.yaml, not this block"
MANAGED_END = "# END science-managed boundary"


class ManagedBlockError(Exception):
    """Raised when managed-block markers are malformed or ambiguous."""


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


def _managed_block_bounds(text: str) -> tuple[int, int] | None:
    begin_count = text.count(MANAGED_BEGIN)
    end_count = text.count(MANAGED_END)
    if not begin_count and not end_count:
        return None
    if not begin_count:
        raise ManagedBlockError("unmatched END science-managed boundary marker")
    if not end_count:
        raise ManagedBlockError("unmatched BEGIN science-managed boundary marker")
    if begin_count > 1 and end_count > 1:
        raise ManagedBlockError("multiple blocks use science-managed boundary markers")
    if begin_count > 1:
        raise ManagedBlockError("duplicate BEGIN science-managed boundary marker")
    if end_count > 1:
        raise ManagedBlockError("duplicate END science-managed boundary marker")

    start = text.find(MANAGED_BEGIN)
    end = text.find(MANAGED_END)
    if end < start:
        raise ManagedBlockError("reversed science-managed boundary markers")
    return start, end


def extract_managed_block(text: str) -> str | None:
    """Return the block body between the markers, or None if not present."""
    bounds = _managed_block_bounds(text)
    if bounds is None:
        return None
    start, end = bounds
    body_start = start + len(MANAGED_BEGIN)
    return text[body_start:end].lstrip("\n")


def splice_managed_block(text: str, block: str) -> str:
    """Replace the managed block in `text`, or append it if absent."""
    rendered = f"{MANAGED_BEGIN}\n{block}{MANAGED_END}\n"
    bounds = _managed_block_bounds(text)
    if bounds is not None:
        start, end = bounds
        return text[:start] + rendered + text[end + len(MANAGED_END) :].lstrip("\n")
    prefix = text if text.endswith("\n") or not text else text + "\n"
    separator = "\n" if prefix else ""
    return f"{prefix}{separator}{rendered}"
