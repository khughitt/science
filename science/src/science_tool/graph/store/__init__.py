from __future__ import annotations

import hashlib
import importlib
import importlib.resources
import json
import re
import subprocess
from collections import deque
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

import click
from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD
from science_model.profiles import CORE_PROFILE
from science_model.profiles.schema import RelationKind
from science_model.reasoning import MeasurementModel, RivalModelPacket
from science_model.relations import relation_allows_kinds

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
from science_tool.graph.io import (
    BIOLINK_NS,
    CITO_NS,
    DCTERMS_NS,
    PROJECT_NS,
    REVISION_URI,
    SCHEMA_NS,
    SCI_NS,
    SCIC_NS,
    build_input_manifest as _build_input_manifest,
    project_root_from_graph_path as _project_root_from_graph_path,
    read_revision_manifest as _read_revision_manifest,
    save_canonical_graph_dataset,
)
from science_tool.graph.belief import aggregate_belief, collect_evidence_units
from science_tool.graph.sources import is_metadata_reference

from .constants import (DEFAULT_GRAPH_PATH, VALID_INQUIRY_TYPES, GRAPH_LAYERS, GRAPH_EXPORT_SCHEMA_VERSION, GRAPH_EXPORT_VISIBLE_LAYERS, GRAPH_EXPORT_EDGE_METADATA_PREDICATES, CURIE_PREFIXES, PROJECT_ENTITY_PREFIXES, PROJECT_ENTITY_PREFIX_KINDS, _RELATION_KIND_BY_PREDICATE, STRUCTURED_PROPOSITION_PREDICATES, EVIDENCE_STANCE_PREDICATES, INITIAL_GRAPH_TEMPLATE, PREDICATE_REGISTRY, BIOLINK_NS, CITO_NS, DCTERMS_NS, PROJECT_NS, REVISION_URI, SCHEMA_NS, SCI_NS, SCIC_NS)
from .types import (InquiryEdge, InquiryInfo, ClaimSummaryData, NeighborhoodSummaryData, QuestionSummaryData, PropositionEvidenceLine, PropositionPhase1Metadata, PropositionEvidenceSemantics, PropositionInteractionTerm, FalsificationRecord, EvidenceClaimBundle, EvidenceEdgeOverlay, EvidenceOverlayData, InquirySummaryData, ProjectSummaryData, EvidenceSignalSummary)
from .graphutil import _has_cycle


from .identity import (_entity_kind_from_uri, canonical_id_from_entity_uri, _slug, _graph_uri, _derive_relation_claim_text, _relation_claim_label, _edge_claims, _edge_statement_uri, _resolve_term, _resolve_center_entity, _about_tokens, shorten_uri, _short_name)
from .notebooks import (_uv_lock, _NOTEBOOKS_PYPROJECT, _copy_viz_notebook)
from .dataset import (init_graph_file, read_graph_stats, _load_dataset, _save_dataset, save_graph_dataset)
from .evidence_signals import (_linked_claims_for_hypothesis, _source_strings, _load_proposition_phase1_metadata, _load_proposition_evidence_semantics, _load_proposition_pre_registrations, _load_proposition_interaction_terms, _load_proposition_bridge_hypotheses, _load_proposition_falsifications, _json_literal, _evidence_targets_for_uri, _collect_evidence_signals, _apply_phase1_metadata_to_bundle, _apply_evidence_semantics_to_bundle, _evidence_type_strings, _collect_evidence_types)
from .mutations import (add_concept, add_article, add_proposition, add_observation, add_evidence_edge, add_finding, add_interpretation, add_discussion, add_falsification, add_mechanism, add_story, add_paper_entity, add_hypothesis, add_question, add_edge, add_inquiry, add_inquiry_node, add_inquiry_edge, add_assumption, add_transformation, add_data_package, set_boundary_role, set_param_metadata, migrate_addresses_direction, _warn_on_relation_direction_mismatch, _attach_edge_claims)
from .export import export_graph_payload


def list_inquiries(graph_path: Path) -> list[dict[str, str]]:
    """List all inquiries in the dataset, returning a list of summary dicts."""
    dataset = _load_dataset(graph_path)
    inquiry_prefix = str(PROJECT_NS) + "inquiry/"
    results: list[dict[str, str]] = []

    for ctx in dataset.graphs():
        graph_id = str(ctx.identifier)
        if not graph_id.startswith(inquiry_prefix):
            continue

        slug = graph_id[len(inquiry_prefix) :]
        inquiry_uri = URIRef(graph_id)

        # Only include actual inquiry graphs (must have Inquiry type)
        if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in ctx:
            continue

        label = ""
        status = ""
        target = ""
        created = ""

        for obj in ctx.objects(inquiry_uri, SKOS.prefLabel):
            label = str(obj)
        for obj in ctx.objects(inquiry_uri, SCI_NS.inquiryStatus):
            status = str(obj)
        for obj in ctx.objects(inquiry_uri, SCI_NS.target):
            target = str(obj)
        for obj in ctx.objects(inquiry_uri, DCTERMS_NS.created):
            created = str(obj)

        inquiry_type = ""
        for obj in ctx.objects(inquiry_uri, SCI_NS.inquiryType):
            inquiry_type = str(obj)
        if not inquiry_type:
            inquiry_type = "general"

        results.append(
            {
                "slug": slug,
                "label": label,
                "inquiry_type": inquiry_type,
                "status": status,
                "target": target,
                "created": created,
            }
        )

    return results


def get_inquiry(graph_path: Path, slug: str) -> InquiryInfo:
    """Get detailed information about a specific inquiry, including boundaries and edges."""
    safe_slug = _slug(slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    # Read metadata
    label = str(next(inquiry_graph.objects(inquiry_uri, SKOS.prefLabel), ""))
    status = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryStatus), ""))
    inquiry_type = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), "general"))
    target = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.target), ""))
    created = str(next(inquiry_graph.objects(inquiry_uri, DCTERMS_NS.created), ""))
    description = str(next(inquiry_graph.objects(inquiry_uri, SKOS.note), ""))

    # Read treatment/outcome (causal inquiries)
    treatment = next(inquiry_graph.objects(inquiry_uri, SCI_NS.treatment), None)
    outcome = next(inquiry_graph.objects(inquiry_uri, SCI_NS.outcome), None)

    # Collect boundary nodes
    boundary_in: list[str] = []
    boundary_out: list[str] = []
    for s, _p, o in inquiry_graph.triples((None, SCI_NS.boundaryRole, None)):
        if o == SCI_NS.BoundaryIn:
            boundary_in.append(str(s))
        elif o == SCI_NS.BoundaryOut:
            boundary_out.append(str(s))

    # Collect edges (excluding metadata predicates)
    metadata_predicates = {
        RDF.type,
        RDF.subject,
        RDF.predicate,
        RDF.object,
        SKOS.prefLabel,
        SKOS.note,
        SCI_NS.inquiryStatus,
        SCI_NS.inquiryType,
        SCI_NS.target,
        SCI_NS.boundaryRole,
        SCI_NS.treatment,
        SCI_NS.outcome,
        SCI_NS.tool,
        SCI_NS.paramValue,
        SCI_NS.paramSource,
        SCI_NS.paramNote,
        SCI_NS.paramRef,
        SCI_NS.backedByClaim,
        SCI_NS.validatedBy,
        DCTERMS_NS.created,
    }
    edges: list[InquiryEdge] = []
    for s, p, o in inquiry_graph:
        if p not in metadata_predicates:
            edge_info: InquiryEdge = {"subject": str(s), "predicate": str(p), "object": str(o)}
            if isinstance(s, URIRef) and isinstance(p, URIRef) and isinstance(o, URIRef):
                claim_uris = _edge_claims(inquiry_graph, s, p, o)
                if claim_uris:
                    edge_info["claims"] = [str(uri) for uri in claim_uris]
            edges.append(edge_info)

    return {
        "slug": safe_slug,
        "label": label,
        "status": status,
        "inquiry_type": inquiry_type,
        "target": target,
        "created": created,
        "description": description,
        "treatment": str(treatment) if treatment else None,
        "outcome": str(outcome) if outcome else None,
        "boundary_in": boundary_in,
        "boundary_out": boundary_out,
        "edges": edges,
    }


def set_treatment_outcome(
    graph_path: Path,
    inquiry_slug: str,
    treatment: str,
    outcome: str,
) -> None:
    """Set treatment and outcome variables for a causal inquiry."""
    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    inquiry_type = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), "general"))
    if inquiry_type != "causal":
        raise ValueError(f"Treatment/outcome only supported for causal inquiries (got '{inquiry_type}')")

    treatment_uri = _resolve_term(treatment)
    outcome_uri = _resolve_term(outcome)

    # Remove any existing treatment/outcome
    inquiry_graph.remove((inquiry_uri, SCI_NS.treatment, None))
    inquiry_graph.remove((inquiry_uri, SCI_NS.outcome, None))

    inquiry_graph.add((inquiry_uri, SCI_NS.treatment, treatment_uri))
    inquiry_graph.add((inquiry_uri, SCI_NS.outcome, outcome_uri))

    _save_dataset(dataset, graph_path)


