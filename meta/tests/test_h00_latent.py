"""Tests for the latent-construct bias CORRECTION (task t066).

Verifies the prototype (a) subtracts the publication-attention axis via PMI
(the two-way independence residual), (b) keeps exactly the curated panel genes
and drops the universal publication-gravity genes as specific support, (c)
*flips* the raw-co-occurrence ranking errors attention causes, (d) is strictly
more aggressive than the t065 discount (drops attention-only genes entirely
rather than collapsing-but-counting them), and (e) carries the correction into
the emitted TriG named graph.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from h00_patch_l1.latent import (
    build_corrected_signature_units,
    correct_disease,
    corrected_fusion,
    gene_attention,
    pmi,
    three_way_report,
)
from h00_patch_l1.model import load_fixture, pubgravity_threshold
from h00_patch_l1.patch import emit_patch_trig

CMT = "MESH:D002607"   # ClinGen-definitive (strong)
HSP = "MESH:D015419"   # OMIM/GeneReviews-broad (provenance-qualified, moderate)


@pytest.fixture(scope="module")
def fixture() -> dict:
    return load_fixture()


def _by(corrected, symbol):
    return next(c for c in corrected if c.gene == symbol)


def test_fixture_carries_marginals(fixture):
    """t066 needs the contingency-table marginals t065 did not extract."""
    assert fixture["grand_total"] > 0
    for mesh in (CMT, HSP):
        dis = fixture["diseases"][mesh]
        assert dis["disease_marginal"] > 0
        assert all(g["gene_marginal"] > 0 for g in dis["genes"])


def test_pmi_subtracts_the_attention_axis(fixture):
    """PMI == log(C_gd/N) − α_g − β_d (the attention axes subtracted off)."""
    N = fixture["grand_total"]
    dis = fixture["diseases"][CMT]
    g = next(x for x in dis["genes"] if x["symbol"] == "MPZ")
    direct = pmi(g["cooc"], g["gene_marginal"], dis["disease_marginal"], N)
    alpha = gene_attention(g["gene_marginal"], N)
    beta = gene_attention(dis["disease_marginal"], N)   # β has the same log-share form
    decomposed = math.log(g["cooc"] / N) - alpha - beta
    assert direct == pytest.approx(decomposed)
    assert direct > 0   # MPZ is a true causal gene -> positive after correction


def test_no_cooccurrence_has_no_pmi():
    assert pmi(0, 1000, 1000, 10_000) is None


@pytest.mark.parametrize("mesh", [CMT, HSP])
def test_panel_survives_universal_drops(fixture, mesh):
    """After correction, specificity recovers exactly the curated panel."""
    corrected = correct_disease(fixture["diseases"][mesh], fixture["grand_total"])
    for c in corrected:
        if c.in_panel:
            assert c.specific and c.pmi > 0, c.gene
        else:
            assert not c.specific and c.pmi <= 0, c.gene


def test_correction_flips_raw_ranking(fixture):
    """The headline: raw co-occurrence ranks a pure-attention gene above a true
    causal gene; correction reverses it. In HSP, TNF has the single highest raw
    count of any gene yet the lowest curated relevance."""
    corrected = correct_disease(fixture["diseases"][HSP], fixture["grand_total"])
    tnf = _by(corrected, "TNF")          # universal inflator
    cyp = _by(corrected, "CYP7B1")       # panel gene, low raw count
    assert tnf.raw_cooc > cyp.raw_cooc           # raw ranking gets it WRONG
    assert tnf.pmi < cyp.pmi                      # correction flips it
    assert not tnf.specific and cyp.specific


def test_corrected_is_stricter_than_t065_discount(fixture):
    """naive(17) -> discounted(8, t065) -> corrected(7 specific, t066)."""
    dis = fixture["diseases"][CMT]
    pg = pubgravity_threshold(fixture)
    N = fixture["grand_total"]
    tw = three_way_report(dis, pg, N)
    assert tw["naive"]["support_count"] == 17
    # corrected keeps ONLY specific genes; the discount kept panel + 1 collapsed group.
    assert tw["corrected"]["support_count"] < tw["discounted"]["support_count"]
    assert tw["corrected"]["support_count"] == 7
    assert tw["corrected"]["n_attention_only"] == 10


def test_corrected_fusion_counts(fixture):
    cf = corrected_fusion(fixture["diseases"][HSP], fixture["grand_total"])
    assert cf["n_specific"] == 7
    assert cf["n_attention_only"] == 10
    assert len(build_corrected_signature_units(fixture["diseases"][HSP],
                                               fixture["grand_total"])) == 7
    assert cf["mean_specific_ppmi"] > 0


def test_emit_trig_carries_correction(fixture, tmp_path: Path):
    from rdflib import Dataset, URIRef

    out = emit_patch_trig(fixture, CMT, tmp_path / "cmt.trig")
    ds = Dataset()
    ds.parse(str(out), format="trig")
    patch_iri = URIRef("http://example.org/meta/patch/MESH_D002607-gene-association")
    g = ds.graph(patch_iri)
    sci = "http://example.org/science/vocab/"
    # patch-level corrected score is present
    assert list(g.objects(patch_iri, URIRef(sci + "correctedSupportScore")))
    # per-edge PMI + specificity flags round-trip
    pmis = list(g.subjects(URIRef(sci + "pmi"), None))
    specifics = list(g.subjects(URIRef(sci + "specificAfterCorrection"), None))
    assert len(pmis) >= 17 and len(specifics) >= 17
