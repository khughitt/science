from __future__ import annotations

import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS, entity_uri_for_ref
from science_tool.graph.patch_membership import (
    PatchMembershipError,
    derive_patch_memberships,
)


_ENTITY_REQUIRED = {
    "project": "",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
    "content_preview": "",
    "file_path": "entities/patches/demo.md",
}


def _uri(ref: str) -> URIRef:
    return entity_uri_for_ref(ref)


def _patch(**overrides: object) -> PatchDefinitionEntity:
    data: dict[str, object] = {
        "id": "patch-definition:p1",
        "canonical_id": "patch-definition:p1",
        "kind": "patch-definition",
        "type": "patch-definition",
        "title": "Patch",
        "status": "active",
        "project": "",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "entities/patches/p1.md",
        "focal": "hypothesis:h1",
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {"name": "local-closure-v1", "version": "local-closure-v1", "max_depth": 2},
        "seeds": [],
        "excludes": [],
    }
    data.update(overrides)
    return PatchDefinitionEntity.model_validate(data)


def _dataset() -> Dataset:
    ds = Dataset()
    g = ds.graph(PROJECT_NS["graph/knowledge"])
    for ref, rdf_type in [
        ("hypothesis:h1", SCI_NS.Hypothesis),
        ("proposition:p1", SCI_NS.Proposition),
        ("proposition:p2", SCI_NS.Proposition),
        ("proposition:p3", SCI_NS.Proposition),
        ("evidence-line:e1", SCI_NS.EvidenceLine),
    ]:
        g.add((_uri(ref), RDF.type, rdf_type))

    def bears_edge(source: str, target: str, depth: int) -> None:
        edge = URIRef(PROJECT_NS[f"bears-on-edge/{source}-{target}-{depth}".replace(":", "-")])
        g.add((edge, RDF.type, SCI_NS.BearsOnEdge))
        g.add((edge, SCI_NS.bearsOnSource, _uri(source)))
        g.add((edge, SCI_NS.bearsOnTarget, _uri(target)))
        g.add((edge, SCI_NS.bearsOnDepth, Literal(depth, datatype=XSD.integer)))

    bears_edge("proposition:p1", "hypothesis:h1", 1)
    bears_edge("proposition:p2", "hypothesis:h1", 2)
    bears_edge("proposition:p3", "hypothesis:h1", 3)
    g.add((_uri("evidence-line:e1"), CITO_NS.supports, _uri("proposition:p1")))
    return ds


def test_deriver_uses_bears_on_depth_not_closed_edge_rewalk() -> None:
    result = derive_patch_memberships(_dataset(), [_patch()], policy_version="local-closure-v1")
    members = {record.member for record in result.records}

    assert _uri("hypothesis:h1") in members
    assert _uri("proposition:p1") in members
    assert _uri("proposition:p2") in members
    assert _uri("proposition:p3") not in members
    p2 = next(record for record in result.records if record.member == _uri("proposition:p2"))
    assert p2.derivation_reason == "closure"
    assert p2.depth == 2


def test_deriver_attaches_direct_relation_neighbors() -> None:
    result = derive_patch_memberships(_dataset(), [_patch()], policy_version="local-closure-v1")
    evidence = next(record for record in result.records if record.member == _uri("evidence-line:e1"))

    assert evidence.member_kind == "evidence"
    assert evidence.derivation_reason == "direct_relation"
    assert evidence.derivation_predicate == CITO_NS.supports
    assert evidence.depth == 2


def test_deriver_records_seeds_as_reason_not_role() -> None:
    result = derive_patch_memberships(
        _dataset(),
        [_patch(seeds=["proposition:p3"])],
        policy_version="local-closure-v1",
    )
    seed = next(record for record in result.records if record.member == _uri("proposition:p3"))

    assert seed.member_role == "member"
    assert seed.member_kind == "proposition"
    assert seed.derivation_reason == "seed"
    assert seed.depth == 0


def test_deriver_excludes_members_and_warns_when_unused() -> None:
    result = derive_patch_memberships(
        _dataset(),
        [
            _patch(
                excludes=[
                    {"ref": "proposition:p1", "reason": "too broad"},
                    {"ref": "proposition:missing", "reason": "stale curation"},
                ]
            )
        ],
        policy_version="local-closure-v1",
    )

    assert _uri("proposition:p1") not in {record.member for record in result.records}
    assert result.warnings == ["patch-definition:p1 exclude proposition:missing did not match any derived member"]


def test_deriver_fails_unresolved_focal_or_seed() -> None:
    with pytest.raises(PatchMembershipError, match="unresolved focal"):
        derive_patch_memberships(_dataset(), [_patch(focal="hypothesis:missing")], policy_version="local-closure-v1")

    with pytest.raises(PatchMembershipError, match="unresolved seed"):
        derive_patch_memberships(_dataset(), [_patch(seeds=["proposition:missing"])], policy_version="local-closure-v1")


def test_deriver_requires_policy_version() -> None:
    with pytest.raises(PatchMembershipError, match="policy_version"):
        derive_patch_memberships(_dataset(), [_patch()], policy_version="")

    with pytest.raises(PatchMembershipError, match="policy_version"):
        derive_patch_memberships(_dataset(), [_patch()], policy_version="   ")


