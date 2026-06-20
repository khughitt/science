"""Patch federation via the dual common space (RFC §2 GLUE).

Two patches (epistemic neighborhoods) connect through two glue mechanisms:

  * **symbolic** — shared ontology identifiers (e.g. overlap of curated gene sets);
  * **latent** — proximity in a data-driven, bias-corrected common coordinate (the
    low-rank factorization of the PPMI matrix from :mod:`science_tool.model.correction`),
    which federates patches *without* shared identifiers and *without* re-inheriting
    the measurement bias.

RFC §2's principle: "symbolic glue where identities are known; latent glue where they
aren't." When the symbolic overlap is zero but the latent proximity is high, the
latent axis carries a relationship the symbolic layer cannot express — and it scales
to entities that have no curated identity to align on at all.

This module consumes pre-computed, L2-normalized embeddings (so cosine == dot). The
factorization that produces them is data processing (numpy/scipy) and lives in the
consuming project; the framework owns the glue *semantics* and the serialization.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from rdflib import RDF, Dataset, Literal, URIRef
from rdflib.namespace import RDFS, XSD

from science_tool.graph.io import SCI_NS


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Dot product; inputs are L2-normalized embeddings, so this is cosine."""
    return sum(x * y for x, y in zip(a, b))


def glue_kind(symbolic_jaccard: float) -> str:
    """Which mechanism connects two patches: 'symbolic+latent' or 'latent-only'."""
    return "symbolic+latent" if symbolic_jaccard > 0 else "latent-only"


def nearest(
    query: Sequence[float],
    candidates: Mapping[str, Sequence[float]],
    k: int,
) -> list[tuple[str, float]]:
    """Top-k candidates by cosine to ``query`` (the query itself is not excluded)."""
    scored = sorted(((cosine(query, vec), key) for key, vec in candidates.items()), reverse=True)
    return [(key, round(score, 4)) for score, key in scored[:k]]


@dataclass(frozen=True)
class FederationLink:
    a: str
    b: str
    a_name: str
    b_name: str
    symbolic_jaccard: float     # ontology / identifier glue
    latent_cosine: float        # data-driven bias-corrected glue
    glue_kind: str


def federation_link(
    a: str,
    b: str,
    symbolic_jaccard: float,
    latent_cosine: float,
    a_name: str = "",
    b_name: str = "",
) -> FederationLink:
    return FederationLink(
        a=a, b=b, a_name=a_name, b_name=b_name,
        symbolic_jaccard=round(symbolic_jaccard, 4),
        latent_cosine=round(latent_cosine, 4),
        glue_kind=glue_kind(symbolic_jaccard),
    )


def emit_federation_trig(
    link: FederationLink,
    patch_iri_a: URIRef,
    patch_iri_b: URIRef,
    federation_iri: URIRef,
    edge_iri: URIRef,
    out_path: str | Path,
) -> Path:
    """Serialize a cross-patch glue edge as its own (aggregate-scale) named graph.

    Per the multi-scale schema (patch ⊂ project ⊂ collection), the federation lives
    one scale above the patches: ``federation_iri`` is the named-graph context holding
    a reified ``PatchFederationLink`` between the two patch IRIs, carrying both glue
    measures and which kind connects them.
    """
    ds = Dataset()
    g = ds.graph(federation_iri)

    for patch, name in [(patch_iri_a, link.a_name), (patch_iri_b, link.b_name)]:
        g.add((patch, RDF.type, SCI_NS.EpistemicPatch))
        if name:
            g.add((patch, RDFS.label, Literal(name)))

    g.add((federation_iri, RDF.type, SCI_NS.PatchFederation))
    g.add((federation_iri, SCI_NS.ladderScale, Literal("aggregate")))

    g.add((edge_iri, RDF.type, SCI_NS.PatchFederationLink))
    g.add((edge_iri, SCI_NS.subject, patch_iri_a))
    g.add((edge_iri, SCI_NS.object, patch_iri_b))
    g.add((edge_iri, SCI_NS.symbolicJaccard, Literal(link.symbolic_jaccard, datatype=XSD.decimal)))
    g.add((edge_iri, SCI_NS.latentCosine, Literal(link.latent_cosine, datatype=XSD.decimal)))
    g.add((edge_iri, SCI_NS.glueKind, Literal(link.glue_kind)))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(out_path), format="trig")
    return out_path
