"""Shared profile schema and manifest exports."""

from science_model.profiles.bio import BIO_PROFILE
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.project_specific import PROJECT_SPECIFIC_PROFILE
from science_model.profiles.schema import EntityKind, ProfileManifest, RelationKind

__all__ = [
    "BIO_PROFILE",
    "CORE_PROFILE",
    "PROJECT_SPECIFIC_PROFILE",
    "EntityKind",
    "ProfileManifest",
    "RelationKind",
]
