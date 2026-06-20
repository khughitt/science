"""The epistemic-neighborhood **patch** — RFC §2 / D-006.

A patch is one epistemic neighborhood (the ``bears_on``/attention neighborhood around
a hypothesis, question, or evidence cluster) promoted to a first-class, addressable
modeling unit. At ladder level **L1** it carries: a belief result, the provenance
axes, and an optional subjective-logic opinion view — computed by REUSING the shipped
:mod:`science_tool.graph.belief` machinery.

Per D-006 a patch IS a named graph: the patch IRI is the TriG graph context, and each
relation is a reified edge-node (the established edge-as-node pattern, not RDF-star)
carrying its belief, provenance, and (optionally) the latent-construct correction and
opinion as triples about that node.

This module owns the *vocabulary and serialization* plus the reusable
independence-aware fusion. Callers mint their own IRIs and build :class:`PatchEdge`
specs from their data; the framework lays down the triples.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rdflib import RDF, Dataset, Literal, URIRef
from rdflib.namespace import PROV, RDFS, XSD

from science_tool.graph.belief import EvidenceUnit, aggregate_belief
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY
from science_tool.graph.belief_scalar import belief_scalar, unit_score
from science_tool.graph.io import SCI_NS

from .opinion import Opinion, opinion_from_scores


@dataclass(frozen=True)
class FusionResult:
    """Patch-level claim fused from its evidence, naive vs independence-discounted.

    ``naive`` counts every unit as an independent support; ``discounted`` is the
    shipped reduction, which collapses shared-source (e.g. publication-gravity)
    groups so one corpus-wide mechanism cannot be counted N times.
    """

    n_units: int
    n_shared_source: int
    naive_support_count: int
    naive_support_score: int
    discounted_support_count: int
    discounted_support_score: int
    magnitude: str
    naive_opinion: Opinion
    discounted_opinion: Opinion


def signature_fusion(units: Sequence[EvidenceUnit]) -> FusionResult:
    """Fuse a patch-level claim from its support units, naive vs discounted."""
    units = list(units)
    naive_score = sum(unit_score(u) for u in units)
    result = aggregate_belief(units)
    scalar = belief_scalar(result)
    return FusionResult(
        n_units=len(units),
        n_shared_source=sum(1 for u in units if u.independence_group),
        naive_support_count=len(units),
        naive_support_score=naive_score,
        discounted_support_count=len(result.support_units),
        discounted_support_score=scalar.massed_support_score,
        magnitude=result.magnitude.value,
        naive_opinion=opinion_from_scores(naive_score, 0),
        discounted_opinion=opinion_from_scores(scalar.massed_support_score, 0),
    )


@dataclass(frozen=True)
class PatchNode:
    iri: URIRef
    label: str
    rdf_type: URIRef


@dataclass(frozen=True)
class PatchEdge:
    """One reified relation in a patch (edge-as-node), with its epistemic annotations."""

    iri: URIRef                       # the reified edge node
    subject: PatchNode
    edge_type: URIRef                 # caller-supplied domain type
    belief_magnitude: str
    provenance_routes: tuple[str, ...] = ()
    opinion: Opinion | None = None
    pmi: float | None = None          # latent-construct correction (model.correction)
    specific: bool | None = None      # survives attention subtraction (PMI > 0)
    publication_gravity: bool = False  # raw shared-source flag (vs the corrected pmi)
    generated_by_ai: bool = False
    ratified_by_human: bool = False


def emit_patch_trig(
    patch_iri: URIRef,
    focal: PatchNode,
    ladder_level: str,
    edges: Sequence[PatchEdge],
    out_path: str | Path,
    *,
    scores: dict[str, int] | None = None,
    ai_agent: URIRef | None = None,
    human_agent: URIRef | None = None,
    dataset: Dataset | None = None,
) -> Path:
    """Emit a patch as a single TriG named graph (D-006).

    ``scores`` are patch-level integer summaries (e.g. naive/discounted/corrected
    support scores) written as triples about the patch IRI.

    PROV note (PLACEHOLDER, not a sanctioned pattern): when ``ai_agent`` /
    ``human_agent`` are given, edges flagged ``generated_by_ai`` / ``ratified_by_human``
    are annotated with ``prov:wasGeneratedBy`` → an agent IRI. PROV-O expects generation
    by an *Activity* with agents attached via attribution/association, and source /
    AI-drafting / human-ratification are distinct activities; this single-edge annotation
    only round-trips structurally. Correct activity/agent modeling is deferred.
    """
    ds = dataset if dataset is not None else Dataset()
    g = ds.graph(patch_iri)

    g.add((focal.iri, RDF.type, focal.rdf_type))
    g.add((focal.iri, RDFS.label, Literal(focal.label)))

    g.add((patch_iri, RDF.type, SCI_NS.EpistemicPatch))
    g.add((patch_iri, SCI_NS.ladderLevel, Literal(ladder_level)))
    g.add((patch_iri, SCI_NS.focalEntity, focal.iri))
    for key, value in (scores or {}).items():
        g.add((patch_iri, SCI_NS[key], Literal(int(value), datatype=XSD.integer)))

    for edge in edges:
        sub = edge.subject
        g.add((sub.iri, RDF.type, sub.rdf_type))
        g.add((sub.iri, RDFS.label, Literal(sub.label)))

        g.add((edge.iri, RDF.type, edge.edge_type))
        g.add((edge.iri, SCI_NS.subject, sub.iri))
        g.add((edge.iri, SCI_NS.object, focal.iri))
        g.add((edge.iri, SCI_NS.beliefMagnitude, Literal(edge.belief_magnitude)))
        g.add((edge.iri, SCI_NS.beliefPolicyId, Literal(DEFAULT_BELIEF_POLICY.policy_id)))
        g.add((edge.iri, SCI_NS.beliefPolicyVersion, Literal(DEFAULT_BELIEF_POLICY.version)))
        if edge.provenance_routes:
            g.add((edge.iri, SCI_NS.provenanceRoutes, Literal(",".join(edge.provenance_routes))))
        if edge.opinion is not None:
            g.add((edge.iri, SCI_NS.opinionBelief,
                   Literal(round(edge.opinion.belief, 4), datatype=XSD.decimal)))
            g.add((edge.iri, SCI_NS.opinionUncertainty,
                   Literal(round(edge.opinion.uncertainty, 4), datatype=XSD.decimal)))
        if edge.pmi is not None:
            g.add((edge.iri, SCI_NS.pmi, Literal(round(edge.pmi, 4), datatype=XSD.decimal)))
            if edge.specific is not None:
                g.add((edge.iri, SCI_NS.specificAfterCorrection, Literal(edge.specific)))
        if edge.publication_gravity:
            g.add((edge.iri, SCI_NS.publicationGravity, Literal(True)))
        if edge.generated_by_ai and ai_agent is not None:
            g.add((edge.iri, PROV.wasGeneratedBy, ai_agent))
        if edge.ratified_by_human and human_agent is not None:
            g.add((edge.iri, SCI_NS.ratifiedBy, human_agent))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(out_path), format="trig")
    return out_path