def render_inquiry_doc(graph_path: Path, slug: str) -> str:
    """Render an inquiry as a markdown document string.

    Calls get_inquiry() to gather data, then builds a markdown document
    with metadata, boundary node tables, interior nodes, edge list,
    assumptions, and parameters.
    """
    info = get_inquiry(graph_path, slug)
    safe_slug = _slug(slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    # Helper: get label for a URI from knowledge or inquiry graph
    def _label_for(uri_str: str) -> str:
        uri_ref = URIRef(uri_str)
        label = next(knowledge.objects(uri_ref, SKOS.prefLabel), None)
        if label is None:
            label = next(inquiry_graph.objects(uri_ref, SKOS.prefLabel), None)
        return str(label) if label else shorten_uri(uri_str)

    # Helper: get rdf:type for a URI (excluding sci:Concept base type)
    def _type_for(uri_str: str) -> str:
        uri_ref = URIRef(uri_str)
        types: list[str] = []
        for t in knowledge.objects(uri_ref, RDF.type):
            t_str = str(t)
            if t_str != str(SCI_NS.Concept):
                types.append(shorten_uri(t_str))
        for t in inquiry_graph.objects(uri_ref, RDF.type):
            t_str = str(t)
            short = shorten_uri(t_str)
            if t_str != str(SCI_NS.Concept) and short not in types:
                types.append(short)
        return ", ".join(types) if types else ""

    # Helper: get note for a URI
    def _note_for(uri_str: str) -> str:
        uri_ref = URIRef(uri_str)
        note = next(knowledge.objects(uri_ref, SKOS.note), None)
        if note is None:
            note = next(inquiry_graph.objects(uri_ref, SKOS.note), None)
        return str(note) if note else ""

    # Helper: get validatedBy for a URI
    def _validated_by(uri_str: str) -> str:
        uri_ref = URIRef(uri_str)
        vals: list[str] = []
        for v in inquiry_graph.objects(uri_ref, SCI_NS.validatedBy):
            vals.append(shorten_uri(str(v)))
        return ", ".join(vals) if vals else ""

    # Helper: get provenance for a URI
    def _provenance_for(uri_str: str) -> str:
        uri_ref = URIRef(uri_str)
        provenance = dataset.graph(_graph_uri("graph/provenance"))
        sources: list[str] = []
        for src in provenance.objects(uri_ref, PROV.wasDerivedFrom):
            sources.append(shorten_uri(str(src)))
        return ", ".join(sources) if sources else ""

    # Target label
    target_str = info["target"]
    target_id = shorten_uri(target_str)

    # Build boundary sets for interior detection
    boundary_set = set(info["boundary_in"]) | set(info["boundary_out"])

    # Find interior nodes: nodes in edges that are not boundary and not the inquiry itself
    interior_nodes: list[str] = []
    seen: set[str] = set()
    for edge in info["edges"]:
        for uri_str in (edge["subject"], edge["object"]):
            if uri_str not in boundary_set and uri_str not in seen and uri_str != str(inquiry_uri):
                interior_nodes.append(uri_str)
                seen.add(uri_str)

    # Build boundary_in rows
    boundary_in_rows = ""
    for uri_str in info["boundary_in"]:
        name = _label_for(uri_str)
        typ = _type_for(uri_str)
        prov = _provenance_for(uri_str)
        boundary_in_rows += f"| {name} | {typ} | {prov} |\n"

    # Build boundary_out rows
    boundary_out_rows = ""
    for uri_str in info["boundary_out"]:
        name = _label_for(uri_str)
        typ = _type_for(uri_str)
        validation = _validated_by(uri_str)
        boundary_out_rows += f"| {name} | {typ} | {validation} |\n"

    # Build interior rows
    interior_rows = ""
    for uri_str in interior_nodes:
        name = _label_for(uri_str)
        typ = _type_for(uri_str)
        note = _note_for(uri_str)
        interior_rows += f"| {name} | {typ} | {note} |\n"

    # Build edge list
    edge_lines: list[str] = []
    for edge in info["edges"]:
        s = shorten_uri(edge["subject"])
        p = shorten_uri(edge["predicate"])
        o = shorten_uri(edge["object"])
        edge_lines.append(f"- {s} --[{p}]--> {o}")
    edge_list = "\n".join(edge_lines) if edge_lines else "(no edges)"

    # Build assumption rows
    assumption_rows = ""
    for s, _p, _o in inquiry_graph.triples((None, RDF.type, SCI_NS.Assumption)):
        name = _label_for(str(s))
        evidence = _provenance_for(str(s))
        # Also check sci:assumes edges for evidence
        for _s2, _p2, ev in inquiry_graph.triples((s, SCI_NS.assumes, None)):
            ev_label = shorten_uri(str(ev))
            evidence = ev_label if not evidence else f"{evidence}, {ev_label}"
        assumption_rows += f"| {name} | {evidence} |\n"

    # Build param rows
    param_rows = ""
    for s in set(inquiry_graph.subjects(SCI_NS.paramValue, None)):
        name = _label_for(str(s))
        value = str(next(inquiry_graph.objects(s, SCI_NS.paramValue), ""))
        source = str(next(inquiry_graph.objects(s, SCI_NS.paramSource), ""))
        refs_list: list[str] = []
        for r in inquiry_graph.objects(s, SCI_NS.paramRef):
            refs_list.append(str(r))
        refs = ", ".join(refs_list)
        note = str(next(inquiry_graph.objects(s, SCI_NS.paramNote), ""))
        param_rows += f"| {name} | {value} | {source} | {refs} | {note} |\n"

    # Also check knowledge graph for params
    for s_uri_str in list(set([*info["boundary_in"], *info["boundary_out"], *[str(n) for n in interior_nodes]])):
        s_ref = URIRef(s_uri_str)
        val = next(knowledge.objects(s_ref, SCI_NS.paramValue), None)
        if val is not None and s_ref not in set(inquiry_graph.subjects(SCI_NS.paramValue, None)):
            name = _label_for(s_uri_str)
            value = str(val)
            source = str(next(knowledge.objects(s_ref, SCI_NS.paramSource), ""))
            refs_list = []
            for r in knowledge.objects(s_ref, SCI_NS.paramRef):
                refs_list.append(str(r))
            refs = ", ".join(refs_list)
            note = str(next(knowledge.objects(s_ref, SCI_NS.paramNote), ""))
            param_rows += f"| {name} | {value} | {source} | {refs} | {note} |\n"

    # Build unknown rows — check both inquiry graph and knowledge graph
    unknown_rows = ""
    unknown_seen: set[str] = set()
    for s, _p3, _o3 in inquiry_graph.triples((None, RDF.type, SCI_NS.Unknown)):
        uri_str = str(s)
        if uri_str not in unknown_seen:
            unknown_seen.add(uri_str)
            name = _label_for(uri_str)
            note = _note_for(uri_str)
            unknown_rows += f"| {name} | {note} |\n"
    # Also check knowledge graph for Unknown-typed nodes referenced in edges
    all_edge_nodes = set()
    for edge in info["edges"]:
        all_edge_nodes.add(edge["subject"])
        all_edge_nodes.add(edge["object"])
    for node_str in all_edge_nodes:
        if node_str not in unknown_seen and (URIRef(node_str), RDF.type, SCI_NS.Unknown) in knowledge:
            unknown_seen.add(node_str)
            name = _label_for(node_str)
            note = _note_for(node_str)
            unknown_rows += f"| {name} | {note} |\n"

    # Assemble document
    lines = [
        "---",
        f'id: "inquiry:{info["slug"]}"',
        'type: "inquiry"',
        f'title: "{info["label"]}"',
        f'status: "{info["status"]}"',
        "source_refs: []",
        "related: []",
        f'created: "{info["created"]}"',
        f'updated: "{info["created"]}"',
        f'target: "{target_id}"',
        "---",
        "",
        f"# Inquiry: {info['label']}",
        "",
        "## Summary",
        "",
        info["description"] or "(no description)",
        "",
        "## Variables",
        "",
        "### Boundary In (Givens)",
        "",
        "| Variable | Type | Provenance |",
        "|---|---|---|",
        boundary_in_rows.rstrip("\n") if boundary_in_rows else "",
        "",
        "### Boundary Out (Produces)",
        "",
        "| Variable | Type | Validation |",
        "|---|---|---|",
        boundary_out_rows.rstrip("\n") if boundary_out_rows else "",
        "",
        "### Interior",
        "",
        "| Variable | Type | Notes |",
        "|---|---|---|",
        interior_rows.rstrip("\n") if interior_rows else "",
        "",
        "## Data Flow",
        "",
        edge_list,
        "",
        "## Assumptions",
        "",
        "| Assumption | Evidence |",
        "|---|---|",
        assumption_rows.rstrip("\n") if assumption_rows else "",
        "",
        "## Unknowns",
        "",
        "| Unknown | Notes |",
        "|---|---|",
        unknown_rows.rstrip("\n") if unknown_rows else "",
        "",
        "## Parameters",
        "",
        "| Parameter | Value | Source | References | Note |",
        "|---|---|---|---|---|",
        param_rows.rstrip("\n") if param_rows else "",
        "",
    ]

    return "\n".join(lines)


def validate_inquiry(graph_path: Path, slug: str) -> list[dict]:
    """Validate an inquiry graph, returning a list of check-result dicts.

    Each result has keys: check (str), status ("pass"/"fail"/"warn"), message (str),
    and optionally details (list).
    """
    safe_slug = _slug(slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    status = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryStatus), "sketch"))
    target = next(inquiry_graph.objects(inquiry_uri, SCI_NS.target), None)

    # Collect boundary nodes
    boundary_in: set[URIRef] = set()
    boundary_out: set[URIRef] = set()
    for s, _p, o in inquiry_graph.triples((None, SCI_NS.boundaryRole, None)):
        if not isinstance(s, URIRef):
            continue
        if o == SCI_NS.BoundaryIn:
            boundary_in.add(s)
        elif o == SCI_NS.BoundaryOut:
            boundary_out.add(s)

    # Build adjacency from flow edges (feedsInto, produces, and scic:causes for causal inquiries)
    flow_predicates = {SCI_NS.feedsInto, SCI_NS.produces, SCIC_NS.causes}
    adjacency: dict[URIRef, list[URIRef]] = {}
    all_flow_nodes: set[URIRef] = set()
    for s, p, o in inquiry_graph:
        if p in flow_predicates and isinstance(s, URIRef) and isinstance(o, URIRef):
            adjacency.setdefault(s, []).append(o)
            all_flow_nodes.add(s)
            all_flow_nodes.add(o)

    results: list[dict] = []

    # 1. boundary_reachability — BFS from BoundaryIn, check all BoundaryOut reachable
    reachable: set[URIRef] = set()
    queue: deque[URIRef] = deque(boundary_in)
    while queue:
        node = queue.popleft()
        if node in reachable:
            continue
        reachable.add(node)
        for neighbor in adjacency.get(node, []):
            if neighbor not in reachable:
                queue.append(neighbor)

    unreachable_out = [str(n) for n in boundary_out if n not in reachable]
    if unreachable_out:
        results.append(
            {
                "check": "boundary_reachability",
                "status": "fail",
                "message": f"{len(unreachable_out)} BoundaryOut node(s) not reachable from any BoundaryIn",
                "details": unreachable_out,
            }
        )
    else:
        results.append(
            {
                "check": "boundary_reachability",
                "status": "pass",
                "message": "All BoundaryOut nodes reachable from BoundaryIn",
            }
        )

    # 2. no_cycles — Kahn's algorithm (topological sort)
    in_degree: dict[URIRef, int] = {n: 0 for n in all_flow_nodes}
    for src, dsts in adjacency.items():
        for dst in dsts:
            in_degree[dst] = in_degree.get(dst, 0) + 1

    topo_queue: deque[URIRef] = deque(n for n, d in in_degree.items() if d == 0)
    sorted_count = 0
    while topo_queue:
        node = topo_queue.popleft()
        sorted_count += 1
        for neighbor in adjacency.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                topo_queue.append(neighbor)

    if sorted_count < len(all_flow_nodes):
        results.append(
            {
                "check": "no_cycles",
                "status": "fail",
                "message": "Cycle detected in flow edges",
            }
        )
    else:
        results.append(
            {
                "check": "no_cycles",
                "status": "pass",
                "message": "No cycles in flow edges",
            }
        )

    # 3. unknown_resolution — find sci:Unknown nodes used in this inquiry
    unknown_nodes: list[str] = []
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    for node in all_flow_nodes:
        if (node, RDF.type, SCI_NS.Unknown) in knowledge or (node, RDF.type, SCI_NS.Unknown) in inquiry_graph:
            unknown_nodes.append(str(node))

    if unknown_nodes and status != "sketch":
        results.append(
            {
                "check": "unknown_resolution",
                "status": "fail",
                "message": f"{len(unknown_nodes)} sci:Unknown node(s) in non-sketch inquiry",
                "details": unknown_nodes,
            }
        )
    else:
        results.append(
            {
                "check": "unknown_resolution",
                "status": "pass",
                "message": "No unresolved Unknown nodes" if not unknown_nodes else "Unknown nodes allowed in sketch",
            }
        )

    # 4. target_exists — check the target has an rdf:type somewhere
    if target is not None:
        has_type = any(True for _ in knowledge.triples((target, RDF.type, None)))
        if not has_type:
            # Also check other graphs
            has_type = any(True for _ in dataset.triples((target, RDF.type, None)))
        if has_type:
            results.append(
                {
                    "check": "target_exists",
                    "status": "pass",
                    "message": "Target node exists",
                }
            )
        else:
            results.append(
                {
                    "check": "target_exists",
                    "status": "fail",
                    "message": f"Target {target} has no rdf:type in the knowledge graph",
                }
            )
    else:
        results.append(
            {
                "check": "target_exists",
                "status": "warn",
                "message": "No target specified for inquiry",
            }
        )

    # 5. orphaned_interior — interior nodes with no incoming or outgoing flow edges
    boundary_all = boundary_in | boundary_out
    orphaned: list[str] = []
    for node in all_flow_nodes:
        if node in boundary_all or node == inquiry_uri:
            continue
        has_incoming = any(node in adjacency.get(src, []) for src in all_flow_nodes)
        has_outgoing = node in adjacency and len(adjacency[node]) > 0
        if not has_incoming or not has_outgoing:
            orphaned.append(str(node))

    if orphaned:
        results.append(
            {
                "check": "orphaned_interior",
                "status": "warn",
                "message": f"{len(orphaned)} interior node(s) missing incoming or outgoing flow edges",
                "details": orphaned,
            }
        )
    else:
        results.append(
            {
                "check": "orphaned_interior",
                "status": "pass",
                "message": "All interior nodes have incoming and outgoing flow edges",
            }
        )

    # === Causal-specific checks (only for type=causal) ===
    inquiry_type = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), "general"))
    if inquiry_type == "causal":
        causal_graph = dataset.graph(_graph_uri("graph/causal"))

        # Collect inquiry member entities (boundary + flow nodes)
        members = boundary_in | boundary_out | all_flow_nodes

        # Filter causal edges to inquiry members
        causal_edges = [
            (str(s), str(o))
            for s, _, o in causal_graph.triples((None, SCIC_NS.causes, None))
            if s in members and o in members
        ]

        # causal_acyclicity
        if _has_cycle(causal_edges):
            results.append(
                {
                    "check": "causal_acyclicity",
                    "status": "fail",
                    "message": "Cycle detected in scic:causes edges among inquiry variables",
                }
            )
        else:
            results.append(
                {
                    "check": "causal_acyclicity",
                    "status": "pass",
                    "message": "Causal edges are acyclic",
                }
            )

        # confounders_declared — check for common causes without scic:confounds
        # A "common cause" is a variable that causes 2+ other inquiry variables
        children: dict[str, set[str]] = {}
        for s_str, o_str in causal_edges:
            children.setdefault(s_str, set()).add(o_str)

        common_causes = [parent for parent, targets in children.items() if len(targets) >= 2]

        # Check if common causes have scic:confounds edges declared
        confound_sources: set[str] = set()
        for s, _p, o in causal_graph.triples((None, SCIC_NS.confounds, None)):
            if s in members:
                confound_sources.add(str(s))

        undeclared = [c for c in common_causes if c not in confound_sources]
        if undeclared:
            short_names = [shorten_uri(u) for u in undeclared]
            results.append(
                {
                    "check": "confounders_declared",
                    "status": "warn",
                    "message": f"Common cause(s) without scic:confounds declaration: {', '.join(short_names)}",
                }
            )
        else:
            results.append(
                {
                    "check": "confounders_declared",
                    "status": "pass",
                    "message": "All common causes have confounders declared"
                    if common_causes
                    else "No common causes found",
                }
            )

        # identifiability + adjustment_sets — requires pgmpy (optional)
        treatment_uri = next(inquiry_graph.objects(inquiry_uri, SCI_NS.treatment), None)
        outcome_uri = next(inquiry_graph.objects(inquiry_uri, SCI_NS.outcome), None)

        if not treatment_uri or not outcome_uri:
            results.append(
                {
                    "check": "identifiability",
                    "status": "skip",
                    "message": "Treatment or outcome not set — cannot check identifiability",
                }
            )
            results.append(
                {
                    "check": "adjustment_sets",
                    "status": "skip",
                    "message": "Treatment or outcome not set — cannot compute adjustment sets",
                }
            )
        else:
            treatment_name = shorten_uri(str(treatment_uri)).rsplit("/", 1)[-1]
            outcome_name = shorten_uri(str(outcome_uri)).rsplit("/", 1)[-1]

            _BN: Any | None = None
            CausalInference: Any | None = None
            try:
                pgmpy_models = importlib.import_module("pgmpy.models")
                bn_cls = getattr(pgmpy_models, "DiscreteBayesianNetwork", None)
                if bn_cls is None:
                    bn_cls = getattr(pgmpy_models, "BayesianNetwork")
                _BN = bn_cls
                causal_inference_module = importlib.import_module("pgmpy.inference")
                CausalInference = getattr(causal_inference_module, "CausalInference")
            except (AttributeError, ImportError):
                pass

            if _BN is None or CausalInference is None:
                results.append(
                    {
                        "check": "identifiability",
                        "status": "skip",
                        "message": "pgmpy not installed — install with: uv add pgmpy",
                    }
                )
                results.append(
                    {
                        "check": "adjustment_sets",
                        "status": "skip",
                        "message": "pgmpy not installed — install with: uv add pgmpy",
                    }
                )
            else:
                edge_list = [
                    (shorten_uri(s).rsplit("/", 1)[-1], shorten_uri(o).rsplit("/", 1)[-1]) for s, o in causal_edges
                ]
                if edge_list:
                    try:
                        model = _BN(edge_list)
                        ci = CausalInference(model)
                        adj_sets = ci.get_all_backdoor_adjustment_sets(treatment_name, outcome_name)
                        adj_list = [set(s) for s in adj_sets]
                        if adj_list:
                            results.append(
                                {
                                    "check": "identifiability",
                                    "status": "pass",
                                    "message": f"Causal effect {treatment_name} -> {outcome_name}"
                                    " is identifiable via back-door",
                                }
                            )
                            sets_str = "; ".join(str(s) for s in adj_list)
                            results.append(
                                {
                                    "check": "adjustment_sets",
                                    "status": "info",
                                    "message": f"Valid adjustment sets: {sets_str}",
                                }
                            )
                        else:
                            results.append(
                                {
                                    "check": "identifiability",
                                    "status": "warn",
                                    "message": f"No valid back-door adjustment set found for"
                                    f" {treatment_name} -> {outcome_name}",
                                }
                            )
                            results.append(
                                {
                                    "check": "adjustment_sets",
                                    "status": "info",
                                    "message": "No valid adjustment sets found",
                                }
                            )
                    except Exception as exc:
                        results.append(
                            {
                                "check": "identifiability",
                                "status": "warn",
                                "message": f"Could not compute identifiability: {exc}",
                            }
                        )
                        results.append(
                            {
                                "check": "adjustment_sets",
                                "status": "skip",
                                "message": f"Could not compute adjustment sets: {exc}",
                            }
                        )
                else:
                    results.append(
                        {
                            "check": "identifiability",
                            "status": "skip",
                            "message": "No causal edges found — cannot assess identifiability",
                        }
                    )
                    results.append(
                        {
                            "check": "adjustment_sets",
                            "status": "skip",
                            "message": "No causal edges found",
                        }
                    )

    # 6. provenance_completeness — specified+ inquiries: all assumptions must have prov:wasDerivedFrom
    if status != "sketch":
        provenance_graph = dataset.graph(_graph_uri("graph/provenance"))
        missing_prov: list[str] = []
        for s, _p, _o in inquiry_graph.triples((None, RDF.type, SCI_NS.Assumption)):
            has_source = any(True for _ in provenance_graph.triples((s, PROV.wasDerivedFrom, None)))
            if not has_source:
                # Also check knowledge graph for inline source
                has_source = any(True for _ in knowledge.triples((s, PROV.wasDerivedFrom, None)))
            if not has_source:
                missing_prov.append(str(s))

        if missing_prov:
            results.append(
                {
                    "check": "provenance_completeness",
                    "status": "fail",
                    "message": f"{len(missing_prov)} assumption(s) missing provenance (prov:wasDerivedFrom)",
                    "details": missing_prov,
                }
            )
        else:
            results.append(
                {
                    "check": "provenance_completeness",
                    "status": "pass",
                    "message": "All assumptions have provenance",
                }
            )

    return results