def test_entity_uri_for_ref_rejects_malformed_refs() -> None:
    with pytest.raises(ValueError, match="invalid entity ref"):
        entity_uri_for_ref(":missing-kind")

    with pytest.raises(ValueError, match="invalid entity ref"):
        entity_uri_for_ref("missing-slug:")

    with pytest.raises(ValueError, match="invalid entity ref"):
        entity_uri_for_ref("nocolon")


def test_deriver_output_is_sorted_by_member_iri() -> None:
    result = derive_patch_memberships(_dataset(), [_patch(seeds=["proposition:p3"])], policy_version="local-closure-v1")

    assert [str(record.member) for record in result.records] == sorted(str(record.member) for record in result.records)


def test_deriver_excludes_non_entity_provenance_nodes() -> None:
    from rdflib.namespace import XSD

    ds = Dataset()
    g = ds.graph(PROJECT_NS["graph/knowledge"])
    g.add((_uri("hypothesis:h1"), RDF.type, SCI_NS.Hypothesis))
    # A provenance source-file node: typed prov:Entity, NOT an sci: entity type.
    source_node = URIRef(PROJECT_NS["source/entities_hypotheses_h1.md"])
    g.add((source_node, RDF.type, URIRef("http://www.w3.org/ns/prov#Entity")))
    # The bears-on layer connects the source node to the entity at depth 1.
    edge = URIRef(PROJECT_NS["bears-on-edge/source-h1-1"])
    g.add((edge, RDF.type, SCI_NS.BearsOnEdge))
    g.add((edge, SCI_NS.bearsOnSource, source_node))
    g.add((edge, SCI_NS.bearsOnTarget, _uri("hypothesis:h1")))
    g.add((edge, SCI_NS.bearsOnDepth, Literal(1, datatype=XSD.integer)))

    result = derive_patch_memberships(ds, [_patch()], policy_version="local-closure-v1")
    members = {record.member for record in result.records}

    assert _uri("hypothesis:h1") in members
    assert source_node not in members
    assert all(record.member_kind != "unknown" for record in result.records)


def test_inquiry_existing_refs_and_minted_nodes_become_members():
    from rdflib import Dataset, RDF, URIRef
    from science_model.patch_definition import PatchDefinitionEntity
    from science_tool.graph.inquiry_compile import emit_inquiry_views
    from science_tool.graph.io import PROJECT_NS, SCI_NS
    from science_tool.graph.patch_membership import derive_patch_memberships

    ds = Dataset()
    g = ds.graph(URIRef(PROJECT_NS["graph/knowledge"]))
    g.add((URIRef(PROJECT_NS["hypothesis/h01"]), RDF.type, SCI_NS.Hypothesis))
    g.add((URIRef(PROJECT_NS["concept/x"]), RDF.type, SCI_NS.Concept))
    g.add((URIRef(PROJECT_NS["concept/y"]), RDF.type, SCI_NS.Concept))
    g.add((URIRef(PROJECT_NS["proposition/p1"]), RDF.type, SCI_NS.Proposition))

    ent = PatchDefinitionEntity(
        **_ENTITY_REQUIRED,
        id="patch-definition:i01", title="I", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={}, patch_type="inquiry",
        inquiry={"profile": "investigation", "status": "sketch",
                 "boundary_roles": [{"ref": "concept:x", "role": "BoundaryIn"}],
                 "flow_edges": [{"subject": "concept:x", "predicate": "feedsInto",
                                 "object": "concept:y", "claim_refs": ["proposition:p1"]}],
                 "assumptions": [{"ref": "assumption:a1", "statement": "iid"}]},
    )
    emit_inquiry_views(ds, [ent])  # view first -> minted assumption node typed
    result = derive_patch_memberships(ds, [ent], policy_version="local-closure-v1")

    by_member = {str(r.member): r for r in result.records}
    assert by_member[str(URIRef(PROJECT_NS["concept/x"]))].derivation_reason == "inquiry"
    assert by_member[str(URIRef(PROJECT_NS["proposition/p1"]))].derivation_reason == "inquiry"
    assum = next(r for m, r in by_member.items() if "assumption" in m)
    assert assum.derivation_reason == "inquiry"
    assert assum.member_kind == "assumption"  # not "unknown" — ordering guard


def test_unresolved_inquiry_boundary_ref_is_hard_error():
    import pytest
    from rdflib import Dataset, RDF, URIRef
    from science_model.patch_definition import PatchDefinitionEntity
    from science_tool.graph.inquiry_compile import emit_inquiry_views
    from science_tool.graph.io import PROJECT_NS, SCI_NS
    from science_tool.graph.patch_membership import PatchMembershipError, derive_patch_memberships

    ds = Dataset()
    g = ds.graph(URIRef(PROJECT_NS["graph/knowledge"]))
    g.add((URIRef(PROJECT_NS["hypothesis/h01"]), RDF.type, SCI_NS.Hypothesis))
    ent = PatchDefinitionEntity(
        **_ENTITY_REQUIRED,
        id="patch-definition:i02", title="I", focal="hypothesis:h01",
        scope_set=[{"scope": "local"}], neighborhood_policy={}, patch_type="inquiry",
        inquiry={"profile": "investigation", "status": "sketch",
                 "boundary_roles": [{"ref": "concept:ghost", "role": "BoundaryIn"}]},
    )
    emit_inquiry_views(ds, [ent])
    with pytest.raises(PatchMembershipError, match="unresolved inquiry"):
        derive_patch_memberships(ds, [ent], policy_version="local-closure-v1")
