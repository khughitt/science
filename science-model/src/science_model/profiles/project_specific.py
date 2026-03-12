"""Formal extension profile for project-local layered knowledge graph semantics."""

from science_model.profiles.schema import ProfileManifest

PROJECT_SPECIFIC_PROFILE = ProfileManifest(
    name="project_specific",
    imports=["core"],
    entity_kinds=[],
    relation_kinds=[],
    strictness="typed-extension",
)
