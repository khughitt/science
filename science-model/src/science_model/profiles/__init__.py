"""Shared profile schema and manifest exports."""

from pathlib import Path

import yaml

from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_model.profiles.schema import EntityKind, ProfileManifest, RelationKind

_DEFAULT_MANIFEST_PATH = Path.home() / ".config" / "science" / "registry" / "manifest.yaml"


def load_profile_manifest(manifest_path: Path) -> ProfileManifest | None:
    """Load a profile manifest from YAML. Returns None if not found."""
    if not manifest_path.is_file():
        return None
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return ProfileManifest.model_validate(data)


def load_shared_profile(
    manifest_path: Path = _DEFAULT_MANIFEST_PATH,
) -> ProfileManifest | None:
    """Load the shared cross-project profile from YAML. Returns None if not found."""
    return load_profile_manifest(manifest_path)


__all__ = [
    "CORE_PROFILE",
    "LOCAL_PROFILE",
    "EntityKind",
    "ProfileManifest",
    "RelationKind",
    "load_profile_manifest",
    "load_shared_profile",
]
