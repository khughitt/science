"""Read `science:merge` annotations from composed entity schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent, ProfileString


class MergePolicy(StrEnum):
    REPLACE = "replace"
    APPEND = "append"
    FORBIDDEN = "forbidden"
    PROJECT_ONLY = "project_only"


_ANNOTATION_KEY = "science:merge"


def read_merge_policy(profile: ProfileString, loader: SchemaLoader | None = None) -> dict[str, MergePolicy]:
    """Return field → merge policy for a composed entity schema."""
    loader = loader or SchemaLoader()
    policy: dict[str, MergePolicy] = {}
    for component in _iter_components(profile):
        schema = loader.load(component)
        for field, spec in (schema.get("properties") or {}).items():
            raw = spec.get(_ANNOTATION_KEY)
            policy[field] = MergePolicy(raw) if raw else MergePolicy.REPLACE
    return policy


def read_overlay_merge_policy(loader: SchemaLoader | None = None) -> dict[str, MergePolicy]:
    """Project-only / append fields declared on the overlay schema."""
    loader = loader or SchemaLoader()
    schema = loader.load(ProfileComponent(name="overlay", version="1.1"))
    policy: dict[str, MergePolicy] = {}
    for field, spec in (schema.get("properties") or {}).items():
        if field in {"id", "overlay_of", "pin_version", "pin_effective_version"}:
            continue
        raw = spec.get(_ANNOTATION_KEY, MergePolicy.PROJECT_ONLY.value)
        policy[field] = MergePolicy(raw)
    return policy


def read_canonical_body_sections(
    profile: ProfileString, loader: SchemaLoader | None = None
) -> list[str]:
    """Return the union of `x-canonical-body-sections` declared by the profile
    components, in declaration order across (base, mixin, extensions).

    Headings are returned verbatim (with original case); matching is case-
    insensitive at the call site. Returns [] when no component declares the
    annotation.
    """
    loader = loader or SchemaLoader()
    sections: list[str] = []
    seen: set[str] = set()
    for component in _iter_components(profile):
        schema = loader.load(component)
        for heading in schema.get("x-canonical-body-sections", []) or []:
            key = heading.casefold()
            if key not in seen:
                sections.append(heading)
                seen.add(key)
    return sections


def _iter_components(profile: ProfileString) -> list[ProfileComponent]:
    components = [profile.base]
    if profile.mixin is not None:
        components.append(profile.mixin)
    components.extend(profile.extensions)
    return components
