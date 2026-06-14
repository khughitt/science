from rdflib import Dataset, RDF, URIRef
from rdflib.namespace import PROV, SKOS

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.graph.inquiry_compile import (
    emit_inquiry_views,
    inquiry_existing_refs,
    inquiry_minted_uris,
)
from science_tool.graph.io import PROJECT_NS, SCI_NS


_ENTITY_REQUIRED = {
    "project": "",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
    "content_preview": "",
    "file_path": "entities/patches/demo.md",
}


def _inquiry_def(slug="i01-flow", **inquiry):
    return PatchDefinitionEntity(
        **_ENTITY_REQUIRED,
        id=f"patch-definition:{slug}",
        title="Flow",
        focal="hypothesis:h01",
        scope_set=[{"scope": "local"}],
        neighborhood_policy={},
        patch_type="inquiry",
        inquiry={"profile": "investigation", "status": "specified", **inquiry},
    )


def test_emits_dedicated_inquiry_graph_with_core_metadata():
    ds = Dataset()
    emit_inquiry_views(ds, [_inquiry_def()])
    iu = URIRef(PROJECT_NS["inquiry/i01-flow"])
    g = ds.graph(iu)
    focal = URIRef(PROJECT_NS["hypothesis/h01"])
    assert (iu, RDF.type, SCI_NS.Inquiry) in g
    assert (iu, SCI_NS.target, focal) in g
    assert (iu, SCI_NS.focalEntity, focal) in g
    assert str(g.identifier) == str(iu)


def test_investigation_maps_to_general_inquiry_type():
    ds = Dataset()
    emit_inquiry_views(ds, [_inquiry_def()])
    iu = URIRef(PROJECT_NS["inquiry/i01-flow"])
    g = ds.graph(iu)
    assert next(g.objects(iu, SCI_NS.inquiryType)).toPython() == "general"


def test_causal_emits_treatment_outcome_and_causal_type():
    ds = Dataset()
    ent = PatchDefinitionEntity(
        **_ENTITY_REQUIRED,
        id="patch-definition:i02-causal", title="Causal", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={}, patch_type="inquiry",
        inquiry={"profile": "causal", "status": "specified", "treatment": "concept:drug", "outcome": "concept:recovery"},
    )
    emit_inquiry_views(ds, [ent])
    iu = URIRef(PROJECT_NS["inquiry/i02-causal"])
    g = ds.graph(iu)
    assert next(g.objects(iu, SCI_NS.inquiryType)).toPython() == "causal"
    assert (iu, SCI_NS.treatment, URIRef(PROJECT_NS["concept/drug"])) in g
    assert (iu, SCI_NS.outcome, URIRef(PROJECT_NS["concept/recovery"])) in g


def test_boundary_and_flow_edges_emitted():
    ds = Dataset()
    ent = _inquiry_def(
        boundary_roles=[{"ref": "concept:x", "role": "BoundaryIn"}, {"ref": "concept:y", "role": "BoundaryOut"}],
        flow_edges=[{"subject": "concept:x", "predicate": "feedsInto", "object": "concept:y"}],
    )
    emit_inquiry_views(ds, [ent])
    g = ds.graph(URIRef(PROJECT_NS["inquiry/i01-flow"]))
    assert (URIRef(PROJECT_NS["concept/x"]), SCI_NS.boundaryRole, SCI_NS.BoundaryIn) in g
    assert (URIRef(PROJECT_NS["concept/y"]), SCI_NS.boundaryRole, SCI_NS.BoundaryOut) in g
    assert (URIRef(PROJECT_NS["concept/x"]), SCI_NS.feedsInto, URIRef(PROJECT_NS["concept/y"])) in g


