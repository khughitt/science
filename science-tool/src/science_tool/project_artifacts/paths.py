"""Path resolution for managed artifacts."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from science_tool.project_artifacts import default_registry


def canonical_path(name: str) -> Path:
    """Return the on-disk path of the canonical bytes file for *name*.

    Raises KeyError if no artifact with that name is in the registry.
    """
    registry = default_registry()
    art = next((a for a in registry.artifacts if a.name == name), None)
    if art is None:
        raise KeyError(f"no managed artifact named {name!r} in the registry")

    files = resources.files("science_tool.project_artifacts")
    with resources.as_file(files / art.source) as p:
        # `as_file` may yield a temp path for zip-installed packages; for our
        # filesystem-installed package this is the real path.
        return Path(p)