def import_snapshot(graph_path: Path, snapshot_path: Path) -> int:
    """Import a Turtle snapshot into :graph/knowledge and record provenance. Returns triple count."""
    if not snapshot_path.exists():
        raise click.ClickException(f"Snapshot file not found: {snapshot_path}")

    from rdflib import Graph

    snapshot = Graph()
    snapshot.parse(str(snapshot_path), format="turtle")
    imported_count = len(snapshot)

    if imported_count == 0:
        raise click.ClickException(f"Snapshot contains no triples: {snapshot_path}")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    for triple in snapshot:
        knowledge.add(triple)

    # Record import provenance
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    import_uri = URIRef(PROJECT_NS[f"import/{_slug(snapshot_path.stem)}"])
    import_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for triple in list(provenance.triples((import_uri, None, None))):
        provenance.remove(triple)

    provenance.add((import_uri, RDF.type, PROV.Activity))
    provenance.add((import_uri, SCHEMA_NS.name, Literal(f"Import: {snapshot_path.name}")))
    provenance.add((import_uri, PROV.generatedAtTime, Literal(import_time, datatype=XSD.dateTime)))
    provenance.add((import_uri, SCHEMA_NS.size, Literal(imported_count, datatype=XSD.integer)))

    _save_dataset(dataset, graph_path)
    return imported_count


