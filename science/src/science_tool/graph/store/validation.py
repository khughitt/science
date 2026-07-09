from __future__ import annotations

from functools import partial
from pathlib import Path

import click
from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import PROV, RDF, SKOS
from science_model.reasoning import EvidenceType

from science_tool.graph.belief_weights import normalize_evidence_type
from science_tool.graph.io import (
    build_input_manifest as _build_input_manifest,
)
from science_tool.graph.io import (
    read_revision_manifest as _read_revision_manifest,
)
from science_tool.graph.patch_membership import validate_patch_membership_convenience
from science_tool.graph.run_resolution import MemberOfCycleError, NoRunReason, resolved_empirical_runs

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

    convenience_errors = validate_patch_membership_convenience(dataset)
    if convenience_errors:
        rows.append(
            {
                "check": "patch_membership_convenience",
                "status": "fail",
                "details": (
                    f"{len(convenience_errors)} convenience edge(s) without a "
                    f"sci:PatchMembership node: {convenience_errors[0]}"
                ),
            }
        )
    else:
        rows.append(
            {
                "check": "patch_membership_convenience",
                "status": "pass",
                "details": "all patch convenience edges backed by sci:PatchMembership nodes",
            }
        )

    run_messages, run_fatal = validate_empirical_run_resolution(dataset)
    if run_messages:
        if run_fatal:
            # Fatal today means a structural `dataset.member-of-cycle` defect
            # (see `validate_empirical_run_resolution`), not "no fingerprinted
            # run" — the per-line message already names the actual defect.
            details = f"structural defect blocking run resolution: {run_messages[0]}"
        else:
            details = f"{len(run_messages)} empirical line(s) without a fingerprinted run: {run_messages[0]}"
        rows.append(
            {
                "check": "empirical_run_resolution",
                "status": "fail" if run_fatal else "warn",
                "details": details,
            }
        )
    else:
        rows.append(
            {
                "check": "empirical_run_resolution",
                "status": "pass",
                "details": "all belief-eligible empirical lines resolve to a fingerprinted run",
            }
        )

    has_failures = any(row["status"] == "fail" for row in rows)
    return rows, has_failures


def _knowledge_and_provenance(dataset: Dataset) -> tuple[Graph, Graph]:
    return (
        dataset.graph(_graph_uri("graph/knowledge")),
        dataset.graph(_graph_uri("graph/provenance")),
    )


def _is_fingerprinted(knowledge: Graph, run_uri: URIRef) -> bool:
    """A run bears a fingerprint iff it carries sci:fingerprintPolicy (Task 8c)."""
    return (run_uri, SCI_NS.fingerprintPolicy, None) in knowledge


def _runs_for_line(
    knowledge: Graph, line: URIRef, datasets: set[URIRef]
) -> tuple[list[URIRef], list[NoRunReason]]:
    """Fingerprinted runs a line resolves to: dataset-derivation union `run_refs`.

    `run_refs` widens the RUN set, never the DATASET set — every entry is
    filtered through the SAME `is_fingerprinted` predicate used for
    dataset-derived resolution, so an unfingerprinted `run_refs` target
    contributes nothing (and adds `RUN_UNFINGERPRINTED` to the reasons).
    `MemberOfCycleError` propagates to the caller (it must be handled per-line,
    not swallowed here).
    """
    is_fingerprinted = partial(_is_fingerprinted, knowledge)

    runs: set[URIRef] = set()
    reasons: list[NoRunReason] = []
    for ds in sorted(datasets, key=str):
        ds_runs, ds_reasons = resolved_empirical_runs(knowledge, ds, is_fingerprinted)
        runs.update(ds_runs)
        reasons.extend(ds_reasons)

    for run_ref in knowledge.objects(line, SCI_NS.runRef):
        if not isinstance(run_ref, URIRef):
            continue
        if is_fingerprinted(run_ref):
            runs.add(run_ref)
        else:
            reasons.append(NoRunReason.RUN_UNFINGERPRINTED)

    if runs:
        return sorted(runs, key=str), []
    return [], reasons


def validate_empirical_run_resolution(dataset: Dataset) -> tuple[list[str], bool]:
    """Belief-eligible empirical lines must resolve to a FINGERPRINTED run.

    Returns (messages, is_fatal). A member_of cycle is fatal; unresolved lines
    warn during P2 and become fatal at the P4 flip (Task 11).

    Resolution reuses `dependence_datasets_by_line` — the same substrate the
    dataset-QA ceiling uses — restricted to `EvidenceType.EMPIRICAL_DATA` lines,
    exactly as `graph/dataset_qa.py` does. `MemberOfCycleError` originates inside
    `_runs_for_line` (via `resolved_empirical_runs`), NOT inside
    `dependence_datasets_by_line`; the try/except therefore wraps the per-line
    loop, and a cycle short-circuits the whole check as fatal.
    """
    from science_tool.graph.dataset_independence import dependence_datasets_by_line

    knowledge, provenance = _knowledge_and_provenance(dataset)
    by_line = dependence_datasets_by_line(knowledge, provenance)

    messages: list[str] = []
    for line, datasets in sorted(by_line.items()):
        evidence_type = next(provenance.objects(line, SCI_NS.evidenceType), None)
        token = normalize_evidence_type(str(evidence_type) if evidence_type is not None else None)
        if token != EvidenceType.EMPIRICAL_DATA:
            continue
        try:
            runs, reasons = _runs_for_line(knowledge, line, datasets)
        except MemberOfCycleError as exc:
            return [f"{line}: dataset.member-of-cycle ({exc})"], True
        if runs:
            continue
        if NoRunReason.RECIPE_ONLY in reasons:
            messages.append(f"{line}: evidence.empirical-run-recipe-only")
        else:
            detail = ", ".join(sorted({r.value for r in reasons})) or "no-provenance"
            messages.append(f"{line}: evidence.empirical-run-unresolved ({detail})")
    return sorted(messages), False


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
