"""Tests for the L1 epistemic-neighborhood patch prototype (task t065).

Verifies the prototype (a) reuses the shipped belief machinery (D-005), (b) keeps
provenance honest (editorial < empirical; weaker panel = more uncertainty), (c)
discounts publication gravity via the existing independence reduction, and (d)
emits a patch as a TriG named graph (D-006).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from h00_patch_l1.model import (
    PUBGRAV_GROUP,
    build_edge_units,
    load_fixture,
    pubgravity_threshold,
)
from h00_patch_l1.opinion import opinion_from_scores
from h00_patch_l1.patch import build_patch_report, emit_patch_trig

CMT = "MESH:D002607"   # ClinGen-definitive (strong)
HSP = "MESH:D015419"   # OMIM/GeneReviews-broad (provenance-qualified, moderate)


@pytest.fixture(scope="module")
def fixture() -> dict:
    return load_fixture()


def _gene(disease: dict, symbol: str) -> dict:
    return next(g for g in disease["genes"] if g["symbol"] == symbol)


def test_fixture_is_real_slice(fixture):
    assert fixture["provenance"]["pubtator_version"] == "2026-03-17"
    assert fixture["n_diseases"] > 3000
    # Universal inflators co-occur with (essentially) every disease.
    cmt = fixture["diseases"][CMT]
    tnf = _gene(cmt, "TNF")
    assert tnf["ubiquity"] >= pubgravity_threshold(fixture)
    assert not tnf["in_panel"]


def test_panel_gene_has_two_provenance_routes(fixture):
    cmt = fixture["diseases"][CMT]
    pg = pubgravity_threshold(fixture)
    units = build_edge_units(cmt, _gene(cmt, "PMP22"), pg)
    types = {u.evidence_type for u in units}
    assert types == {"expert_judgment", "literature"}
    editorial = next(u for u in units if u.evidence_type == "expert_judgment")
    literature = next(u for u in units if u.evidence_type == "literature")
    # Editorial = curated/reference (structurally lower status); literature = gated proxy.
    assert editorial.is_reference_dataset is True
    assert literature.proxy_directness == "indirect" and not literature.has_measurement_model


def test_universal_gene_is_literature_only_and_pubgravity(fixture):
    cmt = fixture["diseases"][CMT]
    pg = pubgravity_threshold(fixture)
    units = build_edge_units(cmt, _gene(cmt, "TNF"), pg)
    assert len(units) == 1 and units[0].evidence_type == "literature"
    assert units[0].independence == "shared-source"
    assert units[0].independence_group == PUBGRAV_GROUP


def test_panel_gene_not_flagged_pubgravity(fixture):
    """No curated panel gene reaches the publication-gravity threshold."""
    cmt = fixture["diseases"][CMT]
    pg = pubgravity_threshold(fixture)
    for g in cmt["genes"]:
        if g["in_panel"]:
            lit = [u for u in build_edge_units(cmt, g, pg) if u.evidence_type == "literature"]
            assert all(u.independence == "independent" for u in lit), g["symbol"]


def test_publication_gravity_is_discounted_by_reduction(fixture):
    cmt = fixture["diseases"][CMT]
    pg = pubgravity_threshold(fixture)
    rep = build_patch_report(cmt, pg)
    f = rep["fusion"]
    # The universal genes collapse to a single unit; specific genes survive.
    assert f["n_universal_pubgravity"] >= 5
    assert f["discounted_support_count"] < f["naive_support_count"]
    n_panel = sum(1 for g in cmt["genes"] if g["in_panel"] and g["cooc"] > 0)
    assert f["discounted_support_count"] == n_panel + 1   # panel (independent) + 1 collapsed group
    assert f["discounted_support_score"] < f["naive_support_score"]


def test_weaker_panel_carries_more_uncertainty(fixture):
    """HSP (OMIM/GeneReviews-broad) panel edges are less certain than CMT (ClinGen)."""
    pg = pubgravity_threshold(fixture)
    cmt_rep = build_patch_report(fixture["diseases"][CMT], pg)
    hsp_rep = build_patch_report(fixture["diseases"][HSP], pg)
    cmt_panel_u = [e.opinion.uncertainty for e in cmt_rep["edges"] if e.in_panel]
    hsp_panel_u = [e.opinion.uncertainty for e in hsp_rep["edges"] if e.in_panel]
    assert min(hsp_panel_u) > min(cmt_panel_u)
    # The provenance-qualified label, ALONE, collapses to maximal ignorance.
    assert hsp_rep["editorial_only_example"]["opinion"]["uncertainty"] == 1.0


def test_opinion_masses_sum_to_one_and_uncertainty_falls_with_evidence():
    thin = opinion_from_scores(1, 0)
    rich = opinion_from_scores(8, 0)
    for op in (thin, rich):
        assert op.belief + op.disbelief + op.uncertainty == pytest.approx(1.0)
    assert rich.uncertainty < thin.uncertainty


def test_emit_patch_trig_named_graph(fixture, tmp_path: Path):
    from rdflib import Dataset, URIRef

    out = emit_patch_trig(fixture, CMT, tmp_path / "cmt.trig")
    ds = Dataset()
    ds.parse(str(out), format="trig")
    contexts = [g.identifier for g in ds.graphs() if list(g)]
    patch_iri = URIRef("http://example.org/meta/patch/MESH_D002607-gene-association")
    # The patch IS a named graph (its IRI is the graph context).
    assert patch_iri in contexts
    g = ds.graph(patch_iri)
    sci = "http://example.org/science/vocab/"
    assert (patch_iri, URIRef(sci + "ladderLevel"), None) in [(s, p, None) for s, p, _ in g]
    # Reified association edge-nodes exist and carry belief.
    assocs = list(g.subjects(URIRef(sci + "beliefMagnitude"), None))
    assert len(assocs) >= 7
