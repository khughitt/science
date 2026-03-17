"""Core profile manifest for Science-native knowledge graph semantics."""

from science_model.profiles.schema import EntityKind, ProfileManifest, RelationKind

CORE_PROFILE = ProfileManifest(
    name="core",
    imports=[],
    strictness="core",
    entity_kinds=[
        EntityKind(
            name="hypothesis",
            canonical_prefix="hypothesis",
            layer="layer/core",
            description="Testable project hypothesis.",
        ),
        EntityKind(
            name="question",
            canonical_prefix="question",
            layer="layer/core",
            description="Open or resolved project question.",
        ),
        EntityKind(
            name="task",
            canonical_prefix="task",
            layer="layer/core",
            description="Operational project task tracked in the graph.",
        ),
        EntityKind(
            name="claim",
            canonical_prefix="claim",
            layer="layer/core",
            description="Evidence-bearing project claim.",
        ),
        EntityKind(
            name="relation_claim",
            canonical_prefix="relation_claim",
            layer="layer/core",
            description="Claim whose content is an explicit subject-predicate-object relation.",
        ),
        EntityKind(
            name="experiment",
            canonical_prefix="experiment",
            layer="layer/core",
            description="Experiment or analysis step that tests project questions.",
        ),
        EntityKind(
            name="evidence",
            canonical_prefix="evidence",
            layer="layer/core",
            description="Evidence item that supports or disputes project claims.",
        ),
    ],
    relation_kinds=[
        RelationKind(
            name="tests",
            predicate="sci:tests",
            source_kinds=["task", "experiment"],
            target_kinds=["hypothesis", "question"],
            layer="layer/core",
            description="Operational work tests a hypothesis or resolves a question.",
        ),
        RelationKind(
            name="blocked_by",
            predicate="sci:blockedBy",
            source_kinds=["task"],
            target_kinds=["task"],
            layer="layer/core",
            description="A task cannot proceed until another task is complete.",
        ),
        RelationKind(
            name="supports",
            predicate="cito:supports",
            source_kinds=["claim", "evidence"],
            target_kinds=["claim", "relation_claim", "hypothesis"],
            layer="layer/core",
            description="Evidence or a claim provides support for a claim or hypothesis.",
        ),
        RelationKind(
            name="disputes",
            predicate="cito:disputes",
            source_kinds=["claim", "evidence"],
            target_kinds=["claim", "relation_claim", "hypothesis"],
            layer="layer/core",
            description="Evidence or a claim disputes a claim or hypothesis.",
        ),
    ],
)
