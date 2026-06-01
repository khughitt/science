# science:code
# status: library
# task_ids: [t067]
# science:end
"""Patch federation via the dual common space (RFC §2 GLUE / R1).

A patch (one disease's gene→disease neighborhood) connects to another through
two glue mechanisms:

  * **symbolic** — shared ontology identifiers. Here: overlap of the curated
    panel gene sets (HGNC symbols). Known-identity glue.
  * **latent** — the data-driven, bias-corrected common coordinate from t066/t067:
    each disease is embedded by factorizing the PPMI (attention-corrected)
    matrix, and two patches relate by cosine in that coordinate. This federates
    patches *without* shared identifiers and *without* re-inheriting literature
    bias.

RFC §2's principle — "symbolic glue where identities are known; latent glue where
they aren't" — is the headline this module makes concrete: CMT and HSP share NO
panel genes (symbolic Jaccard = 0) yet are mutual top-2 latent neighbors out of
3831 diseases, so the latent axis federates two patches that gene-id overlap
alone calls disconnected.

The embeddings are L2-normalized at extraction time, so cosine == dot product;
this module needs no numpy at runtime (it consumes the JSON with stdlib).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rdflib import Dataset, Literal, Namespace, RDF, URIRef
from rdflib.namespace import RDFS, XSD

FEDERATION = Path(__file__).resolve().parent / "fixtures" / "q14_federation.json"

SCI = Namespace("http://example.org/science/vocab/")
BASE = Namespace("http://example.org/meta/patch/")


def load_federation(path: Path = FEDERATION) -> dict:
    return json.loads(Path(path).read_text())


def cosine(a: list[float], b: list[float]) -> float:
    """Dot product; inputs are L2-normalized embeddings, so this is cosine."""
    return sum(x * y for x, y in zip(a, b))


def latent_similarity(fed: dict, mesh_a: str, mesh_b: str) -> float:
    emb = fed["disease_embeddings"]
    return cosine(emb[mesh_a], emb[mesh_b])


def nearest_patches(fed: dict, mesh: str) -> list[dict]:
    """The true global top-ranked latent neighbors recorded at extraction."""
    return fed["focal"][mesh]["neighbors_corrected"]


def panel_genes(slice_fix: dict, mesh: str) -> set[str]:
    disease = slice_fix["diseases"][mesh]
    return {g["symbol"] for g in disease["genes"] if g["in_panel"]}


def symbolic_jaccard(slice_fix: dict, mesh_a: str, mesh_b: str) -> float:
    a, b = panel_genes(slice_fix, mesh_a), panel_genes(slice_fix, mesh_b)
    union = a | b
    return len(a & b) / len(union) if union else 0.0


@dataclass(frozen=True)
class FederationLink:
    a: str
    b: str
    a_name: str
    b_name: str
    symbolic_jaccard: float     # ontology/gene-id glue
    latent_cosine: float        # data-driven bias-corrected glue
    glue_kind: str              # "symbolic+latent" | "latent-only"


def federation_link(fed: dict, slice_fix: dict, mesh_a: str, mesh_b: str) -> FederationLink:
    jac = symbolic_jaccard(slice_fix, mesh_a, mesh_b)
    return FederationLink(
        a=mesh_a, b=mesh_b,
        a_name=fed["focal"].get(mesh_a, {}).get("name", mesh_a),
        b_name=fed["focal"].get(mesh_b, {}).get("name", mesh_b),
        symbolic_jaccard=round(jac, 4),
        latent_cosine=round(latent_similarity(fed, mesh_a, mesh_b), 4),
        glue_kind="symbolic+latent" if jac > 0 else "latent-only",
    )


def gene_latent_similarity(fed: dict, sym_a: str, sym_b: str) -> float:
    g = fed["gene_embeddings"]
    return cosine(g[sym_a]["embedding"], g[sym_b]["embedding"])


def emit_federation_trig(fed: dict, slice_fix: dict, mesh_a: str, mesh_b: str,
                         out_path: Path) -> Path:
    """Serialize the cross-patch GLUE edge as its own (aggregate-scale) named graph.

    Per the multi-scale schema (patch ⊂ project ⊂ collection), the federation
    lives one scale above the disease patches: a `federation` named graph holds a
    reified `PatchFederation` edge between the two patch IRIs, carrying both glue
    measures and which kind actually connects them.
    """
    link = federation_link(fed, slice_fix, mesh_a, mesh_b)
    ds = Dataset()
    fed_iri = URIRef(BASE["federation/q14"])
    g = ds.graph(fed_iri)

    patch_a = URIRef(BASE[f"{mesh_a.replace(':', '_')}-gene-association"])
    patch_b = URIRef(BASE[f"{mesh_b.replace(':', '_')}-gene-association"])
    for patch, name in [(patch_a, link.a_name), (patch_b, link.b_name)]:
        g.add((patch, RDF.type, SCI.EpistemicPatch))
        g.add((patch, RDFS.label, Literal(name)))

    g.add((fed_iri, RDF.type, SCI.PatchFederation))
    g.add((fed_iri, SCI.ladderScale, Literal("aggregate")))

    edge = URIRef(BASE["federation/q14/cmt-hsp"])
    g.add((edge, RDF.type, SCI.PatchFederationLink))
    g.add((edge, SCI.subject, patch_a))
    g.add((edge, SCI.object, patch_b))
    g.add((edge, SCI.symbolicJaccard,
           Literal(link.symbolic_jaccard, datatype=XSD.decimal)))
    g.add((edge, SCI.latentCosine,
           Literal(link.latent_cosine, datatype=XSD.decimal)))
    g.add((edge, SCI.glueKind, Literal(link.glue_kind)))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(out_path), format="trig")
    return out_path
