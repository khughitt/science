"""Formal extension profile for project-local layered knowledge graph semantics."""

from science_model.identity import EntityClass
from science_model.profiles.schema import EntityKind, KindCategory, ProfileManifest

LOCAL_PROFILE = ProfileManifest(
    name="local",
    imports=["core"],
    entity_kinds=[
        EntityKind(
            name="model",
            canonical_prefix="model",
            layer="layer/local",
            description="Project-local scientific model.",
            entity_class=EntityClass.OPERATIONAL,
            category=KindCategory.SOURCE_ONLY,
        ),
        EntityKind(
            name="canonical_parameter",
            canonical_prefix="parameter",
            layer="layer/local",
            description="Project-local canonical model parameter.",
            entity_class=EntityClass.OPERATIONAL,
            category=KindCategory.SOURCE_ONLY,
        ),
        EntityKind(
            name="parameter_binding",
            canonical_prefix="binding",
            layer="layer/local",
            description="Provenance node that binds a model to a canonical parameter.",
            entity_class=EntityClass.OPERATIONAL,
            category=KindCategory.SOURCE_ONLY,
        ),
    ],
    relation_kinds=[],
    strictness="typed-extension",
)
