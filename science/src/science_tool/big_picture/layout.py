"""Canonical entity-home resolution for big-picture inputs.

The big-picture surfaces (resolver, validator, knowledge-gaps) read authored
entities from the project's canonical ``entities/<kind>/`` homes. This helper
resolves those homes from the single source of truth in
``science_tool.entities`` so the locations never drift from the rest of the
toolchain.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.entities import resolve_path_policy


def entity_dir(project_root: Path, kind: str) -> Path:
    """Absolute path to the canonical home directory for ``kind`` entities.

    Resolves via :func:`science_tool.entities.resolve_path_policy` (e.g.
    ``question`` → ``<project_root>/entities/questions``), honoring any
    project-local kind overrides.
    """
    return project_root / resolve_path_policy(kind, project_root=project_root).root
