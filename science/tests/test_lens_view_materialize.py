# science/tests/test_lens_view_materialize.py
from __future__ import annotations

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF

from science_model.entities import Entity, EntityType, LensView, OriginRecord, OriginType
from science_tool.graph.io import SCI_NS
from science_tool.graph.materialize import _add_lens_views, _add_lens_vocabulary, materialize_graph


def _entity() -> Entity:
    return Entity(
        id="question:0001-lens-demo",
        canonical_id="question:0001-lens-demo",
        kind="question",
        type=EntityType.QUESTION,
        title="Lens demo",
        project="p",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/questions/0001-lens-demo.md",
        origins=[
            OriginRecord(type=OriginType.ASSISTANT, ref="explore-ideas-mechanism"),
            OriginRecord(type=OriginType.ASSISTANT, ref="explore-ideas-analogy", independent=True),
        ],
        lens_views=[
            LensView(lens="mechanism", rationale="m", origin_ref="explore-ideas-mechanism"),
            LensView(lens="analogy", rationale="a", origin_ref="explore-ideas-analogy"),
        ],
    )


def test_lens_views_reified_with_origin_link() -> None:
    prov = Graph()
    uri = URIRef("http://example.org/science/entity/question/0001-lens-demo")
    _add_lens_views(uri=uri, provenance=prov, entity=_entity())

    views = list(prov.objects(uri, SCI_NS.hasLensView))
    assert len(views) == 2
    for view in views:
        assert list(prov.objects(view, SCI_NS.viewedThroughLens)), "view missing viewedThroughLens"
        assert list(prov.objects(view, SCI_NS.fromOrigin)), "view missing fromOrigin"


def test_lens_vocabulary_emits_all_six_lenses() -> None:
    g = Graph()
    _add_lens_vocabulary(g)
    lens_nodes = set(g.subjects(RDF.type, SCI_NS.Lens))
    assert len(lens_nodes) == 6
    mechanism = URIRef(SCI_NS["lens/mechanism"])
    assert mechanism in lens_nodes
    assert (mechanism, SCI_NS.lensSlug, Literal("mechanism")) in g


_ENTITY_MD = """\
---
id: question:0001-lens-demo
type: question
title: Lens demo
status: open
ontology_terms: []
related: []
source_refs: []
origins:
  - type: assistant
    ref: explore-ideas-mechanism
  - type: assistant
    ref: explore-ideas-analogy
    independent: true
lens_views:
  - lens: mechanism
    rationale: mechanism framing
    origin_ref: explore-ideas-mechanism
  - lens: analogy
    rationale: analogy framing
    origin_ref: explore-ideas-analogy
created: '2026-07-04'
updated: '2026-07-04'
---
# Lens demo

## Summary

Body.
"""


def test_lens_views_and_vocabulary_wired_into_materialize(tmp_path) -> None:
    # Integration: guards against the helpers existing but never being CALLED.
    (tmp_path / "science.yaml").write_text(
        "name: proj\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8"
    )
    q = tmp_path / "entities" / "questions" / "0001-lens-demo.md"
    q.parent.mkdir(parents=True, exist_ok=True)
    q.write_text(_ENTITY_MD, encoding="utf-8")

    trig = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(trig, format="trig")

    assert any(ds.quads((None, SCI_NS.hasLensView, None))), (
        "no sci:hasLensView edge - _add_lens_views not wired into _add_entity"
    )
    lens_nodes = {row[0] for row in ds.quads((None, RDF.type, SCI_NS.Lens))}
    assert len(lens_nodes) == 6, (
        "expected 6 lens vocabulary nodes - _add_lens_vocabulary not wired into _emit_phase"
    )
