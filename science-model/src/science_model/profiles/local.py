"""Formal extension profile for project-local layered knowledge graph semantics."""

from science_model.profiles.schema import EntityKind, ProfileManifest

LOCAL_PROFILE = ProfileManifest(
    name="local",
    imports=["core"],
    entity_kinds=[
        EntityKind(
            name="model",
            canonical_prefix="model",
            layer="layer/local",
            description="Project-local scientific model.",
        ),
        EntityKind(
            name="canonical_parameter",
            canonical_prefix="parameter",
            layer="layer/local",
            description="Project-local canonical model parameter.",
        ),
        EntityKind(
            name="parameter_binding",
            canonical_prefix="binding",
            layer="layer/local",
            description="Provenance node that binds a model to a canonical parameter.",
        ),
    ],
    relation_kinds=[],
    strictness="typed-extension",
)
