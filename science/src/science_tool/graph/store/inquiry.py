from __future__ import annotations

import importlib
from collections import deque
from pathlib import Path
from typing import Any

from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import PROV, RDF, SKOS

from .constants import DCTERMS_NS, PROJECT_NS, SCI_NS, SCIC_NS
from .dataset import _load_dataset, _save_dataset
from .graphutil import _has_cycle
from .identity import _edge_claims, _graph_uri, _resolve_term, _slug, shorten_uri
from .types import InquiryEdge, InquiryInfo


def _inquiry_property(dataset: Dataset, subject: URIRef, *predicates: URIRef) -> str:
    """First object for `subject` under the first matching predicate, across all
    graphs, as a string. Predicates are tried in order so callers can express a
    fallback (e.g. interactive `sci:inquiryStatus` then materialized
    `sci:projectStatus`)."""
    for predicate in predicates:
        for graph in dataset.graphs():
            obj = next(graph.objects(subject, predicate), None)
            if obj is not None:
                return str(obj)
    return ""


def _discover_inquiries(dataset: Dataset) -> dict[str, tuple[URIRef, Graph]]:
    """Map slug -> (inquiry_uri, home_graph) for every `sci:Inquiry` in the dataset.

    Two layouts coexist. Interactive `inquiry init`/`add-edge` write a dedicated
    per-inquiry named graph whose identifier equals the inquiry URI. The canonical
    `materialize_graph` build instead emits each inquiry as an entity inside the
    shared `graph/knowledge` layer. Both are discovered here by scanning every
    graph for the type triple; when both exist for one slug, the dedicated graph
    wins because it also carries the boundary/edge subgraph.
    """
    inquiry_prefix = str(PROJECT_NS) + "inquiry/"
    found: dict[str, tuple[URIRef, Graph]] = {}
    for graph in dataset.graphs():
        for subject in graph.subjects(RDF.type, SCI_NS.Inquiry):
            if not isinstance(subject, URIRef):
                continue
            uri_str = str(subject)
            if not uri_str.startswith(inquiry_prefix):
                continue
            slug = uri_str[len(inquiry_prefix) :]
            if slug not in found or str(graph.identifier) == uri_str:
                found[slug] = (subject, graph)
    return found


def list_inquiries(graph_path: Path) -> list[dict[str, str]]:
    """List all inquiries in the dataset, returning a list of summary dicts."""
    dataset = _load_dataset(graph_path)
    results: list[dict[str, str]] = []
    for slug, (inquiry_uri, _home) in _discover_inquiries(dataset).items():
        results.append(
            {
                "slug": slug,
                "label": _inquiry_property(dataset, inquiry_uri, SKOS.prefLabel),
                "inquiry_type": _inquiry_property(dataset, inquiry_uri, SCI_NS.inquiryType) or "general",
                "status": _inquiry_property(dataset, inquiry_uri, SCI_NS.inquiryStatus, SCI_NS.projectStatus),
                "target": _inquiry_property(dataset, inquiry_uri, SCI_NS.target),
                "created": _inquiry_property(dataset, inquiry_uri, DCTERMS_NS.created),
            }
        )
    return results


def get_inquiry(graph_path: Path, slug: str) -> InquiryInfo:
    """Get detailed information about a specific inquiry, including boundaries and edges."""
    dataset = _load_dataset(graph_path)
    inquiries = _discover_inquiries(dataset)

    requested = slug
    for prefix in ("inquiry/", "inquiry:"):
        if requested.startswith(prefix):
            requested = requested[len(prefix) :]

    match = inquiries.get(requested)
    if match is None:
        # Tolerate slug-normalization drift between stored hyphenated slugs and
        # the legacy underscore form `_slug` produces.
        normalized = _slug(requested)
        match = next((value for cand, value in inquiries.items() if _slug(cand) == normalized), None)
    if match is None:
        raise ValueError(f"Inquiry 'inquiry/{requested}' does not exist")

    inquiry_uri, home_graph = match
    actual_slug = str(inquiry_uri)[len(str(PROJECT_NS) + "inquiry/") :]

    label = _inquiry_property(dataset, inquiry_uri, SKOS.prefLabel)
    status = _inquiry_property(dataset, inquiry_uri, SCI_NS.inquiryStatus, SCI_NS.projectStatus)
    inquiry_type = _inquiry_property(dataset, inquiry_uri, SCI_NS.inquiryType) or "general"
    target = _inquiry_property(dataset, inquiry_uri, SCI_NS.target)
    created = _inquiry_property(dataset, inquiry_uri, DCTERMS_NS.created)
    description = _inquiry_property(dataset, inquiry_uri, SKOS.note)

    treatment = next((o for g in dataset.graphs() for o in g.objects(inquiry_uri, SCI_NS.treatment)), None)
    outcome = next((o for g in dataset.graphs() for o in g.objects(inquiry_uri, SCI_NS.outcome)), None)
    related = sorted({str(o) for g in dataset.graphs() for o in g.objects(inquiry_uri, SKOS.related)})

    # The boundary/edge subgraph only exists in a dedicated per-inquiry named
    # graph. A materialized inquiry's home graph is the shared `graph/knowledge`
    # layer, so scanning it for "edges" would pull in every entity's triples;
    # treat that case as an empty subgraph.
    boundary_in: list[str] = []
    boundary_out: list[str] = []
    edges: list[InquiryEdge] = []
    if str(home_graph.identifier) == str(inquiry_uri):
        for s, _p, o in home_graph.triples((None, SCI_NS.boundaryRole, None)):
            if o == SCI_NS.BoundaryIn:
                boundary_in.append(str(s))
            elif o == SCI_NS.BoundaryOut:
                boundary_out.append(str(s))

        metadata_predicates = {
            RDF.type,
            RDF.subject,
            RDF.predicate,
            RDF.object,
            SKOS.prefLabel,
            SKOS.note,
            SKOS.related,
            SCI_NS.inquiryStatus,
            SCI_NS.inquiryType,
            SCI_NS.projectStatus,
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
        for s, p, o in home_graph:
            if p not in metadata_predicates:
                edge_info: InquiryEdge = {"subject": str(s), "predicate": str(p), "object": str(o)}
                if isinstance(s, URIRef) and isinstance(p, URIRef) and isinstance(o, URIRef):
                    claim_uris = _edge_claims(home_graph, s, p, o)
                    if claim_uris:
                        edge_info["claims"] = [str(uri) for uri in claim_uris]
                edges.append(edge_info)

    return {
        "slug": actual_slug,
        "label": label,
        "status": status,
        "inquiry_type": inquiry_type,
        "target": target,
        "created": created,
        "description": description,
        "treatment": str(treatment) if treatment else None,
        "outcome": str(outcome) if outcome else None,
        "related": related,
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
