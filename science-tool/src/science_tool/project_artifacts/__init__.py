"""Managed-artifact lifecycle for Science projects.

See docs/superpowers/specs/2026-04-26-managed-artifacts-long-term-design.md.
"""

from science_tool.project_artifacts.loader import (
    RegistryLoadError,
    load_packaged_registry,
    load_registry,
)
from science_tool.project_artifacts.registry_schema import Registry


def default_registry() -> Registry:
    """Return the packaged registry. Validates at import time on first call."""
    return load_packaged_registry()


from science_tool.project_artifacts.paths import canonical_path  # noqa: E402  (avoids import cycle)


__all__ = [
    "Registry",
    "RegistryLoadError",
    "canonical_path",
    "default_registry",
    "load_registry",
]
