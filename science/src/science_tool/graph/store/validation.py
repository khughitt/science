from __future__ import annotations

from pathlib import Path

import click
from rdflib import Dataset
from rdflib.namespace import PROV, RDF, SKOS

from science_tool.graph.io import (
    build_input_manifest as _build_input_manifest,
    read_revision_manifest as _read_revision_manifest,
)

from .constants import PREDICATE_REGISTRY, SCHEMA_NS, SCI_NS, SCIC_NS
from .dataset import _load_dataset
from .graphutil import _has_cycle
from .identity import _graph_uri


def query_predicates() -> list[dict[str, str]]:
    return list(PREDICATE_REGISTRY)


def validate_graph(graph_path: Path) -> tuple[list[dict[str, str]], bool]:
    try:
        dataset = _load_dataset(graph_path)
    except Exception as exc:  # noqa: BLE001
        return _parse_failure_rows(exc), True

    return validate_graph_dataset(dataset)


def validate_graph_dataset(dataset: Dataset) -> tuple[list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []
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


def _parse_failure_rows(exc: Exception) -> list[dict[str, str]]:
    return [
        {
            "check": "parseable_trig",
            "status": "fail",
            "details": f"failed to parse graph.trig: {exc}",
        }
    ]


def diff_graph_inputs(graph_path: Path, mode: str) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    return diff_graph_inputs_dataset(dataset, graph_path=graph_path, mode=mode)


def diff_graph_inputs_dataset(dataset: Dataset, *, graph_path: Path, mode: str) -> list[dict[str, str]]:
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
