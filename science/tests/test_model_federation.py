"""Tests for patch federation via the latent common axis (science_tool.model.federation)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.model.federation import (
    cosine,
    emit_federation_trig,
    federation_link,
    glue_kind,
    nearest,
)


def test_cosine_of_normalized_vectors():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_glue_kind():
    assert glue_kind(0.0) == "latent-only"
    assert glue_kind(0.25) == "symbolic+latent"


def test_latent_glue_where_symbolic_absent():
    """Disjoint identifiers (Jaccard 0) but high latent proximity -> latent-only glue."""
    link = federation_link("MESH:A", "MESH:B", 0.0, 0.95, "CMT", "HSP")
    assert link.symbolic_jaccard == 0.0
    assert link.latent_cosine == 0.95
    assert link.glue_kind == "latent-only"


def test_nearest_ranks_by_cosine():
    query = [1.0, 0.0]
    candidates = {"near": [0.99, 0.14], "mid": [0.7, 0.7], "far": [0.0, 1.0]}
    ranked = nearest(query, candidates, k=2)
    assert [key for key, _ in ranked] == ["near", "mid"]
    assert ranked[0][1] > ranked[1][1]


def test_emit_federation_trig_round_trips(tmp_path: Path):
    from rdflib import Dataset, URIRef

    link = federation_link("MESH:A", "MESH:B", 0.0, 0.95, "CMT", "HSP")
    fed_iri = URIRef("http://example.org/project/patch/federation/demo")
    edge_iri = URIRef("http://example.org/project/patch/federation/demo/a-b")
    out = emit_federation_trig(
        link,
        URIRef("http://example.org/project/patch/A"),
        URIRef("http://example.org/project/patch/B"),
        fed_iri,
        edge_iri,
        tmp_path / "fed.trig",
    )
    ds = Dataset()
    ds.parse(str(out), format="trig")
    sci = "http://example.org/science/vocab/"
    glue = list(ds.quads((edge_iri, URIRef(sci + "glueKind"), None, None)))
    cos = list(ds.quads((edge_iri, URIRef(sci + "latentCosine"), None, None)))
    assert glue and str(glue[0][2]) == "latent-only"
    assert cos and float(cos[0][2]) == pytest.approx(0.95)
