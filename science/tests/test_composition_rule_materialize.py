# science/tests/test_composition_rule_materialize.py
from __future__ import annotations

from rdflib import Literal, URIRef

from science_model.entities import Entity, EntityType
from science_tool.graph.io import SCI_NS
from science_tool.graph.materialize import _add_reasoning_metadata
from rdflib import Graph


def _entity(rule):
    # type MUST equal core_entity_type_for_kind("mechanism") — see entities.py:343.
    return Entity(
        id="mechanism:m1", kind="mechanism", type=EntityType.MECHANISM, title="M1", project="p",
        ontology_terms=[], related=[], source_refs=[], content_preview="",
        file_path="x.md", composition_rule=rule,
    )


def test_composition_rule_materialized():
    prov = Graph()
    uri = URIRef("http://example.org/science/entity/mechanism/m1")
    _add_reasoning_metadata(uri=uri, provenance=prov, entity=_entity("all_steps"))
    assert (uri, SCI_NS.compositionRule, Literal("all_steps")) in prov


def test_absent_rule_not_materialized():
    prov = Graph()
    uri = URIRef("http://example.org/science/entity/mechanism/m1")
    _add_reasoning_metadata(uri=uri, provenance=prov, entity=_entity(None))
    assert (uri, SCI_NS.compositionRule, None) not in prov