def stamp_revision(graph_path: Path) -> str:
    """Update graph revision metadata without adding entities. Returns the revision timestamp."""
    dataset = _load_dataset(graph_path)
    _save_dataset(dataset, graph_path)

    # Read back the stamped time
    dataset = _load_dataset(graph_path)
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    time_obj = next(provenance.objects(REVISION_URI, SCHEMA_NS.dateModified), None)
    return str(time_obj) if time_obj else "unknown"


def query_predicates() -> list[dict[str, str]]:
    return list(PREDICATE_REGISTRY)


def validate_graph(graph_path: Path) -> tuple[list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []

    try:
        dataset = _load_dataset(graph_path)
    except Exception as exc:  # noqa: BLE001
        rows.append(
            {
                "check": "parseable_trig",
                "status": "fail",
                "details": f"failed to parse graph.trig: {exc}",
            }
        )
        return rows, True

    rows.append(
        {
            "check": "parseable_trig",
            "status": "pass",
            "details": "graph.trig parsed successfully",
        }
    )

    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    causal = dataset.graph(_graph_uri("graph/causal"))

    provenance_failures = 0
    for entity_type in (SCI_NS.Proposition, SCI_NS.Hypothesis):
        for entity, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            if not any(provenance.triples((entity, PROV.wasDerivedFrom, None))):
                provenance_failures += 1

    if provenance_failures:
        rows.append(
            {
                "check": "provenance_completeness",
                "status": "fail",
                "details": f"{provenance_failures} proposition/hypothesis entities missing prov:wasDerivedFrom",
            }
        )
    else:
        rows.append(
            {
                "check": "provenance_completeness",
                "status": "pass",
                "details": "all propositions and hypotheses have provenance links",
            }
        )

    edges = [(str(subj), str(obj)) for subj, _, obj in causal.triples((None, SCIC_NS.causes, None))]
    if _has_cycle(edges):
        rows.append(
            {
                "check": "causal_acyclicity",
                "status": "fail",
                "details": "cycle detected in scic:causes edges",
            }
        )
    else:
        rows.append(
            {
                "check": "causal_acyclicity",
                "status": "pass",
                "details": "causal graph is acyclic",
            }
        )

    # Orphaned nodes: entities with rdf:type but no other triples as subject or object
    typed_entities = set()
    for entity_type in (SCI_NS.Concept, SCI_NS.Proposition, SCI_NS.Hypothesis, SCI_NS.Question, SCI_NS.Task):
        for entity, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            typed_entities.add(entity)
    for entity, _, _ in knowledge.triples((None, RDF.type, SCIC_NS.Variable)):
        typed_entities.add(entity)

    # Predicates that describe the node itself (metadata), not edges to other entities
    metadata_preds = {
        RDF.type,
        SKOS.prefLabel,
        SKOS.note,
        SKOS.definition,
        SCHEMA_NS.identifier,
        SCHEMA_NS.text,
        SCI_NS.maturity,
        SCI_NS.projectStatus,
    }

    orphaned = 0
    for entity in typed_entities:
        # Count triples where entity appears as subject (excluding metadata predicates)
        as_subject = sum(1 for _, p, _ in knowledge.triples((entity, None, None)) if p not in metadata_preds)
        # Count triples where entity appears as object
        as_object = sum(1 for _ in knowledge.triples((None, None, entity)))
        if as_subject == 0 and as_object == 0:
            orphaned += 1

    if orphaned:
        rows.append(
            {
                "check": "orphaned_nodes",
                "status": "warn",
                "details": f"{orphaned} entities have no edges to other entities",
            }
        )
    else:
        rows.append(
            {
                "check": "orphaned_nodes",
                "status": "pass",
                "details": "all entities have at least one edge",
            }
        )

    has_failures = any(row["status"] == "fail" for row in rows)
    return rows, has_failures


def diff_graph_inputs(graph_path: Path, mode: str) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    baseline = _read_revision_manifest(dataset)
    current = _build_input_manifest(graph_path=graph_path)

    rows: list[dict[str, str]] = []

    for rel_path, current_meta in current.items():
        baseline_meta = baseline.get(rel_path)
        if baseline_meta is None:
            rows.append({"path": rel_path, "status": "stale", "reason": "new_file"})
            continue

        mtime_changed = current_meta["mtime_ns"] != baseline_meta.get("mtime_ns")
        hash_changed = current_meta["sha256"] != baseline_meta.get("sha256")

        reason: str | None = None
        if mode == "mtime":
            if mtime_changed:
                reason = "mtime_changed"
        elif mode == "hash":
            if hash_changed:
                reason = "hash_changed"
        elif mode == "hybrid":
            if hash_changed:
                reason = "hash_changed"
            elif mtime_changed:
                reason = "mtime_changed"
        else:
            raise click.ClickException(f"Unsupported diff mode: {mode}")

        if reason is not None:
            rows.append({"path": rel_path, "status": "stale", "reason": reason})

    for removed in sorted(set(baseline.keys()) - set(current.keys())):
        rows.append({"path": removed, "status": "stale", "reason": "removed_file"})

    rows.sort(key=lambda row: row["path"])
    return rows


def query_neighborhood(
    graph_path: Path,
    center: str,
    hops: int,
    graph_layer: str,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    layer = dataset.graph(_graph_uri(graph_layer))

    center_uri = _resolve_center_entity(center)
    adjacency: dict[URIRef, set[URIRef]] = {}
    triples: list[tuple[URIRef, URIRef, URIRef]] = []

    for subj, pred, obj in layer:
        if not isinstance(subj, URIRef) or not isinstance(pred, URIRef) or not isinstance(obj, URIRef):
            continue
        triples.append((subj, pred, obj))
        adjacency.setdefault(subj, set()).add(obj)
        adjacency.setdefault(obj, set()).add(subj)

    visited: set[URIRef] = {center_uri}
    queue: deque[tuple[URIRef, int]] = deque([(center_uri, 0)])
    while queue:
        node, depth = queue.popleft()
        if depth >= hops:
            continue
        for neighbor in adjacency.get(node, set()):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, depth + 1))

    rows: list[dict[str, str]] = []
    for subj, pred, obj in triples:
        if subj in visited or obj in visited:
            rows.append(
                {
                    "subject": str(subj),
                    "predicate": str(pred),
                    "object": str(obj),
                }
            )
    return rows[:limit]


