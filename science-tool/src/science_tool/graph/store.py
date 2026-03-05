from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import click
from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD

DEFAULT_GRAPH_PATH = Path("knowledge/graph.trig")
PROJECT_NS = Namespace("http://example.org/project/")
SCI_NS = Namespace("http://example.org/science/vocab/")
SCIC_NS = Namespace("http://example.org/science/vocab/causal/")
SCHEMA_NS = Namespace("https://schema.org/")
BIOLINK_NS = Namespace("https://w3id.org/biolink/vocab/")
REVISION_URI = URIRef(PROJECT_NS["graph_revision"])

GRAPH_LAYERS: tuple[str, ...] = (
    "graph/knowledge",
    "graph/causal",
    "graph/provenance",
    "graph/datasets",
)

CURIE_PREFIXES: dict[str, Namespace] = {
    "sci": SCI_NS,
    "scic": SCIC_NS,
    "schema": SCHEMA_NS,
    "prov": Namespace(str(PROV)),
    "skos": Namespace(str(SKOS)),
    "rdf": Namespace(str(RDF)),
    "biolink": BIOLINK_NS,
}
PROJECT_ENTITY_PREFIXES: set[str] = {
    "paper",
    "concept",
    "claim",
    "hypothesis",
    "dataset",
    "question",
}

INITIAL_GRAPH_TEMPLATE = """@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix schema: <https://schema.org/> .
@prefix sci:    <http://example.org/science/vocab/> .
@prefix scic:   <http://example.org/science/vocab/causal/> .
@prefix :       <http://example.org/project/> .

<http://example.org/project/graph/knowledge> {
}

<http://example.org/project/graph/causal> {
}

<http://example.org/project/graph/provenance> {
}

<http://example.org/project/graph/datasets> {
}
"""


def init_graph_file(graph_path: Path) -> None:
    if graph_path.exists():
        raise click.ClickException(f"Graph file already exists: {graph_path}")

    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")


def read_graph_stats(graph_path: Path) -> dict[str, int]:
    dataset = _load_dataset(graph_path)

    stats: dict[str, int] = {}
    for layer in GRAPH_LAYERS:
        stats[layer] = len(dataset.graph(_graph_uri(layer)))

    return stats


def add_concept(graph_path: Path, label: str, concept_type: str | None, ontology_id: str | None) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    concept_uri = URIRef(PROJECT_NS[f"concept/{_slug(label)}"])
    knowledge.add((concept_uri, RDF.type, SCI_NS.Concept))
    knowledge.add((concept_uri, SKOS.prefLabel, Literal(label)))

    if concept_type:
        knowledge.add((concept_uri, RDF.type, _resolve_term(concept_type)))
    if ontology_id:
        knowledge.add((concept_uri, SCHEMA_NS.identifier, Literal(ontology_id)))

    _save_dataset(dataset, graph_path)
    return concept_uri


def add_paper(graph_path: Path, doi: str) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    doi_slug = _slug(doi)
    paper_uri = URIRef(PROJECT_NS[f"paper/doi_{doi_slug}"])
    knowledge.add((paper_uri, RDF.type, SCI_NS.Paper))
    knowledge.add((paper_uri, SCHEMA_NS.identifier, Literal(doi)))

    _save_dataset(dataset, graph_path)
    return paper_uri


def add_claim(
    graph_path: Path,
    text: str,
    source: str,
    confidence: float | None,
    claim_id: str | None = None,
) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    if claim_id is not None:
        token = _slug(claim_id)
        if not token:
            raise click.ClickException("Claim ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{source}|{text}".encode("utf-8")).hexdigest()[:12]

    claim_uri = URIRef(PROJECT_NS[f"claim/{token}"])
    knowledge.add((claim_uri, RDF.type, SCI_NS.Claim))
    knowledge.add((claim_uri, SCHEMA_NS.text, Literal(text)))

    provenance.add((claim_uri, PROV.wasDerivedFrom, _resolve_term(source)))
    if confidence is not None:
        provenance.add((claim_uri, SCI_NS.confidence, Literal(confidence, datatype=XSD.decimal)))

    _save_dataset(dataset, graph_path)
    return claim_uri


