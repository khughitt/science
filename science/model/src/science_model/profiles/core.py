"""Core profile manifest for Science-native knowledge graph semantics."""

from science_model.profiles.schema import EntityKind, ProfileManifest, RelationEndpointPair, RelationKind

_CONCLUSION_KINDS = [
    "interpretation",
    "finding",
    "discussion",
    "report",
    "validation-report",
    "story",
]

_CONCLUSION_KIND_PAIRS = [
    RelationEndpointPair(source_kind=source_kind, target_kind=target_kind)
    for source_kind in _CONCLUSION_KINDS
    for target_kind in _CONCLUSION_KINDS
]

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
            name="proposition",
            canonical_prefix="proposition",
            layer="layer/core",
            description="Truth-apt statement — the fundamental epistemic unit.",
        ),
        EntityKind(
            name="observation",
            canonical_prefix="observation",
            layer="layer/core",
            description="Concrete empirical fact anchored to specific data.",
        ),
        EntityKind(
            name="finding",
            canonical_prefix="finding",
            layer="layer/core",
            description="Unit of learned knowledge: propositions grounded by observations from an analysis.",
        ),
        EntityKind(
            name="interpretation",
            canonical_prefix="interpretation",
            layer="layer/core",
            description="One analysis session's narrative and its findings.",
        ),
        EntityKind(
            name="story",
            canonical_prefix="story",
            layer="layer/core",
            description="Coherent narrative arc synthesizing interpretations around a question or hypothesis.",
        ),
        EntityKind(
            name="mechanism",
            canonical_prefix="mechanism",
            layer="layer/core",
            description="Named explanatory structure linking multiple typed entities and propositions.",
        ),
        EntityKind(
            name="theme",
            canonical_prefix="theme",
            layer="layer/core",
            description="Durable cross-cutting organizing frame linking project questions, hypotheses, tasks, reports, concepts, and guardrails.",
        ),
        EntityKind(
            name="paper",
            canonical_prefix="paper",
            layer="layer/core",
            description="Ordered composition of stories structured for communication.",
        ),
        EntityKind(
            name="book",
            canonical_prefix="book",
            layer="layer/core",
            description="Long-form monograph summarized chapter-by-chapter; an evidence source.",
        ),
        EntityKind(
            name="talk",
            canonical_prefix="talk",
            layer="layer/core",
            description="Recorded seminar or conference presentation; an unrefereed evidence source.",
        ),
        EntityKind(
            name="experiment",
            canonical_prefix="experiment",
            layer="layer/core",
            description="Experiment or analysis step that tests project questions.",
        ),
        EntityKind(
            name="method",
            canonical_prefix="method",
            layer="layer/core",
            description="Analytical method or computational approach.",
        ),
        EntityKind(
            name="workflow",
            canonical_prefix="workflow",
            layer="layer/core",
            description="Reusable pipeline definition (Snakefile + config + rules).",
        ),
        EntityKind(
            name="workflow-run",
            canonical_prefix="workflow-run",
            layer="layer/core",
            description="Concrete execution of a workflow producing durable outputs.",
        ),
        EntityKind(
            name="workflow-step",
            canonical_prefix="workflow-step",
            layer="layer/core",
            description="Individual step within a workflow definition or run.",
        ),
        EntityKind(
            name="data-package",
            canonical_prefix="data-package",
            layer="layer/core",
            description="Frictionless research package containing analysis results, prose, and provenance metadata.",
        ),
        EntityKind(
            name="structural-chain",
            canonical_prefix="chain",
            layer="layer/core",
            description="Ordered structural decomposition: >=2 entity refs forming a chain whose verdicts are carried by chain-audit.",
        ),
        EntityKind(
            name="chain-audit",
            canonical_prefix="chain-audit",
            layer="layer/core",
            description="Verdict over a structural-chain. Carries verdict+bayes_factor_evidence with enforced consistency.",
        ),
        EntityKind(
            name="code-file",
            canonical_prefix="code-file",
            layer="layer/core",
            description="Source-code file implementing workflow steps and methods.",
        ),
        EntityKind(
            name="evidence-line",
            canonical_prefix="evidence-line",
            layer="layer/core",
            description="A single, independence-tagged line of evidence that supports or disputes a proposition.",
            entity_class="epistemic",
        ),
    ],
    relation_kinds=[
        RelationKind(
            name="tests",
            predicate="sci:tests",
            source_kinds=["task", "experiment", "workflow-run"],
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
            source_kinds=["observation", "proposition", "evidence-line"],
            target_kinds=["proposition", "hypothesis"],
            layer="layer/core",
            description="An observation or proposition provides support for a proposition or hypothesis.",
        ),
        RelationKind(
            name="disputes",
            predicate="cito:disputes",
            source_kinds=["observation", "proposition", "evidence-line"],
            target_kinds=["proposition", "hypothesis"],
            layer="layer/core",
            description="An observation or proposition disputes a proposition or hypothesis.",
        ),
        RelationKind(
            name="addresses",
            predicate="sci:addresses",
            source_kinds=["question"],
            target_kinds=["proposition"],
            layer="layer/core",
            description="A question is addressed by a proposition.",
        ),
        RelationKind(
            name="realizes",
            predicate="sci:realizes",
            source_kinds=["workflow"],
            target_kinds=["method"],
            layer="layer/core",
            description="A workflow is the executable realization of a method.",
        ),
        RelationKind(
            name="contains",
            predicate="sci:contains",
            source_kinds=["workflow", "finding", "interpretation", "discussion"],
            target_kinds=["workflow-step", "proposition", "observation", "finding"],
            layer="layer/core",
            description="A container entity includes its components: workflow→steps, finding→propositions/observations, interpretation/discussion→findings/propositions.",
        ),
        RelationKind(
            name="executes",
            predicate="sci:executes",
            source_kinds=["workflow-run"],
            target_kinds=["workflow"],
            layer="layer/core",
            description="A workflow run executes a specific workflow.",
        ),
        RelationKind(
            name="supersedes",
            predicate="sci:supersedes",
            source_kinds=["workflow-run", *_CONCLUSION_KINDS],
            target_kinds=["workflow-run", *_CONCLUSION_KINDS],
            allowed_kind_pairs=[
                RelationEndpointPair(source_kind="workflow-run", target_kind="workflow-run"),
                *_CONCLUSION_KIND_PAIRS,
            ],
            layer="layer/core",
            description=(
                "A newer entity replaces an older entity as canonical. Valid "
                "for workflow-run replacement and conclusion-level replacement."
            ),
        ),
        RelationKind(
            name="amends",
            predicate="sci:amends",
            source_kinds=_CONCLUSION_KINDS,
            target_kinds=_CONCLUSION_KINDS,
            allowed_kind_pairs=_CONCLUSION_KIND_PAIRS,
            layer="layer/core",
            description=(
                "A newer conclusion revises, narrows, qualifies, or extends an "
                "older conclusion without replacing it."
            ),
        ),
        RelationKind(
            name="feeds_into",
            predicate="sci:feedsInto",
            source_kinds=["workflow-step"],
            target_kinds=["workflow-step"],
            layer="layer/core",
            description="A workflow step feeds data into another step.",
        ),
        RelationKind(
            name="grounded_by",
            predicate="sci:groundedBy",
            source_kinds=["finding"],
            target_kinds=["data-package", "workflow-run"],
            layer="layer/core",
            description="A finding is grounded by a data package or workflow run.",
        ),
        RelationKind(
            name="synthesizes",
            predicate="sci:synthesizes",
            source_kinds=["story"],
            target_kinds=["interpretation", "discussion", "hypothesis"],
            layer="layer/core",
            description="A story synthesizes interpretations, discussions, or hypotheses.",
        ),
        RelationKind(
            name="organized_by",
            predicate="sci:organizedBy",
            source_kinds=["story"],
            target_kinds=["question", "hypothesis"],
            layer="layer/core",
            description="A story is organized around a question or hypothesis.",
        ),
        RelationKind(
            name="has_participant",
            predicate="sci:hasParticipant",
            source_kinds=["mechanism"],
            target_kinds=[],
            layer="layer/core",
            description="A mechanism points to its semantic participants.",
        ),
        RelationKind(
            name="has_proposition",
            predicate="sci:hasProposition",
            source_kinds=["mechanism"],
            target_kinds=["proposition"],
            layer="layer/core",
            description="A mechanism points to the propositions defining its claims.",
        ),
        RelationKind(
            name="comprises",
            predicate="sci:comprises",
            source_kinds=["paper"],
            target_kinds=["story"],
            layer="layer/core",
            description="A paper comprises one or more stories.",
        ),
        RelationKind(
            name="grounds",
            predicate="sci:grounds",
            source_kinds=["workflow-run"],
            target_kinds=["observation"],
            layer="layer/core",
            description="A workflow run grounds an observation.",
        ),
        RelationKind(
            name="produced_by",
            predicate="sci:producedBy",
            source_kinds=["data-package", "dataset"],
            target_kinds=["workflow-run", "code-file"],
            layer="layer/core",
            description="A data artifact was produced by a workflow run or by code.",
        ),
        RelationKind(
            name="has_link",
            predicate="sci:hasLink",
            source_kinds=["structural-chain"],
            target_kinds=["mechanism", "model", "proposition", "observation", "finding"],
            layer="layer/core",
            description=(
                "Ordered structural-chain link. Targets are restricted to the "
                "structural building blocks. Order is carried in the materialized "
                "graph by sci:linkSequence (RDF list)."
            ),
        ),
        RelationKind(
            name="audits",
            predicate="sci:audits",
            source_kinds=["chain-audit"],
            target_kinds=["structural-chain"],
            layer="layer/core",
            description=(
                "A chain-audit asserts a verdict over a structural-chain. "
                "Mirrors the shape of `tests` (single target by convention)."
            ),
        ),
        RelationKind(
            name="bears_on",
            predicate="sci:bearsOn",
            source_kinds=[],
            target_kinds=[
                "assumption",
                "chain-audit",
                "discussion",
                "evidence-line",
                "finding",
                "hypothesis",
                "interpretation",
                "mechanism",
                "observation",
                "proposition",
                "question",
                "report",
                "story",
                "structural-chain",
                "theme",
                "validation-report",
            ],
            layer="layer/core",
            description=(
                "Source entity's state contributes to the evidence base of the "
                "target epistemic entity. Direction is upstream→downstream "
                "(evidence → belief). Auto-derived from typed edges and "
                "prov:wasDerivedFrom triples by the freshness engine; may also "
                "be hand-authored for cases the auto-rules miss."
            ),
        ),
        RelationKind(
            name="implements",
            predicate="sci:implements",
            source_kinds=["code-file"],
            target_kinds=["workflow-step", "method"],
            layer="layer/core",
            description="A code file implements a workflow step or method.",
        ),
        RelationKind(
            name="defines",
            predicate="sci:defines",
            source_kinds=["code-file"],
            target_kinds=["workflow"],
            layer="layer/core",
            description="A code file defines a workflow.",
        ),
    ],
)
