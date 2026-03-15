"""Formal extension profile for project-local layered knowledge graph semantics."""

from science_model.profiles.schema import EntityKind, ProfileManifest

PROJECT_SPECIFIC_PROFILE = ProfileManifest(
    name="project_specific",
    imports=["core"],
    entity_kinds=[
        EntityKind(
            name="model",
            canonical_prefix="model",
            layer="layer/project_specific/model",
            description="Project-local scientific model.",
        ),
        EntityKind(
            name="canonical-parameter",
            canonical_prefix="parameter",
            layer="layer/project_specific/model",
            description="Project-local canonical model parameter.",
        ),
        EntityKind(
            name="parameter-binding",
            canonical_prefix="binding",
            layer="layer/project_specific/provenance",
            description="Provenance node that binds a model to a canonical parameter.",
        ),
    ],
    relation_kinds=[],
    strictness="typed-extension",
)
