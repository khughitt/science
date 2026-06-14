from __future__ import annotations

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.graph.io import SCI_NS, entity_uri_for_ref
from science_tool.graph.patch_membership import (
    MembershipRecord,
    emit_patch_memberships,
    validate_patch_membership_convenience,
)


def _uri(ref: str) -> URIRef:
    return entity_uri_for_ref(ref)


def _patch() -> PatchDefinitionEntity:
    return PatchDefinitionEntity.model_validate(
        {
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
            "seeds": ["proposition:p1"],
            "excludes": [{"ref": "proposition:p2", "reason": "out of scope"}],
        }
    )


def test_emit_patch_membership_context_and_authoritative_nodes() -> None:
    ds = Dataset()
    patch = _patch()
    patch_uri = _uri("patch-definition:p1")
    member_uri = _uri("proposition:p1")
    records = [
        MembershipRecord(
            patch=patch_uri,
            patch_id=patch.canonical_id,
            member=member_uri,
            member_role="member",
            member_kind="proposition",
            derivation_reason="seed",
            depth=0,
            policy_version="local-closure-v1",
            build_id="build-1",
        )
    ]

    emit_patch_memberships(ds, [patch], records)
    graph = ds.graph(patch_uri)
    membership_nodes = list(graph.subjects(RDF.type, SCI_NS.PatchMembership))

    assert (patch_uri, RDF.type, SCI_NS.EpistemicPatch) in graph
    assert (patch_uri, SCI_NS.focalEntity, _uri("hypothesis:h1")) in graph
    assert (patch_uri, SCI_NS.hasMember, member_uri) in graph
    assert (member_uri, SCI_NS.inPatch, patch_uri) in graph
    assert len(membership_nodes) == 1
    node = membership_nodes[0]
    assert (node, SCI_NS.patch, patch_uri) in graph
    assert (node, SCI_NS.member, member_uri) in graph
    assert (node, SCI_NS.memberRole, Literal("member")) in graph
    assert (node, SCI_NS.memberKind, Literal("proposition")) in graph
    assert (node, SCI_NS.derivationReason, Literal("seed")) in graph
    assert (node, SCI_NS.policyVersion, Literal("local-closure-v1")) in graph
    assert (node, SCI_NS.buildId, Literal("build-1")) in graph
    assert (node, SCI_NS.derivationDepth, Literal(0, datatype=XSD.integer)) in graph


def test_emit_patch_metadata_includes_seeds_and_exclusions() -> None:
    ds = Dataset()
    patch = _patch()
    patch_uri = _uri("patch-definition:p1")

    emit_patch_memberships(ds, [patch], [])
    graph = ds.graph(patch_uri)

    assert (patch_uri, SCI_NS.patchSeed, _uri("proposition:p1")) in graph
    exclusion_nodes = list(graph.subjects(RDF.type, SCI_NS.PatchExclusion))
    assert len(exclusion_nodes) == 1
    exclusion = exclusion_nodes[0]
    assert (exclusion, SCI_NS.patch, patch_uri) in graph
    assert (exclusion, SCI_NS.excludedEntity, _uri("proposition:p2")) in graph
    assert (exclusion, SCI_NS.excludeReason, Literal("out of scope")) in graph


def test_validate_patch_membership_rejects_orphan_convenience_edges() -> None:
    ds = Dataset()
    patch_uri = _uri("patch-definition:p1")
    member_uri = _uri("proposition:p1")
    graph = ds.graph(patch_uri)
    graph.add((patch_uri, SCI_NS.hasMember, member_uri))

    errors = validate_patch_membership_convenience(ds)

    assert errors == [
        "http://example.org/project/patch-definition/p1 has sci:hasMember http://example.org/project/proposition/p1 without a sci:PatchMembership node"
    ]