def query_claims(graph_path: Path, about: str, limit: int) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    tokens = _about_tokens(about)
    rows: list[dict[str, str]] = []
    for prop_uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Proposition)):
        text_obj = next(knowledge.objects(prop_uri, SCHEMA_NS.text), None)
        if text_obj is None:
            continue
        text = str(text_obj)
        if not any(token in text.lower() for token in tokens):
            continue

        sources = sorted({str(src) for src in provenance.objects(prop_uri, PROV.wasDerivedFrom)})
        rows.append(
            {
                "claim": str(prop_uri),
                "text": text,
                "sources": "; ".join(sources),
            }
        )
    return rows[:limit]


def query_evidence(
    graph_path: Path,
    target_ref: str,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    target_uri = _resolve_center_entity(target_ref)
    rows: list[dict[str, str]] = []
    seen: dict[tuple[str, str], dict[str, str]] = {}

    if (target_uri, RDF.type, SCI_NS.Hypothesis) in knowledge:
        _append_evidence_rows(
            rows=rows,
            seen=seen,
            knowledge=knowledge,
            provenance=provenance,
            target_uri=target_uri,
        )
        for claim_uri in _linked_claims_for_hypothesis(knowledge, target_uri):
            _append_evidence_rows(
                rows=rows,
                seen=seen,
                knowledge=knowledge,
                provenance=provenance,
                target_uri=claim_uri,
            )
    else:
        _append_evidence_rows(
            rows=rows,
            seen=seen,
            knowledge=knowledge,
            provenance=provenance,
            target_uri=target_uri,
        )

    return rows[:limit]


def _append_evidence_rows(
    rows: list[dict[str, str]],
    seen: dict[tuple[str, str], dict[str, str]],
    knowledge,
    provenance,
    target_uri: URIRef,
) -> None:
    allowed_predicates: tuple[tuple[URIRef, str], ...] = (
        (CITO_NS.supports, "supports"),
        (CITO_NS.disputes, "disputes"),
    )

    for predicate_uri, relation in allowed_predicates:
        for subj, _, _ in knowledge.triples((None, predicate_uri, target_uri)):
            if isinstance(subj, URIRef):
                _append_row(
                    rows=rows,
                    seen=seen,
                    knowledge=knowledge,
                    provenance=provenance,
                    evidence_uri=subj,
                    relation=relation,
                )


def _append_row(
    rows: list[dict[str, str]],
    seen: dict[tuple[str, str], dict[str, str]],
    knowledge,
    provenance,
    evidence_uri: URIRef,
    relation: str,
    fallback_uri: URIRef | None = None,
) -> None:
    key = (str(evidence_uri), relation)
    text_obj = (
        next(knowledge.objects(evidence_uri, SCHEMA_NS.text), None)
        or next(knowledge.objects(evidence_uri, SCHEMA_NS.description), None)
        or next(knowledge.objects(evidence_uri, SKOS.prefLabel), None)
    )
    text = str(text_obj) if text_obj else _short_name(str(evidence_uri))

    sources = _source_strings(provenance, evidence_uri, fallback_uri)
    if fallback_uri is not None and not text:
        fallback_text_obj = next(knowledge.objects(fallback_uri, SCHEMA_NS.text), None)
        text = str(fallback_text_obj) if fallback_text_obj else text

    existing_row = seen.get(key)
    if existing_row is not None:
        existing_sources = {source for source in existing_row["sources"].split("; ") if source}
        existing_sources.update(sources)
        existing_row["sources"] = "; ".join(sorted(existing_sources))
        if not existing_row["text"] and text:
            existing_row["text"] = text
        return

    row = {
        "evidence": str(evidence_uri),
        "relation": relation,
        "text": text,
        "sources": "; ".join(sources),
    }
    rows.append(row)
    seen[key] = row


def _summary_targets(knowledge, *, include_hypotheses: bool) -> list[URIRef]:
    entity_types = [SCI_NS.Proposition]
    if include_hypotheses:
        entity_types.append(SCI_NS.Hypothesis)

    seen: set[URIRef] = set()
    targets: list[URIRef] = []
    for entity_type in entity_types:
        for uri, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            if not isinstance(uri, URIRef) or uri in seen:
                continue
            seen.add(uri)
            targets.append(uri)
    return targets


def _claim_summary_data(knowledge, provenance, uri: URIRef) -> ClaimSummaryData | None:
    evidence_summary = _collect_evidence_signals(knowledge, provenance, uri)
    support_count = cast(int, evidence_summary["support_count"])
    dispute_count = cast(int, evidence_summary["dispute_count"])
    source_count = cast(int, evidence_summary["source_count"])
    evidence_types = sorted(_collect_evidence_types(knowledge, provenance, uri))
    has_empirical_data = any(
        evidence_type in {"empirical_data_evidence", "benchmark_evidence"} for evidence_type in evidence_types
    )
    belief = aggregate_belief(
        collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, uri))
    )
    belief_state = belief.magnitude.value
    contested = belief.contested
    belief_display = belief.display()
    evidence_semantics = _load_proposition_evidence_semantics(provenance, uri)
    statistical_support = evidence_semantics.get("statistical_support", "")
    mechanistic_support = evidence_semantics.get("mechanistic_support", "")
    replication_scope = evidence_semantics.get("replication_scope", "")
    claim_status = evidence_semantics.get("claim_status", "")
    pre_registrations = _load_proposition_pre_registrations(provenance, uri)
    pre_registration_count = len(pre_registrations)
    interaction_terms = _load_proposition_interaction_terms(provenance, uri)
    interaction_count = len(interaction_terms)
    interaction_modifiers = [f"{term['modifier']}({term['effect']})" for term in interaction_terms]
    bridge_hypotheses = _load_proposition_bridge_hypotheses(provenance, uri)
    bridge_count = len(bridge_hypotheses)
    has_explicit_semantics = any((statistical_support, mechanistic_support, replication_scope, claim_status))

    status_obj = next(provenance.objects(uri, SCI_NS.epistemicStatus), None)
    status = str(status_obj) if status_obj else ""
    conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
    confidence: float | None = None
    if conf_obj is not None:
        try:
            confidence = float(str(conf_obj))
        except ValueError:
            pass

    signals: list[str] = []
    risk_score = 0.0
    total_evidence = support_count + dispute_count
    if contested:
        signals.append("contested")
        risk_score += 3.0
    if support_count > 0 and source_count <= 1:
        signals.append("single_source")
        risk_score += 2.0
    if total_evidence > 0 and not has_empirical_data:
        signals.append("no_empirical_data")
        risk_score += 1.5
    if total_evidence == 0:
        signals.append("no_evidence")
        risk_score += 1.0
    if confidence is not None and confidence < 0.5:
        signals.append("low_confidence")
        risk_score += 1.0 + (0.5 - confidence)
    if _load_proposition_falsifications(knowledge, uri):
        signals.append("falsified")
        risk_score += 3.0
    if claim_status:
        signals.append(f"claim_status:{claim_status}")
        if claim_status in {"null", "weakened"}:
            risk_score += 1.0
        elif claim_status in {"retired", "falsified"}:
            risk_score += 2.0
    if pre_registration_count > 0:
        signals.append("pre_registered")
    if interaction_count > 0:
        signals.append("effect_modified")
    if bridge_count > 0:
        signals.append("cross_hypothesis_bridge")
    if status:
        signals.append(f"status:{status}")
        risk_score += 0.5

    if (
        total_evidence == 0
        and confidence is None
        and not status
        and not has_explicit_semantics
        and pre_registration_count == 0
        and interaction_count == 0
        and bridge_count == 0
    ):
        return None

    text_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
    text = str(text_obj) if text_obj else _short_name(str(uri))
    label_obj = next(knowledge.objects(uri, SKOS.prefLabel), None)
    label = str(label_obj) if label_obj else text

    return {
        "uri": uri,
        "claim": str(uri),
        "label": label,
        "text": text,
        "belief_state": belief_state,
        "contested": contested,
        "belief_display": belief_display,
        "support_count": support_count,
        "dispute_count": dispute_count,
        "source_count": source_count,
        "evidence_types": evidence_types,
        "has_empirical_data": has_empirical_data,
        "statistical_support": statistical_support,
        "mechanistic_support": mechanistic_support,
        "replication_scope": replication_scope,
        "claim_status": claim_status,
        "pre_registration_count": pre_registration_count,
        "pre_registrations": pre_registrations,
        "interaction_count": interaction_count,
        "interaction_modifiers": interaction_modifiers,
        "bridge_count": bridge_count,
        "bridge_hypotheses": bridge_hypotheses,
        "signals": signals,
        "risk_score": risk_score,
    }


