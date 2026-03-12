"""Curated biology profile manifest layered on top of core Science semantics."""

from science_model.profiles.schema import EntityKind, ProfileManifest, RelationKind

BIO_PROFILE = ProfileManifest(
    name="bio",
    imports=["core"],
    strictness="curated",
    entity_kinds=[
        EntityKind(
            name="gene",
            canonical_prefix="gene",
            layer="layer/domain/bio",
            description="Curated gene entity aligned with biology ontologies.",
        ),
        EntityKind(
            name="protein",
            canonical_prefix="protein",
            layer="layer/domain/bio",
            description="Curated protein or gene product entity.",
        ),
        EntityKind(
            name="protein-family",
            canonical_prefix="protein-family",
            layer="layer/domain/bio",
            description="Curated protein family or domain grouping.",
        ),
        EntityKind(
            name="pathway",
            canonical_prefix="pathway",
            layer="layer/domain/bio",
            description="Curated biological pathway or process grouping.",
        ),
    ],
    relation_kinds=[
        RelationKind(
            name="encodes",
            predicate="biolink:encodes",
            source_kinds=["gene"],
            target_kinds=["protein"],
            layer="layer/domain/bio",
            description="A gene encodes a protein or gene product.",
        ),
        RelationKind(
            name="member_of_family",
            predicate="biolink:member_of",
            source_kinds=["protein"],
            target_kinds=["protein-family"],
            layer="layer/domain/bio",
            description="A protein belongs to a curated protein family grouping.",
        ),
        RelationKind(
            name="participates_in",
            predicate="biolink:participates_in",
            source_kinds=["gene", "protein", "protein-family"],
            target_kinds=["pathway"],
            layer="layer/domain/bio",
            description="A biological entity participates in a pathway.",
        ),
    ],
)