def add_hypothesis(graph_path: Path, hypothesis_id: str, text: str, source: str) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    hypothesis_uri = URIRef(PROJECT_NS[f"hypothesis/{hypothesis_id.lower()}"])
    knowledge.add((hypothesis_uri, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((hypothesis_uri, SCHEMA_NS.identifier, Literal(hypothesis_id)))
    knowledge.add((hypothesis_uri, SCHEMA_NS.text, Literal(text)))

    provenance.add((hypothesis_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    _save_dataset(dataset, graph_path)
    return hypothesis_uri


def add_edge(graph_path: Path, subject: str, predicate: str, obj: str, graph_layer: str) -> None:
    if graph_layer not in GRAPH_LAYERS:
        raise click.ClickException(f"Unsupported graph layer: {graph_layer}")

    dataset = _load_dataset(graph_path)
    layer = dataset.graph(_graph_uri(graph_layer))
    layer.add((_resolve_term(subject), _resolve_term(predicate), _resolve_term(obj)))

    _save_dataset(dataset, graph_path)


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
    for entity_type in (SCI_NS.Claim, SCI_NS.Hypothesis):
        for entity, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            if not any(provenance.triples((entity, PROV.wasDerivedFrom, None))):
                provenance_failures += 1

    if provenance_failures:
        rows.append(
            {
                "check": "provenance_completeness",
                "status": "fail",
                "details": f"{provenance_failures} claim/hypothesis entities missing prov:wasDerivedFrom",
            }
        )
    else:
        rows.append(
            {
                "check": "provenance_completeness",
                "status": "pass",
                "details": "all claims and hypotheses have provenance links",
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
    for claim_uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Claim)):
        text_obj = next(knowledge.objects(claim_uri, SCHEMA_NS.text), None)
        if text_obj is None:
            continue
        text = str(text_obj)
        if not any(token in text.lower() for token in tokens):
            continue

        sources = sorted({str(src) for src in provenance.objects(claim_uri, PROV.wasDerivedFrom)})
        rows.append(
            {
                "claim": str(claim_uri),
                "text": text,
                "sources": "; ".join(sources),
            }
        )
    return rows[:limit]


def query_evidence(
    graph_path: Path,
    hypothesis_id: str,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    hyp_uri = _resolve_center_entity(hypothesis_id)

    rows: list[dict[str, str]] = []
    for ev_uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Evidence)):
        relation: str | None = None
        if (ev_uri, SCI_NS.supports, hyp_uri) in knowledge:
            relation = "supports"
        elif (ev_uri, SCI_NS.refutes, hyp_uri) in knowledge:
            relation = "refutes"
        else:
            continue

        text_obj = next(knowledge.objects(ev_uri, SCHEMA_NS.text), None)
        text = str(text_obj) if text_obj else ""

        sources = sorted({str(src) for src in provenance.objects(ev_uri, PROV.wasDerivedFrom)})
        rows.append(
            {
                "evidence": str(ev_uri),
                "relation": relation,
                "text": text,
                "sources": "; ".join(sources),
            }
        )
    return rows[:limit]


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
            issues.append(f"low_connectivity(degree={degree})")

        # Claims missing provenance
        if (uri, RDF.type, SCI_NS.Claim) in knowledge:
            if not any(provenance.triples((uri, PROV.wasDerivedFrom, None))):
                issues.append("missing_provenance")

        # Low confidence
        conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
        if conf_obj is not None:
            try:
                conf = float(str(conf_obj))
                if conf < 0.5:
                    issues.append(f"low_confidence({conf:.2f})")
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
    for entity_type in (SCI_NS.Claim, SCI_NS.Hypothesis):
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

            is_uncertain_status = status.lower() in uncertain_statuses
            is_low_confidence = confidence is not None and confidence < 0.5

            if not is_uncertain_status and not is_low_confidence:
                continue

            text_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
            text = str(text_obj) if text_obj else _short_name(str(uri))

            # Sort key: lower confidence = more uncertain; uncertain status adds penalty
            sort_score = confidence if confidence is not None else 0.5
            if is_uncertain_status:
                sort_score -= 1.0

            rows.append(
                {
                    "entity": str(uri),
                    "text": text,
                    "status": status or "-",
                    "confidence": f"{confidence:.2f}" if confidence is not None else "-",
                    "_sort": str(sort_score),
                }
            )

    rows.sort(key=lambda r: float(r["_sort"]))
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
        lines.append(
            f'  "{_short_name(subj)}" -> "{_short_name(obj)}" [label="{_short_name(pred)}"];'
        )
    for node in sorted(nodes):
        lines.append(f'  "{_short_name(node)}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _has_cycle(edges: list[tuple[str, str]]) -> bool:
    adjacency: dict[str, list[str]] = {}
    for source, target in edges:
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, [])

    state: dict[str, int] = {}
    # 0 = unvisited, 1 = visiting, 2 = visited

    def visit(node: str) -> bool:
        status = state.get(node, 0)
        if status == 1:
            return True
        if status == 2:
            return False

        state[node] = 1
        for nxt in adjacency.get(node, []):
            if visit(nxt):
                return True
        state[node] = 2
        return False

    for node in adjacency:
        if state.get(node, 0) == 0 and visit(node):
            return True
    return False


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _graph_uri(layer: str) -> URIRef:
    return URIRef(PROJECT_NS[layer])


def _resolve_term(value: str) -> URIRef:
    if value.startswith(("http://", "https://")):
        return URIRef(value)

    if ":" in value:
        prefix, suffix = value.split(":", 1)
        namespace = CURIE_PREFIXES.get(prefix)
        if namespace is not None:
            return URIRef(namespace[suffix])
        if prefix in PROJECT_ENTITY_PREFIXES:
            return URIRef(PROJECT_NS[f"{prefix}/{suffix}"])
        supported_prefixes = sorted([*CURIE_PREFIXES.keys(), *PROJECT_ENTITY_PREFIXES])
        raise click.ClickException(
            f"Unknown CURIE prefix '{prefix}'. Supported prefixes: {', '.join(supported_prefixes)}"
        )

    return URIRef(PROJECT_NS[value])


def _load_dataset(graph_path: Path) -> Dataset:
    if not graph_path.exists():
        raise click.ClickException(f"Graph file not found: {graph_path}")

    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    return dataset


def _save_dataset(dataset: Dataset, graph_path: Path) -> None:
    _upsert_revision_metadata(dataset, graph_path)
    dataset.serialize(destination=str(graph_path), format="trig")


def _upsert_revision_metadata(dataset: Dataset, graph_path: Path) -> None:
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    for triple in list(provenance.triples((REVISION_URI, None, None))):
        provenance.remove(triple)

    manifest = _build_input_manifest(graph_path=graph_path)
    manifest_json = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    revision_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    provenance.add((REVISION_URI, RDF.type, PROV.Entity))
    provenance.add((REVISION_URI, SCHEMA_NS.name, Literal("graph-revision")))
    provenance.add((REVISION_URI, SCHEMA_NS.dateModified, Literal(revision_time, datatype=XSD.dateTime)))
    provenance.add((REVISION_URI, SCHEMA_NS.text, Literal(manifest_json)))

    preview = dataset.serialize(format="trig")
    preview_text = preview.decode("utf-8") if isinstance(preview, bytes) else str(preview)
    graph_hash = hashlib.sha256(preview_text.encode("utf-8")).hexdigest()
    provenance.add((REVISION_URI, SCHEMA_NS.sha256, Literal(graph_hash)))


def _read_revision_manifest(dataset: Dataset) -> dict[str, dict[str, int | str]]:
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    manifest_literal = next(provenance.objects(REVISION_URI, SCHEMA_NS.text), None)
    if manifest_literal is None:
        return {}

    try:
        loaded = json.loads(str(manifest_literal))
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}

    manifest: dict[str, dict[str, int | str]] = {}
    for key, value in loaded.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        sha = value.get("sha256")
        mtime = value.get("mtime_ns")
        if not isinstance(sha, str):
            continue
        if not isinstance(mtime, int):
            continue
        manifest[key] = {"sha256": sha, "mtime_ns": mtime}
    return manifest


def _build_input_manifest(graph_path: Path) -> dict[str, dict[str, int | str]]:
    project_root = _project_root_from_graph_path(graph_path)
    include_dirs = ("doc", "specs", "notes", "papers/summaries", "data", "code")
    include_files = ("RESEARCH_PLAN.md", "science.yaml", "CLAUDE.md", "AGENTS.md")

    files: set[Path] = set()
    for file_name in include_files:
        candidate = project_root / file_name
        if candidate.is_file():
            files.add(candidate)

    for dir_name in include_dirs:
        base = project_root / dir_name
        if not base.is_dir():
            continue
        for candidate in base.rglob("*"):
            if candidate.is_file():
                files.add(candidate)

    manifest: dict[str, dict[str, int | str]] = {}
    for file_path in sorted(files):
        rel_path = file_path.relative_to(project_root).as_posix()
        stat = file_path.stat()
        manifest[rel_path] = {
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": _sha256_file(file_path),
        }
    return manifest


def _project_root_from_graph_path(graph_path: Path) -> Path:
    if graph_path.name == "graph.trig" and graph_path.parent.name == "knowledge":
        return graph_path.parent.parent
    return graph_path.parent


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_center_entity(value: str) -> URIRef:
    if value.startswith(("http://", "https://")) or ":" in value or "/" in value:
        return _resolve_term(value)
    return URIRef(PROJECT_NS[f"concept/{_slug(value)}"])


def _about_tokens(about: str) -> set[str]:
    tokens: set[str] = set()
    lowered = about.lower()
    tokens.add(lowered)
    slug = _slug(about).replace("_", " ")
    if slug:
        tokens.add(slug)

    if "/" in about:
        tail = about.rsplit("/", 1)[-1].lower().replace("_", " ")
        if tail:
            tokens.add(tail)
    if ":" in about:
        suffix = about.split(":", 1)[1].lower().replace("_", " ")
        if suffix:
            tokens.add(suffix)
    return {token for token in tokens if token}


def _short_name(uri: str) -> str:
    if uri.startswith(str(PROJECT_NS)):
        return uri.replace(str(PROJECT_NS), "")
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rsplit("/", 1)[-1]
