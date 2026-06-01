"""Tests for patch federation via the dual common space (task t067).

Verifies (a) the bias-corrected latent coordinate federates two patches whose
panel gene sets are DISJOINT (symbolic glue absent → latent glue carries it),
(b) the proximity is specific (beats random controls) and biologically coherent
(every neighbor with a MeSH tree is a C10 nervous-system disease — an independent
validation the embedding never saw), (c) the gene-coordinate half is structured
too (same-biology panel genes cluster; universal genes form their own cluster),
(d) the correction's marginal effect on federation is an honest *sharpening*, not
a rescue, and (e) the cross-patch glue edge round-trips in TriG.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from h00_patch_l1.glue import (
    emit_federation_trig,
    federation_link,
    gene_latent_similarity,
    latent_similarity,
    load_federation,
    nearest_patches,
    symbolic_jaccard,
)
from h00_patch_l1.model import load_fixture

CMT, HSP = "MESH:D002607", "MESH:D015419"


@pytest.fixture(scope="module")
def fed() -> dict:
    return load_federation()


@pytest.fixture(scope="module")
def slice_fix() -> dict:
    return load_fixture()


def test_fixture_is_real_embeddings(fed):
    assert fed["provenance"]["pubtator_version"] == "2026-03-17"
    assert fed["n_diseases"] > 3000
    assert len(fed["disease_embeddings"][CMT]) == fed["provenance"]["k"]


def test_disjoint_panels_have_zero_symbolic_glue(slice_fix):
    """CMT and HSP curate entirely different causal genes."""
    assert symbolic_jaccard(slice_fix, CMT, HSP) == 0.0


def test_latent_glue_federates_where_symbolic_is_absent(fed, slice_fix):
    """The §2 payoff: latent axis connects patches gene-id overlap calls disconnected."""
    link = federation_link(fed, slice_fix, CMT, HSP)
    assert link.symbolic_jaccard == 0.0
    assert link.glue_kind == "latent-only"
    assert link.latent_cosine > 0.9
    # HSP is among CMT's very nearest disease-patches out of all 3831.
    assert fed["cmt_hsp"]["hsp_rank_among_cmt_corrected"] <= 3


def test_proximity_is_specific_not_universal(fed):
    """CMT–HSP must beat seeded-random control diseases — proximity is biology,
    not a universal artifact of the coordinate."""
    cmt_hsp = latent_similarity(fed, CMT, HSP)
    assert all(cmt_hsp > c["cosine_to_cmt"] for c in fed["controls"])


@pytest.mark.parametrize("mesh", [CMT, HSP])
def test_neighbors_are_nervous_system_diseases(fed, mesh):
    """Independent validation: every neighbor with a MeSH tree number sits in
    C10 (Nervous System Diseases). The embedding never saw the MeSH hierarchy."""
    trees = [nb["tree"] for nb in nearest_patches(fed, mesh) if nb["tree"]]
    assert trees and all(t.startswith("C10") for t in trees)


def test_latent_similarity_matches_stored(fed):
    assert latent_similarity(fed, CMT, HSP) == pytest.approx(
        fed["cmt_hsp"]["cosine_corrected"], abs=1e-3)
    assert latent_similarity(fed, CMT, CMT) == pytest.approx(1.0, abs=1e-3)


def test_correction_sharpens_federation_not_rescues(fed):
    """Honest scope: at the disease-PROFILE scale the attention bias is largely
    washed out by normalization, so correction *sharpens* (better rank) rather
    than rescuing a broken raw signal — both ranks are already small."""
    ch = fed["cmt_hsp"]
    assert ch["hsp_rank_among_cmt_corrected"] <= ch["hsp_rank_among_cmt_raw"]
    assert ch["hsp_rank_among_cmt_raw"] <= 10        # raw was already decent
    assert ch["cosine_corrected"] > ch["cosine_raw"]  # but corrected is tighter


def test_gene_coordinate_is_structured(fed):
    """Same-biology panel genes cluster; a panel gene is far from a universal one."""
    same_biology = gene_latent_similarity(fed, "PMP22", "MPZ")     # both CMT myelin
    panel_vs_universal = gene_latent_similarity(fed, "PMP22", "TNF")
    assert same_biology > panel_vs_universal
    assert gene_latent_similarity(fed, "TNF", "IL6") > panel_vs_universal  # universals cluster


def test_emit_federation_trig(fed, slice_fix, tmp_path: Path):
    from rdflib import Dataset, URIRef

    out = emit_federation_trig(fed, slice_fix, CMT, HSP, tmp_path / "fed.trig")
    ds = Dataset()
    ds.parse(str(out), format="trig")
    sci = "http://example.org/science/vocab/"
    edge = URIRef("http://example.org/meta/patch/federation/q14/cmt-hsp")
    glue = list(ds.quads((edge, URIRef(sci + "glueKind"), None, None)))
    cosines = list(ds.quads((edge, URIRef(sci + "latentCosine"), None, None)))
    assert glue and str(glue[0][2]) == "latent-only"
    assert cosines and float(cosines[0][2]) > 0.9
