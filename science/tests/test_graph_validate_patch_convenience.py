from __future__ import annotations

from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.graph.io import SCI_NS, entity_uri_for_ref
from science_tool.graph.store.validation import validate_graph_dataset


def _uri(ref: str) -> URIRef:
    return entity_uri_for_ref(ref)


def _row(rows: list[dict[str, str]], check: str) -> dict[str, str]:
    return next(row for row in rows if row["check"] == check)


def test_validate_graph_flags_orphan_patch_convenience_edge() -> None:
    ds = Dataset()
    patch_uri = _uri("patch-definition:p1")
    member_uri = _uri("proposition:p1")
    # A convenience edge with no backing sci:PatchMembership node.
    ds.graph(patch_uri).add((patch_uri, SCI_NS.hasMember, member_uri))

    rows, has_failures = validate_graph_dataset(ds)

    row = _row(rows, "patch_membership_convenience")
    assert row["status"] == "fail"
    assert "without a sci:PatchMembership node" in row["details"]
    assert has_failures is True


def test_validate_graph_passes_when_convenience_edges_are_backed() -> None:
    ds = Dataset()
    patch_uri = _uri("patch-definition:p1")
    member_uri = _uri("proposition:p1")
    graph = ds.graph(patch_uri)
    node = _uri("patch-membership:m1")
    graph.add((node, RDF.type, SCI_NS.PatchMembership))
    graph.add((node, SCI_NS.patch, patch_uri))
    graph.add((node, SCI_NS.member, member_uri))
    graph.add((patch_uri, SCI_NS.hasMember, member_uri))
    graph.add((member_uri, SCI_NS.inPatch, patch_uri))

    rows, _ = validate_graph_dataset(ds)

    row = _row(rows, "patch_membership_convenience")
    assert row["status"] == "pass"


def test_validate_graph_passes_when_no_patches_present() -> None:
    ds = Dataset()

    rows, _ = validate_graph_dataset(ds)

    row = _row(rows, "patch_membership_convenience")
    assert row["status"] == "pass"
