from __future__ import annotations

from pathlib import Path
from typing import cast

import click
from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import RDF, SKOS

from science_tool.graph.export_types import (
    GraphExportEdge,
    GraphExportLayer,
    GraphExportNode,
    GraphExportOverlays,
    GraphExportPayload,
    GraphExportScope,
    build_graph_export_edge_id,
    build_graph_export_node_id,
)
from science_tool.graph.io import project_root_from_graph_path as _project_root_from_graph_path

from .constants import (
    GRAPH_EXPORT_EDGE_METADATA_PREDICATES,
    GRAPH_EXPORT_SCHEMA_VERSION,
    GRAPH_LAYERS,
    PROJECT_NS,
    SCHEMA_NS,
    SCI_NS,
    SCIC_NS,
)
from .dataset import _load_dataset
from .evidence_signals import (
    _apply_evidence_semantics_to_bundle,
    _apply_phase1_metadata_to_bundle,
    _collect_evidence_signals,
    _load_proposition_bridge_hypotheses,
    _load_proposition_evidence_semantics,
    _load_proposition_falsifications,
    _load_proposition_interaction_terms,
    _load_proposition_phase1_metadata,
    _load_proposition_pre_registrations,
    _source_strings,
)
from .identity import (
    _edge_claims,
    _graph_uri,
    shorten_uri,
)
from .types import (
    EvidenceClaimBundle,
    EvidenceEdgeOverlay,
)


def _export_graph_layers(dataset: Dataset) -> list[str]:
    """Return named graph layers that should be exported as base graph content."""
    return _sort_export_layers(_export_layer_graph_map(dataset))


def _canonical_export_layer_id(graph_id: str) -> str | None:
    project_prefix = str(PROJECT_NS)
    inquiry_prefix = f"{project_prefix}inquiry/"
    if not graph_id.startswith(project_prefix) or graph_id.startswith(inquiry_prefix):
        return None

    layer = graph_id[len(project_prefix) :]
    if not layer:
        return None
    if not layer.startswith("graph/"):
        layer = f"graph/{layer}"
    return layer


def _export_layer_graph_map(dataset: Dataset) -> dict[str, Graph]:
    graphs_by_layer: dict[str, list[Graph]] = {}

    for graph in dataset.graphs():
        layer = _canonical_export_layer_id(str(graph.identifier))
        if layer is None:
            continue
        graphs_by_layer.setdefault(layer, []).append(graph)

    combined_graphs: dict[str, Graph] = {}
    for layer, graphs in graphs_by_layer.items():
        if len(graphs) == 1:
            combined_graphs[layer] = graphs[0]
            continue

        merged_graph = Graph()
        for graph in graphs:
            for triple in graph:
                merged_graph.add(triple)
        combined_graphs[layer] = merged_graph

    return combined_graphs


def _sort_export_layers(layer_graphs: dict[str, Graph]) -> list[str]:
    layers = list(layer_graphs)

    preferred_layers = [layer for layer in GRAPH_LAYERS if layer != "graph/provenance"]
    preferred_order = {layer: index for index, layer in enumerate(preferred_layers)}

    def _sort_key(layer: str) -> tuple[int, int | str]:
        if layer in preferred_order:
            return (0, preferred_order[layer])
        if layer == "graph/provenance":
            return (2, layer)
        return (1, layer)

    return sorted(layers, key=_sort_key)


