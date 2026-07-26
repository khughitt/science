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


def extract_managed_block(text: str) -> str | None:
    """Return the block body between the markers, or None if not present."""
    start = text.find(MANAGED_BEGIN)
    if start == -1:
        return None
    end = text.find(MANAGED_END, start)
    if end == -1:
        return None
    body_start = start + len(MANAGED_BEGIN)
    return text[body_start:end].lstrip("\n")


def splice_managed_block(text: str, block: str) -> str:
    """Replace the managed block in `text`, or append it if absent."""
    rendered = f"{MANAGED_BEGIN}\n{block}{MANAGED_END}\n"
    start = text.find(MANAGED_BEGIN)
    if start != -1:
        end = text.find(MANAGED_END, start)
        if end != -1:
            return text[:start] + rendered + text[end + len(MANAGED_END) :].lstrip("\n")
    prefix = text if text.endswith("\n") or not text else text + "\n"
    separator = "\n" if prefix else ""
    return f"{prefix}{separator}{rendered}"