def _format_claim_summary_row(summary: ClaimSummaryData) -> dict[str, str]:
    evidence_types = summary["evidence_types"]
    signals = summary["signals"]
    return {
        "claim": str(summary["claim"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "belief_state": str(summary["belief_state"]),
        "contested": "yes" if bool(summary["contested"]) else "no",
        "belief_display": str(summary["belief_display"]),
        "support_count": str(summary["support_count"]),
        "dispute_count": str(summary["dispute_count"]),
        "source_count": str(summary["source_count"]),
        "evidence_types": "; ".join(evidence_types) if evidence_types else "-",
        "has_empirical_data": "yes" if bool(summary["has_empirical_data"]) else "no",
        "statistical_support": str(summary["statistical_support"]) or "-",
        "mechanistic_support": str(summary["mechanistic_support"]) or "-",
        "replication_scope": str(summary["replication_scope"]) or "-",
        "claim_status": str(summary["claim_status"]) or "-",
        "pre_registration_count": str(summary["pre_registration_count"]),
        "pre_registrations": "; ".join(summary["pre_registrations"]) if summary["pre_registrations"] else "-",
        "interaction_count": str(summary["interaction_count"]),
        "interaction_modifiers": "; ".join(summary["interaction_modifiers"])
        if summary["interaction_modifiers"]
        else "-",
        "bridge_count": str(summary["bridge_count"]),
        "bridge_hypotheses": "; ".join(summary["bridge_hypotheses"]) if summary["bridge_hypotheses"] else "-",
        "signals": "; ".join(signals) if signals else "-",
        "risk_score": f"{summary['risk_score']:.2f}",
    }


def _claim_summaries(knowledge, provenance, *, include_hypotheses: bool) -> list[ClaimSummaryData]:
    rows: list[ClaimSummaryData] = []
    for uri in _summary_targets(knowledge, include_hypotheses=include_hypotheses):
        summary = _claim_summary_data(knowledge, provenance, uri)
        if summary is not None:
            rows.append(summary)
    return rows


def query_dashboard_summary(
    graph_path: Path,
    top: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    rows = [
        _format_claim_summary_row(summary)
        for summary in _claim_summaries(knowledge, provenance, include_hypotheses=True)
    ]
    rows.sort(key=lambda row: (-float(row["risk_score"]), row["text"]))
    return rows[:top]


def _hypotheses_for_claim(knowledge, claim_uri: URIRef) -> set[URIRef]:
    hypotheses: set[URIRef] = set()

    for _, _, obj in knowledge.triples((claim_uri, CITO_NS.discusses, None)):
        if isinstance(obj, URIRef) and (obj, RDF.type, SCI_NS.Hypothesis) in knowledge:
            hypotheses.add(obj)

    return hypotheses


def _claim_summary_adjacency(knowledge, summary_uris: set[URIRef]) -> dict[URIRef, set[URIRef]]:
    adjacency: dict[URIRef, set[URIRef]] = {uri: set() for uri in summary_uris}
    link_predicates = {CITO_NS.supports, CITO_NS.disputes, CITO_NS.discusses}

    def connect(left: URIRef, right: URIRef) -> None:
        if left == right:
            return
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)

    for subj, predicate, obj in knowledge:
        if predicate not in link_predicates:
            continue
        if isinstance(subj, URIRef) and isinstance(obj, URIRef) and subj in summary_uris and obj in summary_uris:
            connect(subj, obj)

    claims_by_hypothesis: dict[URIRef, set[URIRef]] = {}
    for claim_uri in summary_uris:
        for hypothesis_uri in _hypotheses_for_claim(knowledge, claim_uri):
            claims_by_hypothesis.setdefault(hypothesis_uri, set()).add(claim_uri)

    for claim_group in claims_by_hypothesis.values():
        for left, right in combinations(sorted(claim_group, key=str), 2):
            connect(left, right)

    return adjacency


def _neighborhood_summary_data_rows(knowledge, provenance, *, hops: int) -> list[NeighborhoodSummaryData]:
    summary_rows = _claim_summaries(knowledge, provenance, include_hypotheses=False)
    by_uri: dict[URIRef, ClaimSummaryData] = {summary["uri"]: summary for summary in summary_rows}
    adjacency = _claim_summary_adjacency(knowledge, set(by_uri))

    rows: list[NeighborhoodSummaryData] = []
    for center_uri, center_summary in by_uri.items():
        visited: set[URIRef] = {center_uri}
        queue: deque[tuple[URIRef, int]] = deque([(center_uri, 0)])
        while queue:
            node, depth = queue.popleft()
            if depth >= hops:
                continue
            for neighbor in adjacency.get(node, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

        neighborhood = [by_uri[uri] for uri in sorted(visited, key=str)]
        neighbor_claim_count = max(len(neighborhood) - 1, 0)
        avg_risk_score = sum(float(item["risk_score"]) for item in neighborhood) / len(neighborhood)
        contested_count = sum("contested" in list(item["signals"]) for item in neighborhood)
        single_source_count = sum("single_source" in list(item["signals"]) for item in neighborhood)
        no_empirical_count = sum(not bool(item["has_empirical_data"]) for item in neighborhood)
        structural_fragility = "isolated" if neighbor_claim_count == 0 else "connected"
        neighborhood_risk = (
            avg_risk_score + (0.75 * contested_count) + (0.5 * single_source_count) + (0.5 * no_empirical_count)
        )

        rows.append(
            {
                "center_uri": center_uri,
                "label": str(center_summary["label"]),
                "text": str(center_summary["text"]),
                "neighbor_claim_count": neighbor_claim_count,
                "avg_risk_score": avg_risk_score,
                "contested_count": contested_count,
                "single_source_count": single_source_count,
                "no_empirical_count": no_empirical_count,
                "structural_fragility": structural_fragility,
                "neighborhood_risk": neighborhood_risk,
            }
        )

    return rows


def _format_neighborhood_summary_row(summary: NeighborhoodSummaryData) -> dict[str, str]:
    return {
        "center_claim": str(summary["center_uri"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "neighbor_claim_count": str(summary["neighbor_claim_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_count": str(summary["contested_count"]),
        "single_source_count": str(summary["single_source_count"]),
        "no_empirical_count": str(summary["no_empirical_count"]),
        "structural_fragility": str(summary["structural_fragility"]),
        "neighborhood_risk": f"{summary['neighborhood_risk']:.2f}",
    }


def query_neighborhood_summary(
    graph_path: Path,
    top: int,
    hops: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    rows = [
        _format_neighborhood_summary_row(summary)
        for summary in _neighborhood_summary_data_rows(knowledge, provenance, hops=hops)
    ]
    rows.sort(key=lambda row: (-float(row["neighborhood_risk"]), row["text"]))
    return rows[:top]


def _question_claims(knowledge, question_uri: URIRef) -> list[URIRef]:
    claims: set[URIRef] = set()
    for _, _, prop_uri in knowledge.triples((question_uri, SCI_NS.addresses, None)):
        if not isinstance(prop_uri, URIRef):
            continue
        if (prop_uri, RDF.type, SCI_NS.Proposition) in knowledge:
            claims.add(prop_uri)

    for related_uri in knowledge.objects(question_uri, SKOS.related):
        if not isinstance(related_uri, URIRef):
            continue
        if (related_uri, RDF.type, SCI_NS.Hypothesis) not in knowledge:
            continue
        claims.update(_linked_claims_for_hypothesis(knowledge, related_uri))

    return sorted(claims, key=str)


def _inquiry_claims(knowledge, inquiry_graph, inquiry_uri: URIRef) -> tuple[list[URIRef], list[URIRef]]:
    backed_claims: set[URIRef] = set()
    for statement_uri, _, _ in inquiry_graph.triples((None, RDF.type, RDF.Statement)):
        for claim_uri in inquiry_graph.objects(statement_uri, SCI_NS.backedByClaim):
            if isinstance(claim_uri, URIRef) and (claim_uri, RDF.type, SCI_NS.Proposition) in knowledge:
                backed_claims.add(claim_uri)

    targeted_claims: set[URIRef] = set()
    target_uri = next(inquiry_graph.objects(inquiry_uri, SCI_NS.target), None)
    if isinstance(target_uri, URIRef):
        if (target_uri, RDF.type, SCI_NS.Proposition) in knowledge:
            targeted_claims.add(target_uri)
        elif (target_uri, RDF.type, SCI_NS.Hypothesis) in knowledge:
            targeted_claims.update(_linked_claims_for_hypothesis(knowledge, target_uri))
        elif (target_uri, RDF.type, SCI_NS.Question) in knowledge:
            targeted_claims.update(_question_claims(knowledge, target_uri))

    claim_uris = sorted(backed_claims | targeted_claims, key=str)
    return claim_uris, sorted(backed_claims, key=str)


def _rollup_claim_group(
    claim_uris: list[URIRef],
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_by_center: dict[URIRef, NeighborhoodSummaryData],
    *,
    grounding_penalty: float = 0.0,
) -> dict[str, float | int]:
    claim_count = len(claim_uris)
    neighborhood_rows = [neighborhood_by_center[uri] for uri in claim_uris if uri in neighborhood_by_center]
    neighborhood_count = len(neighborhood_rows)

    risk_values: list[float] = []
    contested_claim_count = 0
    single_source_claim_count = 0
    no_empirical_claim_count = 0

    for claim_uri in claim_uris:
        summary = claim_by_uri.get(claim_uri)
        if summary is None:
            risk_values.append(1.0)
            no_empirical_claim_count += 1
            continue

        risk_values.append(float(summary["risk_score"]))
        if "contested" in list(summary["signals"]):
            contested_claim_count += 1
        if "single_source" in list(summary["signals"]):
            single_source_claim_count += 1
        if not bool(summary["has_empirical_data"]):
            no_empirical_claim_count += 1

    avg_risk_score = sum(risk_values) / claim_count if claim_count else 0.0
    avg_neighborhood_risk = (
        sum(float(summary["neighborhood_risk"]) for summary in neighborhood_rows) / neighborhood_count
        if neighborhood_count
        else 0.0
    )
    priority_score = (
        avg_risk_score
        + (0.5 * avg_neighborhood_risk)
        + (0.75 * contested_claim_count)
        + (0.5 * single_source_claim_count)
        + (0.5 * no_empirical_claim_count)
        + grounding_penalty
    )

    return {
        "claim_count": claim_count,
        "neighborhood_count": neighborhood_count,
        "avg_risk_score": avg_risk_score,
        "contested_claim_count": contested_claim_count,
        "single_source_claim_count": single_source_claim_count,
        "no_empirical_claim_count": no_empirical_claim_count,
        "priority_score": priority_score,
    }


def _question_summary_data(
    knowledge,
    question_uri: URIRef,
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_by_center: dict[URIRef, NeighborhoodSummaryData],
) -> QuestionSummaryData:
    question_text_obj = next(knowledge.objects(question_uri, SCHEMA_NS.text), None)
    question_text = str(question_text_obj) if question_text_obj else _short_name(str(question_uri))
    question_label_obj = next(knowledge.objects(question_uri, SKOS.prefLabel), None)
    question_identifier_obj = next(knowledge.objects(question_uri, SCHEMA_NS.identifier), None)
    question_label = (
        str(question_label_obj)
        if question_label_obj
        else str(question_identifier_obj)
        if question_identifier_obj
        else question_text
    )

    metrics = _rollup_claim_group(
        _question_claims(knowledge, question_uri),
        claim_by_uri,
        neighborhood_by_center,
    )
    return {
        "uri": question_uri,
        "question": str(question_uri),
        "label": question_label,
        "text": question_text,
        "claim_count": cast(int, metrics["claim_count"]),
        "neighborhood_count": cast(int, metrics["neighborhood_count"]),
        "avg_risk_score": cast(float, metrics["avg_risk_score"]),
        "contested_claim_count": cast(int, metrics["contested_claim_count"]),
        "single_source_claim_count": cast(int, metrics["single_source_claim_count"]),
        "no_empirical_claim_count": cast(int, metrics["no_empirical_claim_count"]),
        "priority_score": cast(float, metrics["priority_score"]),
    }


def _format_question_summary_row(summary: QuestionSummaryData) -> dict[str, str]:
    return {
        "question": str(summary["question"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "claim_count": str(summary["claim_count"]),
        "neighborhood_count": str(summary["neighborhood_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_claim_count": str(summary["contested_claim_count"]),
        "single_source_claim_count": str(summary["single_source_claim_count"]),
        "no_empirical_claim_count": str(summary["no_empirical_claim_count"]),
        "priority_score": f"{summary['priority_score']:.2f}",
    }


def query_question_summary(
    graph_path: Path,
    top: int | None,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    claim_by_uri = {
        summary["uri"]: summary for summary in _claim_summaries(knowledge, provenance, include_hypotheses=False)
    }
    neighborhood_by_center = {
        summary["center_uri"]: summary for summary in _neighborhood_summary_data_rows(knowledge, provenance, hops=1)
    }

    rows = [
        _format_question_summary_row(
            _question_summary_data(knowledge, question_uri, claim_by_uri, neighborhood_by_center)
        )
        for question_uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Question))
        if isinstance(question_uri, URIRef)
    ]
    rows.sort(key=lambda row: (-float(row["priority_score"]), row["text"]))
    return rows if top is None else rows[:top]


def _inquiry_summary_data(
    knowledge,
    inquiry_graph,
    inquiry_uri: URIRef,
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_by_center: dict[URIRef, NeighborhoodSummaryData],
) -> InquirySummaryData:
    claim_uris, backed_claims = _inquiry_claims(knowledge, inquiry_graph, inquiry_uri)
    metrics = _rollup_claim_group(
        claim_uris,
        claim_by_uri,
        neighborhood_by_center,
        grounding_penalty=0.5 if not backed_claims else 0.0,
    )

    label_obj = next(inquiry_graph.objects(inquiry_uri, SKOS.prefLabel), None)
    label = str(label_obj) if label_obj else _short_name(str(inquiry_uri))
    text_obj = next(inquiry_graph.objects(inquiry_uri, SKOS.note), None)
    text = str(text_obj) if text_obj else label
    status_obj = next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryStatus), None)
    inquiry_type_obj = next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), None)

    return {
        "uri": inquiry_uri,
        "inquiry": str(inquiry_uri),
        "label": label,
        "text": text,
        "inquiry_type": str(inquiry_type_obj) if inquiry_type_obj else "general",
        "status": str(status_obj) if status_obj else "",
        "claim_count": cast(int, metrics["claim_count"]),
        "backed_claim_count": len(backed_claims),
        "avg_risk_score": cast(float, metrics["avg_risk_score"]),
        "contested_claim_count": cast(int, metrics["contested_claim_count"]),
        "single_source_claim_count": cast(int, metrics["single_source_claim_count"]),
        "no_empirical_claim_count": cast(int, metrics["no_empirical_claim_count"]),
        "priority_score": cast(float, metrics["priority_score"]),
    }


def _format_inquiry_summary_row(summary: InquirySummaryData) -> dict[str, str]:
    return {
        "inquiry": str(summary["inquiry"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "inquiry_type": str(summary["inquiry_type"]),
        "status": str(summary["status"]) or "-",
        "claim_count": str(summary["claim_count"]),
        "backed_claim_count": str(summary["backed_claim_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_claim_count": str(summary["contested_claim_count"]),
        "single_source_claim_count": str(summary["single_source_claim_count"]),
        "no_empirical_claim_count": str(summary["no_empirical_claim_count"]),
        "priority_score": f"{summary['priority_score']:.2f}",
    }


def query_inquiry_summary(
    graph_path: Path,
    top: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    claim_by_uri = {
        summary["uri"]: summary for summary in _claim_summaries(knowledge, provenance, include_hypotheses=False)
    }
    neighborhood_by_center = {
        summary["center_uri"]: summary for summary in _neighborhood_summary_data_rows(knowledge, provenance, hops=1)
    }

    inquiry_prefix = str(PROJECT_NS) + "inquiry/"
    rows: list[dict[str, str]] = []
    for inquiry_graph in dataset.graphs():
        graph_id = str(inquiry_graph.identifier)
        if not graph_id.startswith(inquiry_prefix):
            continue
        inquiry_uri = URIRef(graph_id)
        if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
            continue

        rows.append(
            _format_inquiry_summary_row(
                _inquiry_summary_data(knowledge, inquiry_graph, inquiry_uri, claim_by_uri, neighborhood_by_center)
            )
        )

    rows.sort(key=lambda row: (-float(row["priority_score"]), row["label"]))
    return rows[:top]


def _project_summary_data(
    project_root: Path,
    profile: str,
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_rows: list[NeighborhoodSummaryData],
    question_rows: list[QuestionSummaryData],
    inquiry_rows: list[InquirySummaryData],
) -> ProjectSummaryData:
    high_risk_neighborhood_count = sum(float(row["neighborhood_risk"]) >= 3.0 for row in neighborhood_rows)
    metrics = _rollup_claim_group(
        sorted(claim_by_uri, key=str),
        claim_by_uri,
        {row["center_uri"]: row for row in neighborhood_rows},
    )

    return {
        "project": str(project_root),
        "profile": profile,
        "question_count": len(question_rows),
        "inquiry_count": len(inquiry_rows),
        "claim_count": cast(int, metrics["claim_count"]),
        "high_risk_neighborhood_count": high_risk_neighborhood_count,
        "avg_risk_score": cast(float, metrics["avg_risk_score"]),
        "contested_claim_count": cast(int, metrics["contested_claim_count"]),
        "single_source_claim_count": cast(int, metrics["single_source_claim_count"]),
        "no_empirical_claim_count": cast(int, metrics["no_empirical_claim_count"]),
        "priority_score": cast(float, metrics["priority_score"]) + (0.5 * high_risk_neighborhood_count),
    }


def _format_project_summary_row(summary: ProjectSummaryData) -> dict[str, str]:
    return {
        "project": summary["project"],
        "profile": summary["profile"],
        "question_count": str(summary["question_count"]),
        "inquiry_count": str(summary["inquiry_count"]),
        "claim_count": str(summary["claim_count"]),
        "high_risk_neighborhood_count": str(summary["high_risk_neighborhood_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_claim_count": str(summary["contested_claim_count"]),
        "single_source_claim_count": str(summary["single_source_claim_count"]),
        "no_empirical_claim_count": str(summary["no_empirical_claim_count"]),
        "priority_score": f"{summary['priority_score']:.2f}",
    }


def query_project_summary(graph_path: Path) -> list[dict[str, str]]:
    from science_tool.paths import resolve_paths

    project_root = _project_root_from_graph_path(graph_path).resolve()
    profile = resolve_paths(project_root).profile
    if profile != "research":
        raise ValueError("project-summary is currently defined only for research projects")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    claim_rows = _claim_summaries(knowledge, provenance, include_hypotheses=False)
    claim_by_uri = {summary["uri"]: summary for summary in claim_rows}
    neighborhood_rows = _neighborhood_summary_data_rows(knowledge, provenance, hops=1)
    neighborhood_by_center = {summary["center_uri"]: summary for summary in neighborhood_rows}
    question_rows = [
        _question_summary_data(knowledge, question_uri, claim_by_uri, neighborhood_by_center)
        for question_uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Question))
        if isinstance(question_uri, URIRef)
    ]

    inquiry_prefix = str(PROJECT_NS) + "inquiry/"
    inquiry_rows: list[InquirySummaryData] = []
    for inquiry_graph in dataset.graphs():
        graph_id = str(inquiry_graph.identifier)
        if not graph_id.startswith(inquiry_prefix):
            continue
        inquiry_uri = URIRef(graph_id)
        if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
            continue
        inquiry_rows.append(
            _inquiry_summary_data(knowledge, inquiry_graph, inquiry_uri, claim_by_uri, neighborhood_by_center)
        )

    return [
        _format_project_summary_row(
            _project_summary_data(project_root, profile, claim_by_uri, neighborhood_rows, question_rows, inquiry_rows)
        )
    ]


def query_coverage(
    graph_path: Path,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    causal = dataset.graph(_graph_uri("graph/causal"))
    datasets_graph = dataset.graph(_graph_uri("graph/datasets"))

    entity_uris: set[URIRef] = set()
    for uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Concept)):
        if isinstance(uri, URIRef):
            entity_uris.add(uri)
    for uri, _, _ in causal.triples((None, RDF.type, SCIC_NS.Variable)):
        if isinstance(uri, URIRef):
            entity_uris.add(uri)

    rows: list[dict[str, str]] = []
    for uri in sorted(entity_uris, key=str):
        label_obj = next(knowledge.objects(uri, SKOS.prefLabel), None)
        label = str(label_obj) if label_obj else _short_name(str(uri))

        measured = any(datasets_graph.triples((uri, SCI_NS.measuredBy, None)))

        observed_lit = next(causal.objects(uri, SCIC_NS.isObserved), None)
        if observed_lit is not None:
            observed = str(observed_lit).lower() in ("true", "1")
            observed_str = "yes" if observed else "no"
        else:
            observed_str = "-"

        rows.append(
            {
                "entity": str(uri),
                "label": label,
                "measured": "yes" if measured else "no",
                "observed": observed_str,
            }
        )
    return rows[:limit]


def query_gaps(
    graph_path: Path,
    center: str,
    hops: int,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    center_uri = _resolve_center_entity(center)

    # BFS to find neighborhood entities
    adjacency: dict[URIRef, set[URIRef]] = {}
    for subj, _, obj in knowledge:
        if not isinstance(subj, URIRef) or not isinstance(obj, URIRef):
            continue
        adjacency.setdefault(subj, set()).add(obj)
        adjacency.setdefault(obj, set()).add(subj)

    visited: set[URIRef] = {center_uri}
    queue: deque[tuple[URIRef, int]] = deque([(center_uri, 0)])
    while queue:
        node, depth = queue.popleft()
        if depth >= hops:
            continue
        for neighbor in adjacency.get(node, set()):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, depth + 1))

    rows: list[dict[str, str]] = []
    for uri in sorted(visited, key=str):
        issues: list[str] = []

        # Low connectivity
        degree = len(adjacency.get(uri, set()))
        if degree <= 1:
            issues.append(f"structural_fragility(low_connectivity,degree={degree})")

        # Proposition and hypothesis evidence/provenance fragility
        if (uri, RDF.type, SCI_NS.Proposition) in knowledge or (uri, RDF.type, SCI_NS.Hypothesis) in knowledge:
            if not any(provenance.triples((uri, PROV.wasDerivedFrom, None))):
                issues.append("missing_provenance")

            evidence_summary = _collect_evidence_signals(knowledge, provenance, uri)
            support_count = int(evidence_summary["support_count"])
            dispute_count = int(evidence_summary["dispute_count"])
            total_evidence = support_count + dispute_count
            source_count = int(evidence_summary["source_count"])
            if support_count > 0 and dispute_count > 0:
                issues.append("evidential_fragility(contested)")
            if total_evidence > 0 and source_count <= 1:
                issues.append("evidential_fragility(single_source)")

        # Low confidence
        conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
        if conf_obj is not None:
            try:
                conf = float(str(conf_obj))
                if conf < 0.5:
                    issues.append(f"authored_low_confidence({conf:.2f})")
            except ValueError:
                pass

        if issues:
            label_obj = next(knowledge.objects(uri, SKOS.prefLabel), None)
            if label_obj is None:
                label_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
            label = str(label_obj) if label_obj else _short_name(str(uri))

            rows.append(
                {
                    "entity": str(uri),
                    "label": label,
                    "issues": "; ".join(issues),
                }
            )
    return rows[:limit]


def query_uncertainty(
    graph_path: Path,
    top: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    uncertain_statuses = {"disputed", "hypothesized"}

    rows: list[dict[str, str]] = []
    # Collect all entities with epistemic metadata
    seen: set[URIRef] = set()
    for entity_type in (SCI_NS.Proposition, SCI_NS.Hypothesis):
        for uri, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            if not isinstance(uri, URIRef) or uri in seen:
                continue
            seen.add(uri)

            status_obj = next(provenance.objects(uri, SCI_NS.epistemicStatus), None)
            status = str(status_obj) if status_obj else ""

            conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
            confidence: float | None = None
            if conf_obj is not None:
                try:
                    confidence = float(str(conf_obj))
                except ValueError:
                    pass

            evidence_summary = _collect_evidence_signals(knowledge, provenance, uri)
            support_count = int(evidence_summary["support_count"])
            dispute_count = int(evidence_summary["dispute_count"])
            source_count = int(evidence_summary["source_count"])
            signals: list[str] = []
            risk_score = 0.0

            if support_count > 0 and dispute_count > 0:
                signals.append("contested")
                risk_score += 3.0

            total_evidence = support_count + dispute_count
            if total_evidence > 0 and source_count <= 1:
                signals.append("single_source")
                risk_score += 2.0

            is_uncertain_status = status.lower() in uncertain_statuses
            if is_uncertain_status:
                signals.append(f"status:{status.lower()}")
                risk_score += 1.5

            is_low_confidence = confidence is not None and confidence < 0.5
            if is_low_confidence and confidence is not None:
                signals.append("low_confidence")
                risk_score += 1.0 + (0.5 - confidence)

            if not signals:
                continue

            text_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
            text = str(text_obj) if text_obj else _short_name(str(uri))

            rows.append(
                {
                    "entity": str(uri),
                    "text": text,
                    "status": status or "-",
                    "confidence": f"{confidence:.2f}" if confidence is not None else "-",
                    "signals": "; ".join(signals),
                    "support_count": str(support_count),
                    "dispute_count": str(dispute_count),
                    "_sort": str(risk_score),
                }
            )

    rows.sort(key=lambda r: float(r["_sort"]), reverse=True)
    for row in rows:
        del row["_sort"]
    return rows[:top]


def build_graph_dot(
    graph_path: Path,
    graph_layer: str,
    center: str | None,
    hops: int,
    limit: int,
) -> str:
    if center:
        rows = query_neighborhood(
            graph_path=graph_path,
            center=center,
            hops=hops,
            graph_layer=graph_layer,
            limit=limit,
        )
    else:
        dataset = _load_dataset(graph_path)
        layer = dataset.graph(_graph_uri(graph_layer))
        rows = []
        for subj, pred, obj in layer:
            if isinstance(subj, URIRef) and isinstance(obj, URIRef):
                rows.append(
                    {
                        "subject": str(subj),
                        "predicate": str(pred),
                        "object": str(obj),
                    }
                )
            if len(rows) >= limit:
                break

    lines = ["digraph G {", "  rankdir=LR;"]
    nodes: set[str] = set()
    for row in rows:
        subj = row["subject"]
        obj = row["object"]
        pred = row["predicate"]
        nodes.add(subj)
        nodes.add(obj)
        lines.append(f'  "{_short_name(subj)}" -> "{_short_name(obj)}" [label="{_short_name(pred)}"];')
    for node in sorted(nodes):
        lines.append(f'  "{_short_name(node)}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


