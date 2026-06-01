# science:code
# status: library
# task_ids: [t065]
# science:end
"""Assemble one L1 patch, run the shipped belief machinery, emit a TriG named graph.

Per D-006 a patch IS a named graph: the patch IRI is the TriG graph context, and
every gene→disease association is a reified edge-node (the established edge-as-node
pattern, not RDF-star) carrying its belief, provenance axes, and opinion as triples
about that node. PROV-O carries the human-vs-AI + activity axis (RFC §5).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdflib import Dataset, Literal, Namespace, RDF, URIRef
from rdflib.namespace import PROV, RDFS, XSD
from science_tool.graph.belief import aggregate_belief
from science_tool.graph.belief_scalar import belief_scalar, unit_score

from .model import PUBGRAV_GROUP, build_edge_units, build_signature_units, pubgravity_threshold
from .opinion import Opinion, opinion_from_scores

SCI = Namespace("http://example.org/science/vocab/")
BASE = Namespace("http://example.org/meta/patch/")
AI_AGENT = URIRef("http://example.org/meta/agent/claude-opus-4-8")
HUMAN_AGENT = URIRef("http://example.org/meta/agent/k-hughitt")


@dataclass(frozen=True)
class EdgeBelief:
    gene: str
    in_panel: bool
    provenance_types: tuple[str, ...]   # editorial / empirical routes on this edge
    magnitude: str
    contested: bool
    support_score: int
    opinion: Opinion


def _edge_belief(disease: dict, gene: dict, pubgrav: int) -> EdgeBelief:
    units = build_edge_units(disease, gene, pubgrav)
    result = aggregate_belief(units)
    scalar = belief_scalar(result)
    routes = []
    if gene["in_panel"]:
        routes.append("editorial")          # elicited (ProvenanceType.EDITORIAL)
    if gene["cooc"] > 0:
        routes.append("empirical")          # discovered (literature)
    return EdgeBelief(
        gene=gene["symbol"],
        in_panel=gene["in_panel"],
        provenance_types=tuple(routes),
        magnitude=result.magnitude.value,
        contested=result.contested,
        support_score=scalar.massed_support_score,
        opinion=opinion_from_scores(scalar.massed_support_score, scalar.massed_dispute_score),
    )


def _signature_fusion(disease: dict, pubgrav: int) -> dict:
    """Patch-level claim, with vs without the independence reduction."""
    units = build_signature_units(disease, pubgrav)
    n_universal = sum(1 for u in units if u.independence_group == PUBGRAV_GROUP)

    # Naive: every co-occurring gene counts as an independent support.
    naive_score = sum(unit_score(u) for u in units)
    naive_count = len(units)

    # Discounted: the shipped reduction collapses the publication-gravity group.
    result = aggregate_belief(units)
    scalar = belief_scalar(result)
    reduced_count = len(result.support_units)

    return {
        "n_genes": len(units),
        "n_universal_pubgravity": n_universal,
        "naive_support_count": naive_count,
        "naive_support_score": naive_score,
        "discounted_support_count": reduced_count,
        "discounted_support_score": scalar.massed_support_score,
        "magnitude": result.magnitude.value,
        "naive_opinion": opinion_from_scores(naive_score, 0).as_dict(),
        "discounted_opinion": opinion_from_scores(scalar.massed_support_score, 0).as_dict(),
    }


def build_patch_report(disease: dict, pubgrav: int) -> dict:
    edges = [_edge_belief(disease, g, pubgrav) for g in disease["genes"]]
    # Editorial-only opinion for a representative panel gene: the honest-ignorance
    # case (a label with no empirical corroboration yet).
    panel_gene = next((g for g in disease["genes"] if g["in_panel"]), None)
    editorial_only = None
    if panel_gene is not None:
        ed_units = [u for u in build_edge_units(disease, panel_gene, pubgrav)
                    if u.evidence_type == "expert_judgment"]
        ed_scalar = belief_scalar(aggregate_belief(ed_units))
        editorial_only = {
            "gene": panel_gene["symbol"],
            "opinion": opinion_from_scores(ed_scalar.massed_support_score, 0).as_dict(),
        }
    return {
        "edges": edges,
        "fusion": _signature_fusion(disease, pubgrav),
        "editorial_only_example": editorial_only,
    }


def emit_patch_trig(fixture: dict, mesh_id: str, out_path: Path) -> Path:
    """Emit the disease patch as a single TriG named graph (D-006)."""
    disease = fixture["diseases"][mesh_id]
    pubgrav = pubgravity_threshold(fixture)
    ds = Dataset()
    patch_iri = URIRef(BASE[f"{mesh_id.replace(':', '_')}-gene-association"])
    g = ds.graph(patch_iri)

    disease_node = URIRef(f"http://example.org/world/disease/{mesh_id.replace(':', '_')}")
    g.add((disease_node, RDF.type, SCI.Disease))
    g.add((disease_node, RDFS.label, Literal(disease["name"])))

    # Patch-level metadata (triples ABOUT the named graph IRI): ladder level +
    # provenance + the fusion summary live on the patch itself.
    fusion = _signature_fusion(disease, pubgrav)
    g.add((patch_iri, RDF.type, SCI.EpistemicPatch))
    g.add((patch_iri, SCI.ladderLevel, Literal("L1")))
    g.add((patch_iri, SCI.focalEntity, disease_node))
    g.add((patch_iri, SCI.naiveSupportScore,
           Literal(fusion["naive_support_score"], datatype=XSD.integer)))
    g.add((patch_iri, SCI.discountedSupportScore,
           Literal(fusion["discounted_support_score"], datatype=XSD.integer)))

    for gene in disease["genes"]:
        units = build_edge_units(disease, gene, pubgrav)
        if not units:
            continue
        eb = _edge_belief(disease, gene, pubgrav)
        gene_node = URIRef(f"http://example.org/world/gene/{gene['symbol']}")
        g.add((gene_node, RDF.type, SCI.Gene))
        g.add((gene_node, RDFS.label, Literal(gene["symbol"])))

        # Reified association edge-node (edge-as-node; multi-edge ready).
        edge = URIRef(BASE[f"{mesh_id.replace(':', '_')}/assoc/{gene['symbol']}"])
        g.add((edge, RDF.type, SCI.GeneDiseaseAssociation))
        g.add((edge, SCI.subject, gene_node))
        g.add((edge, SCI.object, disease_node))
        g.add((edge, SCI.beliefMagnitude, Literal(eb.magnitude)))
        g.add((edge, SCI.provenanceRoutes, Literal(",".join(eb.provenance_types))))
        g.add((edge, SCI.opinionBelief, Literal(round(eb.opinion.belief, 4), datatype=XSD.decimal)))
        g.add((edge, SCI.opinionUncertainty,
               Literal(round(eb.opinion.uncertainty, 4), datatype=XSD.decimal)))
        # PROV agent axis: editorial assertions are AI-drafted + human-ratified.
        if gene["in_panel"]:
            g.add((edge, PROV.wasGeneratedBy, AI_AGENT))
            g.add((edge, SCI.ratifiedBy, HUMAN_AGENT))
        if any(u.independence_group == PUBGRAV_GROUP for u in units):
            g.add((edge, SCI.publicationGravity, Literal(True)))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(out_path), format="trig")
    return out_path