def export_graph_payload(graph_path: Path, overlays: list[str] | None = None) -> GraphExportPayload:
    """Export the base project graph as a reusable JSON-ready payload."""
    requested_overlays = set(overlays or [])
    unsupported_overlays = requested_overlays - {"causal", "evidence"}
    if unsupported_overlays:
        raise click.ClickException(f"Unsupported graph export overlay(s): {', '.join(sorted(unsupported_overlays))}")

    dataset = _load_dataset(graph_path)
    layer_graph_by_id = _export_layer_graph_map(dataset)
    export_layers = _sort_export_layers(layer_graph_by_id)
    knowledge = layer_graph_by_id.get("graph/knowledge", dataset.graph(_graph_uri("graph/knowledge")))
    provenance = layer_graph_by_id.get("graph/provenance", dataset.graph(_graph_uri("graph/provenance")))
    layer_graphs = [(layer, layer_graph_by_id[layer]) for layer in export_layers]
    inquiry_graphs = [
        graph for graph in dataset.graphs() if str(graph.identifier).startswith(f"{PROJECT_NS}inquiry/")
    ]

    statement_nodes: set[str] = set()
    node_layers: dict[str, set[str]] = {}
    edge_records: dict[str, GraphExportEdge] = {}
    layer_edge_ids: dict[str, set[str]] = {layer: set() for layer in export_layers}
    warnings: list[str] = []

    def _claim_ids_for_exported_edge(layer_graph: Graph, subject: URIRef, predicate: URIRef, object_: URIRef) -> list[str]:
        claim_uris = set(_edge_claims(layer_graph, subject, predicate, object_))
        for inquiry_graph in inquiry_graphs:
            claim_uris.update(_edge_claims(inquiry_graph, subject, predicate, object_))
        return [str(claim_uri) for claim_uri in sorted(claim_uris, key=str)]

    for layer, layer_graph in layer_graphs:
        for subject, predicate, object_ in layer_graph:
            if isinstance(subject, URIRef):
                subject_id = str(subject)
                node_layers.setdefault(subject_id, set()).add(layer)
                if predicate == RDF.type and object_ == RDF.Statement:
                    statement_nodes.add(subject_id)

            if isinstance(object_, URIRef) and predicate not in GRAPH_EXPORT_EDGE_METADATA_PREDICATES:
                object_id = str(object_)
                node_layers.setdefault(object_id, set()).add(layer)

            if not isinstance(subject, URIRef) or not isinstance(predicate, URIRef) or not isinstance(object_, URIRef):
                continue
            if predicate in GRAPH_EXPORT_EDGE_METADATA_PREDICATES:
                continue

            edge_id = build_graph_export_edge_id(
                subject=str(subject),
                predicate=str(predicate),
                obj=str(object_),
                graph_layer=layer,
            )
            claim_ids = _claim_ids_for_exported_edge(layer_graph, subject, predicate, object_)
            edge_records[edge_id] = GraphExportEdge(
                id=edge_id,
                subject=build_graph_export_node_id(str(subject)),
                predicate=str(predicate),
                object=build_graph_export_node_id(str(object_)),
                graph_layer=layer,
                claim_ids=claim_ids,
            )
            layer_edge_ids[layer].add(edge_id)

    for node_id in statement_nodes:
        node_layers.pop(node_id, None)

    def _node_label(node_uri: URIRef) -> str:
        for graph in (layer_graph for _, layer_graph in layer_graphs):
            for predicate in (SKOS.prefLabel, SCHEMA_NS.name, SCHEMA_NS.text, SCHEMA_NS.description):
                label_obj = next(graph.objects(node_uri, predicate), None)
                if label_obj is None:
                    continue
                label = str(label_obj).strip()
                if label:
                    return label
        return shorten_uri(str(node_uri))

    def _node_types(node_uri: URIRef) -> list[str]:
        types: list[str] = []
        seen: set[str] = set()
        for graph in (layer_graph for _, layer_graph in layer_graphs):
            for type_obj in graph.objects(node_uri, RDF.type):
                type_name = shorten_uri(str(type_obj))
                if type_name and type_name not in seen:
                    seen.add(type_name)
                    types.append(type_name)
        return types

    def _node_status(node_uri: URIRef) -> str | None:
        for graph in (layer_graph for _, layer_graph in layer_graphs):
            status_obj = next(graph.objects(node_uri, SCI_NS.projectStatus), None)
            if status_obj is None:
                continue
            status = str(status_obj).strip()
            if status:
                return status
        return None

    def _node_confidence(node_uri: URIRef) -> float | None:
        confidence_obj = next(provenance.objects(node_uri, SCI_NS.confidence), None)
        if confidence_obj is None:
            return None
        try:
            return float(str(confidence_obj))
        except ValueError as exc:
            raise click.ClickException(f"Invalid confidence value for {shorten_uri(str(node_uri))}") from exc

    def _causal_edge_kind(predicate: str) -> str | None:
        if predicate == str(SCIC_NS.causes):
            return "causes"
        if predicate == str(SCIC_NS.confounds):
            return "confounds"
        return None

    def _evidence_claim_bundle(claim_uri: URIRef) -> EvidenceClaimBundle | None:
        if (claim_uri, RDF.type, SCI_NS.Proposition) not in knowledge:
            return None

        evidence_summary = _collect_evidence_signals(knowledge, provenance, claim_uri)
        support_count = cast(int, evidence_summary["support_count"])
        dispute_count = cast(int, evidence_summary["dispute_count"])

        bundle: EvidenceClaimBundle = {
            "uri": str(claim_uri),
            "text": str(next(knowledge.objects(claim_uri, SCHEMA_NS.text), shorten_uri(str(claim_uri)))),
            "confidence": None,
            "sources": _source_strings(provenance, claim_uri),
            "support_count": support_count,
            "dispute_count": dispute_count,
        }

        confidence_obj = next(provenance.objects(claim_uri, SCI_NS.confidence), None)
        if confidence_obj is not None:
            try:
                bundle["confidence"] = float(str(confidence_obj))
            except ValueError as exc:
                raise click.ClickException(f"Invalid confidence value for {shorten_uri(str(claim_uri))}") from exc

        _apply_phase1_metadata_to_bundle(bundle, _load_proposition_phase1_metadata(provenance, claim_uri))
        _apply_evidence_semantics_to_bundle(bundle, _load_proposition_evidence_semantics(provenance, claim_uri))

        pre_registrations = _load_proposition_pre_registrations(provenance, claim_uri)
        if pre_registrations:
            bundle["pre_registrations"] = pre_registrations

        interaction_terms = _load_proposition_interaction_terms(provenance, claim_uri)
        if interaction_terms:
            bundle["interaction_terms"] = interaction_terms

        bridge_between = _load_proposition_bridge_hypotheses(provenance, claim_uri)
        if bridge_between:
            bundle["bridge_between"] = bridge_between

        falsifications = _load_proposition_falsifications(knowledge, claim_uri)
        if falsifications:
            bundle["falsifications"] = falsifications

        return bundle

    nodes: list[GraphExportNode] = []
    for node_id in sorted(node_layers):
        node_uri = URIRef(node_id)
        primary_layer = next((layer for layer in export_layers if layer in node_layers[node_id]), None)
        if primary_layer is None:
            continue
        nodes.append(
            GraphExportNode(
                id=build_graph_export_node_id(node_id),
                label=_node_label(node_uri),
                type=", ".join(_node_types(node_uri)) or None,
                graph_layer=primary_layer,
                status=_node_status(node_uri),
                confidence=_node_confidence(node_uri),
                source_refs=_source_strings(provenance, node_uri),
            )
        )

    edges = [edge_records[edge_id] for edge_id in sorted(edge_records)]

    layer_node_counts: dict[str, int] = {
        layer: sum(1 for membership_layers in node_layers.values() if layer in membership_layers)
        for layer in export_layers
    }

    layers: list[GraphExportLayer] = []
    for layer in export_layers:
        layers.append(
            GraphExportLayer(
                id=layer,
                node_count=layer_node_counts[layer],
                edge_count=len(layer_edge_ids[layer]),
                default_visible=True,
            )
        )

    project_root = _project_root_from_graph_path(graph_path)
    project_scope = GraphExportScope(
        id="project",
        kind="project",
        label=project_root.name or "Project",
        node_ids=[node.id for node in nodes],
        edge_ids=[edge.id for edge in edges],
        metadata={},
    )

    inquiry_scopes: list[GraphExportScope] = []
    causal_inquiries: dict[str, dict[str, object]] = {}
    evidence_edges: dict[str, EvidenceEdgeOverlay] = {}
    inquiry_prefix = str(PROJECT_NS) + "inquiry/"

    for graph in dataset.graphs():
        graph_id = str(graph.identifier)
        if not graph_id.startswith(inquiry_prefix):
            continue

        inquiry_uri = URIRef(graph_id)
        if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in graph:
            continue

        slug = graph_id[len(inquiry_prefix) :]
        label_obj = next(graph.objects(inquiry_uri, SKOS.prefLabel), None)
        status_obj = next(graph.objects(inquiry_uri, SCI_NS.inquiryStatus), None)
        inquiry_type_obj = next(graph.objects(inquiry_uri, SCI_NS.inquiryType), None)
        target_obj = next(graph.objects(inquiry_uri, SCI_NS.target), None)
        treatment_obj = next(graph.objects(inquiry_uri, SCI_NS.treatment), None)
        outcome_obj = next(graph.objects(inquiry_uri, SCI_NS.outcome), None)

        boundary_in = sorted(
            str(subject)
            for subject in graph.subjects(SCI_NS.boundaryRole, SCI_NS.BoundaryIn)
            if isinstance(subject, URIRef)
        )
        boundary_out = sorted(
            str(subject)
            for subject in graph.subjects(SCI_NS.boundaryRole, SCI_NS.BoundaryOut)
            if isinstance(subject, URIRef)
        )

        member_nodes: set[str] = set(boundary_in)
        member_nodes.update(boundary_out)
        statement_nodes_in_inquiry = {
            str(subject) for subject in graph.subjects(RDF.type, RDF.Statement) if isinstance(subject, URIRef)
        }
        for subject, predicate, object_ in graph:
            if isinstance(subject, URIRef) and subject != inquiry_uri:
                member_nodes.add(str(subject))
            if isinstance(object_, URIRef) and (
                predicate not in GRAPH_EXPORT_EDGE_METADATA_PREDICATES
                or predicate in {SCI_NS.target, SCI_NS.treatment, SCI_NS.outcome}
            ):
                member_nodes.add(str(object_))
        member_nodes.difference_update(statement_nodes_in_inquiry)
        member_nodes.intersection_update(node.id for node in nodes)

        edge_ids = [edge.id for edge in edges if edge.subject in member_nodes and edge.object in member_nodes]

        if "causal" in requested_overlays:
            inquiry_key = f"inquiry/{slug}"
            causal_edge_ids: list[str] = []
            causal_edge_map: dict[str, dict[str, str]] = {}

            for edge in edges:
                if edge.graph_layer != "graph/causal":
                    continue
                if edge.subject not in member_nodes or edge.object not in member_nodes:
                    continue
                kind = _causal_edge_kind(edge.predicate)
                if kind is None:
                    continue
                causal_edge_ids.append(edge.id)
                causal_edge_map[edge.id] = {"kind": kind}

            treatment = str(treatment_obj) if treatment_obj is not None and str(treatment_obj) in member_nodes else None
            if treatment_obj is not None and treatment is None:
                warnings.append(f"{inquiry_key}: skipped missing treatment ref {str(treatment_obj)}")

            outcome = str(outcome_obj) if outcome_obj is not None and str(outcome_obj) in member_nodes else None
            if outcome_obj is not None and outcome is None:
                warnings.append(f"{inquiry_key}: skipped missing outcome ref {str(outcome_obj)}")

            boundary_roles = {node_id: "BoundaryIn" for node_id in boundary_in if node_id in member_nodes}
            boundary_roles.update({node_id: "BoundaryOut" for node_id in boundary_out if node_id in member_nodes})

            causal_inquiries[inquiry_key] = {
                "node_ids": sorted(member_nodes),
                "edge_ids": sorted(causal_edge_ids),
                "treatment": treatment,
                "outcome": outcome,
                "boundary_roles": boundary_roles,
                "edges": causal_edge_map,
            }

        inquiry_scopes.append(
            GraphExportScope(
                id=f"inquiry/{slug}",
                kind="inquiry",
                label=str(label_obj).strip() if label_obj is not None and str(label_obj).strip() else slug,
                node_ids=sorted(member_nodes),
                edge_ids=sorted(edge_ids),
                metadata={
                    "status": str(status_obj) if status_obj is not None else "sketch",
                    "inquiry_type": str(inquiry_type_obj) if inquiry_type_obj is not None else "general",
                    "target": str(target_obj) if target_obj is not None else "",
                    "treatment": str(treatment_obj) if treatment_obj is not None else None,
                    "outcome": str(outcome_obj) if outcome_obj is not None else None,
                    "boundary_in": boundary_in,
                    "boundary_out": boundary_out,
                },
            )
        )

    if "evidence" in requested_overlays:
        for edge in edges:
            if not edge.claim_ids:
                continue

            claim_bundles: list[EvidenceClaimBundle] = []
            for claim_id in edge.claim_ids:
                claim_uri = URIRef(claim_id)
                claim_bundle = _evidence_claim_bundle(claim_uri)
                if claim_bundle is None:
                    warnings.append(f"{edge.id}: missing claim ref {claim_id}")
                    continue
                claim_bundles.append(claim_bundle)

            if claim_bundles:
                evidence_edges[edge.id] = {"claims": claim_bundles}

    return GraphExportPayload(
        schema_version=GRAPH_EXPORT_SCHEMA_VERSION,
        nodes=nodes,
        edges=edges,
        layers=layers,
        scopes=[project_scope, *sorted(inquiry_scopes, key=lambda scope: scope.id)],
        overlays=GraphExportOverlays(
            causal={"inquiries": causal_inquiries} if "causal" in requested_overlays else {},
            evidence={"edges": evidence_edges} if "evidence" in requested_overlays else {},
        ),
        warnings=warnings,
    )