def test_flow_edge_claims_emitted_as_reified_statement():
    ds = Dataset()
    ent = _inquiry_def(
        flow_edges=[{"subject": "concept:x", "predicate": "feedsInto", "object": "concept:y",
                     "claim_refs": ["proposition:p1"]}],
    )
    emit_inquiry_views(ds, [ent])
    g = ds.graph(URIRef(PROJECT_NS["inquiry/i01-flow"]))
    s = URIRef(PROJECT_NS["concept/x"])
    stmts = [st for st in g.subjects(RDF.subject, s) if (st, RDF.object, URIRef(PROJECT_NS["concept/y"])) in g]
    assert stmts, "expected a reified rdf:Statement for the flow edge"
    claims = list(g.objects(stmts[0], SCI_NS.backedByClaim))
    assert URIRef(PROJECT_NS["proposition/p1"]) in claims


def test_assumption_minted_typed_with_provenance():
    ds = Dataset()
    ent = _inquiry_def(assumptions=[{"ref": "assumption:a1", "statement": "iid", "derived_from": "paper:doi_x"}])
    emit_inquiry_views(ds, [ent])
    g = ds.graph(URIRef(PROJECT_NS["inquiry/i01-flow"]))
    prov = ds.graph(URIRef(PROJECT_NS["graph/provenance"]))
    nodes = list(g.subjects(RDF.type, SCI_NS.Assumption))
    assert len(nodes) == 1
    assert (nodes[0], PROV.wasDerivedFrom, URIRef(PROJECT_NS["paper/doi_x"])) in prov


def test_transformation_and_unknowns_emitted():
    ds = Dataset()
    ent = _inquiry_def(
        transformations=[{"ref": "transformation:t1", "tool": "pandas", "params": [{"value": "0.5", "source": "prior"}]}],
        unknowns=["concept:z"],
    )
    emit_inquiry_views(ds, [ent])
    g = ds.graph(URIRef(PROJECT_NS["inquiry/i01-flow"]))
    tnodes = list(g.subjects(RDF.type, SCI_NS.Transformation))
    assert len(tnodes) == 1
    assert (tnodes[0], SCI_NS.tool, None) in {(s, p, None) for s, p, _ in g}
    assert (tnodes[0], SCI_NS.paramValue, None) in {(s, p, None) for s, p, _ in g}
    assert (URIRef(PROJECT_NS["concept/z"]), RDF.type, SCI_NS.Unknown) in g


def test_get_inquiry_does_not_treat_focalentity_as_edge(tmp_path):
    from science_tool.graph.store.inquiry import get_inquiry

    ds = Dataset()
    emit_inquiry_views(
        ds, [_inquiry_def(flow_edges=[{"subject": "concept:x", "predicate": "feedsInto", "object": "concept:y"}])]
    )
    trig = tmp_path / "graph.trig"
    ds.serialize(destination=str(trig), format="trig")
    info = get_inquiry(trig, "i01-flow")
    preds = {e["predicate"] for e in info["edges"]}
    assert not any("focalEntity" in p for p in preds)
    assert any("feedsInto" in p for p in preds)


def test_origin_helpers_split_existing_and_minted():
    ent = _inquiry_def(
        boundary_roles=[{"ref": "concept:x", "role": "BoundaryIn"}],
        flow_edges=[{"subject": "concept:x", "predicate": "feedsInto", "object": "concept:y",
                     "claim_refs": ["proposition:p1"]}],
        assumptions=[{"ref": "assumption:a1", "statement": "iid"}],
    )
    existing = set(inquiry_existing_refs(ent))
    minted = set(inquiry_minted_uris(ent))
    assert {"concept:x", "concept:y", "proposition:p1"} <= existing
    assert any("assumption" in str(u) for u in minted)


def test_non_inquiry_definitions_emit_nothing():
    ds = Dataset()
    plain = PatchDefinitionEntity(
        **_ENTITY_REQUIRED,
        id="patch-definition:plain", title="Plain", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={},
    )
    emit_inquiry_views(ds, [plain])
    assert len(list(ds.graph(URIRef(PROJECT_NS["inquiry/plain"])))) == 0
