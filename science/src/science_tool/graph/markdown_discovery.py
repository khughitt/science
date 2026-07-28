"""Pure discovery policy for canonical markdown source records.

Filesystem adapters and descriptor-anchored readers perform I/O differently, but
they must agree on which roots and leaves are eligible. This module owns that
filesystem-free contract so neither reader can drift by copying path spellings or
sidecar rules.
"""

from __future__ import annotations

from pathlib import PurePosixPath

ENTITY_MARKDOWN_SCAN_ROOT = "entities"
RESEARCH_PACKAGE_SCAN_ROOT = "research/packages"
DEFAULT_MARKDOWN_SCAN_ROOTS = (
    ENTITY_MARKDOWN_SCAN_ROOT,
    RESEARCH_PACKAGE_SCAN_ROOT,
)

# Anchor-surface sidecars live inside entity roots but are not entity records.
SIDECAR_MARKDOWN_SUFFIX = ".source.md"


def is_discoverable_markdown_leaf(name: str) -> bool:
    """Whether one leaf name is a canonical markdown source candidate."""
    return name.endswith(".md") and not name.endswith(SIDECAR_MARKDOWN_SUFFIX)


def uses_entity_directory_policy(scan_root: str) -> bool:
    """Whether this is the default exact ``entities`` scan root.

    A caller-supplied subroot such as ``entities/reports`` is an explicit
    traversal boundary and recursively scans everything below that boundary.
    """
    normalized = scan_root.replace("\\", "/")
    return PurePosixPath(normalized) == PurePosixPath(ENTITY_MARKDOWN_SCAN_ROOT)
