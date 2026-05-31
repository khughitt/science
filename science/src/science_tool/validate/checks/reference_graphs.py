"""Reference graph collection checks (RG1)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from science_tool.commons.member import ResolutionState, evaluate_key_resolution, parse_member_of
from science_tool.commons.reference_graph import (
    REFERENCE_GRAPH_FORMATS,
    ReferenceGraphCollectionError,
    ReferenceGraphNode,
    is_reference_graph_frontmatter,
    is_reference_graph_member_frontmatter,
    parse_edge_rows,
    parse_node_index_rows,
)
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _is_int(value: object) -> bool:
    return type(value) is int


def _collection_defect(fm: dict[str, Any]) -> str | None:
    graph_resource = fm.get("graph_resource")
    if not isinstance(graph_resource, str) or not graph_resource.strip():
        return "graph_resource must name a Frictionless resource"
    graph_format = fm.get("graph_format")
    if graph_format not in REFERENCE_GRAPH_FORMATS:
        return f"graph_format must be one of {sorted(REFERENCE_GRAPH_FORMATS)}"
    member_key_space = fm.get("member_key_space")
    if not isinstance(member_key_space, dict):
        return "member_key_space must be an object"
    kind = member_key_space.get("kind")
    if kind not in ("curie", "iri", "tuple"):
        return "member_key_space.kind must be curie|iri|tuple"
    prefixes = member_key_space.get("prefixes")
    if (
        not isinstance(prefixes, list)
        or not prefixes
        or any(not isinstance(item, str) or not item for item in prefixes)
    ):
        return "member_key_space.prefixes must be a non-empty list of strings"
    status = member_key_space.get("resolution_status")
    if status not in ("resolved", "declared_unresolved"):
        return "member_key_space.resolution_status must be resolved|declared_unresolved"
    node_resource = fm.get("node_index_resource")
    if not isinstance(node_resource, str) or not node_resource.strip():
        return "node_index_resource must name a Frictionless resource"
    edge_resource = fm.get("edge_resource")
    if edge_resource is not None and (not isinstance(edge_resource, str) or not edge_resource.strip()):
        return "edge_resource must name a Frictionless resource when declared"
    member_count = fm.get("member_count")
    if not _is_int(member_count):
        return "member_count must be a positive integer"
    assert isinstance(member_count, int)
    if member_count < 1:
        return "member_count must be a positive integer"
    edge_count = fm.get("edge_count")
    if edge_count is not None and not _is_int(edge_count):
        return "edge_count must be a non-negative integer"
    if edge_count is not None:
        assert isinstance(edge_count, int)
    if edge_count is not None and edge_count < 0:
        return "edge_count must be a non-negative integer"
    return None


def _node_by_key(nodes: list[ReferenceGraphNode]) -> dict[str, ReferenceGraphNode]:
    return {node.member_key: node for node in nodes}


def _member_defect(derivation: dict[str, Any]) -> str | None:
    parent = derivation.get("parent_dataset")
    if not isinstance(parent, str) or not parent.startswith("dataset:"):
        return "member_of derivation requires a parent_dataset 'dataset:' reference"
    key = derivation.get("member_key")
    if not isinstance(key, str) or not key.strip():
        return "member_of derivation requires a non-empty member_key"
    return None


def evaluate_reference_graphs(
    datasets: Iterable[dict[str, Any]],
    *,
    graph_available_by_dataset_id: dict[str, bool | Exception | None],
    node_rows_by_dataset_id: dict[str, list[dict[str, Any]] | Exception | None],
    edge_rows_by_dataset_id: dict[str, list[dict[str, Any]] | Exception | None],
    member_datasets: Iterable[dict[str, Any]],
) -> Iterator[Result]:
    collections = [fm for fm in datasets if is_reference_graph_frontmatter(fm)]
    nodes_by_collection: dict[str, dict[str, ReferenceGraphNode]] = {}

    for fm in collections:
        ident = str(fm.get("id") or "?")
        path = fm.get("_path")
        defect = _collection_defect(fm)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: malformed bio.reference_graph collection -- {defect}",
                "reference-graph.collection-malformed",
            )
            continue

        graph_available = graph_available_by_dataset_id.get(ident)
        if graph_available is None or graph_available is False:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: graph_resource is unavailable; graph artifact cannot be verified",
                "reference-graph.graph-resource-unavailable",
            )
        elif isinstance(graph_available, Exception):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: graph_resource malformed -- {graph_available}",
                "reference-graph.graph-resource-malformed",
            )

        raw_nodes = node_rows_by_dataset_id.get(ident)
        if raw_nodes is None:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: node_index_resource is unavailable; member resolution cannot be verified",
                "reference-graph.node-index-unavailable",
            )
        elif isinstance(raw_nodes, Exception):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: node_index_resource malformed -- {raw_nodes}",
                "reference-graph.node-index-malformed",
            )
        else:
            try:
                nodes = parse_node_index_rows(raw_nodes)
            except ReferenceGraphCollectionError as exc:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: node_index_resource malformed -- {exc}",
                    "reference-graph.node-index-malformed",
                )
            else:
                if len(nodes) != fm["member_count"]:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: member_count={fm['member_count']} but node_index_resource has {len(nodes)} node rows",
                        "reference-graph.member-count-mismatch",
                    )
                else:
                    nodes_by_collection[ident] = _node_by_key(nodes)

        raw_edges = edge_rows_by_dataset_id.get(ident)
        if raw_edges is None:
            if fm.get("edge_resource") is not None:
                yield _result(
                    Severity.INFO,
                    path,
                    f"{ident}: edge_resource is unavailable; edge count cannot be verified",
                    "reference-graph.edge-resource-unavailable",
                )
            continue
        if isinstance(raw_edges, Exception):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: edge_resource malformed -- {raw_edges}",
                "reference-graph.edge-resource-malformed",
            )
            continue
        try:
            edges = parse_edge_rows(raw_edges)
        except ReferenceGraphCollectionError as exc:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: edge_resource malformed -- {exc}",
                "reference-graph.edge-resource-malformed",
            )
            continue
        if fm.get("edge_count") is not None and len(edges) != fm["edge_count"]:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: edge_count={fm['edge_count']} but edge_resource has {len(edges)} rows",
                "reference-graph.edge-count-mismatch",
            )

    for member in member_datasets:
        if not is_reference_graph_member_frontmatter(member):
            continue
        member_id = str(member.get("id") or "?")
        path = member.get("_path")
        derivation = member.get("derivation")
        if not isinstance(derivation, dict) or derivation.get("kind") != "member_of":
            yield _result(
                Severity.ERROR,
                path,
                f"{member_id}: bio.reference_graph.member must use derivation.kind=member_of",
                "reference-graph.member-not-member-of",
            )
            continue
        defect = _member_defect(derivation)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{member_id}: malformed bio.reference_graph.member -- {defect}",
                "reference-graph.member-malformed",
            )
            continue
        member_of = parse_member_of(member)
        if member_of is None:
            continue

        available_nodes = nodes_by_collection.get(member_of.parent_dataset)
        state = evaluate_key_resolution(
            key=member_of.member_key,
            available_keys=set(available_nodes) if available_nodes is not None else None,
            declared_status=None,
        )
        if state is ResolutionState.UNKNOWN:
            yield _result(
                Severity.INFO,
                path,
                (
                    f"{member_id}: parent reference graph {member_of.parent_dataset!r} unavailable; "
                    "member resolution cannot be verified"
                ),
                "reference-graph.member-resolution-unknown",
            )
            continue
        if state is ResolutionState.UNRESOLVED:
            yield _result(
                Severity.ERROR,
                path,
                f"{member_id}: member_key {member_of.member_key!r} is absent from {member_of.parent_dataset}",
                "reference-graph.member-unresolved",
            )
            continue

        assert available_nodes is not None
        node = available_nodes[member_of.member_key]
        if node.status in {"deprecated", "withdrawn"}:
            replacement = f"; replaced_by={';'.join(node.replaced_by)}" if node.replaced_by else ""
            yield _result(
                Severity.WARN,
                path,
                f"{member_id}: member_key {member_of.member_key!r} is {node.status}{replacement}",
                "reference-graph.member-deprecated",
            )
