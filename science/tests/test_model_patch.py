"""Tests for the epistemic-neighborhood patch (science_tool.model.patch).

Uses synthetic EvidenceUnits — no project data — to exercise the independence-aware
signature fusion and the TriG named-graph emission.
"""
from __future__ import annotations

from pathlib import Path

from science_tool.graph.belief import EvidenceUnit
from science_tool.model.opinion import opinion_from_scores
from science_tool.model.patch import (
    PatchEdge,
    PatchNode,
    emit_patch_trig,
    signature_fusion,
)

SHARED = "shared-source-group"


def _lit_unit(idx: int, *, shared: bool) -> EvidenceUnit:
    """A synthetic literature/proxy support unit; ``shared`` puts it in one source group."""
    return EvidenceUnit(
        line_uri=f"edge/g{idx}/literature#0",
        stance="supports",
        strength="moderate",
        independence="shared-source" if shared else "independent",
        independence_group=SHARED if shared else None,
        evidence_role="proxy_support",
        evidence_type="literature",
        dispute_scope=None,
        proxy_directness="indirect",
        has_measurement_model=False,
        source="synthetic",
        observability_keys=(),
        is_reference_dataset=False,
    )


def test_signature_fusion_discounts_shared_source_group():
    """3 independent + 4 shared-source supports: the shared group collapses to one."""
    units = [_lit_unit(i, shared=False) for i in range(3)] + [
        _lit_unit(i, shared=True) for i in range(3, 7)
    ]
    fusion = signature_fusion(units)
    assert fusion.n_units == 7
    assert fusion.n_shared_source == 4
    assert fusion.naive_support_count == 7
    assert fusion.discounted_support_count < fusion.naive_support_count
    assert fusion.discounted_support_count == 4          # 3 independent + 1 collapsed group
    assert fusion.discounted_support_score < fusion.naive_support_score
    # discounting raises honest ignorance (the opinion's uncertainty mass)
    assert fusion.discounted_opinion.uncertainty > fusion.naive_opinion.uncertainty


def test_emit_patch_trig_named_graph(tmp_path: Path):
    from rdflib import Dataset, URIRef

    sci = "http://example.org/science/vocab/"
    patch_iri = URIRef("http://example.org/project/patch/demo")
    focal = PatchNode(URIRef("http://example.org/world/disease/D1"), "Demo Disease", URIRef(sci + "Disease"))
    ai = URIRef("http://example.org/agent/ai")
    human = URIRef("http://example.org/agent/human")
    edges = [
        PatchEdge(
            iri=URIRef("http://example.org/project/patch/demo/assoc/G1"),
            subject=PatchNode(URIRef("http://example.org/world/gene/G1"), "G1", URIRef(sci + "Gene")),
            edge_type=URIRef(sci + "GeneDiseaseAssociation"),
            belief_magnitude="supported",
            provenance_routes=("editorial", "empirical"),
            opinion=opinion_from_scores(4, 0),
            pmi=4.6,
            specific=True,
            generated_by_ai=True,
            ratified_by_human=True,
        ),
        PatchEdge(
            iri=URIRef("http://example.org/project/patch/demo/assoc/G2"),
            subject=PatchNode(URIRef("http://example.org/world/gene/G2"), "G2", URIRef(sci + "Gene")),
            edge_type=URIRef(sci + "GeneDiseaseAssociation"),
            belief_magnitude="fragile",
            provenance_routes=("empirical",),
            pmi=-1.2,
            specific=False,
            publication_gravity=True,
        ),
    ]
    out = emit_patch_trig(
        patch_iri, focal, "L1", edges, tmp_path / "patch.trig",
        scores={"naiveSupportScore": 7, "discountedSupportScore": 4, "correctedSupportScore": 1},
        ai_agent=ai, human_agent=human,
    )
    ds = Dataset()
    ds.parse(str(out), format="trig")
    contexts = [g.identifier for g in ds.graphs() if list(g)]
    assert patch_iri in contexts          # the patch IS a named graph
    g = ds.graph(patch_iri)
    assert (patch_iri, URIRef(sci + "ladderLevel"), None) in [(s, p, None) for s, p, _ in g]
    assoc = list(g.subjects(URIRef(sci + "beliefMagnitude"), None))
    assert len(assoc) == 2
    pmis = list(g.subjects(URIRef(sci + "pmi"), None))
    assert len(pmis) == 2
    # patch-level scores present
    assert list(g.objects(patch_iri, URIRef(sci + "correctedSupportScore")))
