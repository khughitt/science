"""Dataset-QA seam: consume schema-driven QA verdicts into the graph (Spec 5).

Reads each opted-in dataset's persisted `qa_report.json` (the artifact `science datasets qa
--report-dir` writes), stamps the structural verdict on the dataset node, and stamps
SCI_NS.qaFailedDataset on each EMPIRICAL evidence line resting on a structurally-failed
dependence dataset. Belief consumes those triples; QA itself is never recomputed here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from rdflib import Graph, URIRef
from rdflib import Literal as RDFLiteral
from science_model.reasoning import EvidenceType

from .belief_weights import normalize_evidence_type
from .dataset_independence import dependence_datasets_by_line
from .dataset_usage import project_entity_uri
from .io import SCI_NS

if TYPE_CHECKING:
    from .sources import ProjectSources


class DatasetQaReportError(ValueError):
    """A dataset declares a qa_report that is missing, unreadable, or malformed (fail early)."""


def _read_structural_verdict(report_path: Path, dataset_id: str) -> tuple[bool, list[str], str]:
    try:
        raw = report_path.read_text(encoding="utf-8")
        report = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetQaReportError(
            f"{dataset_id}: qa_report {report_path} is missing or unreadable: {exc}"
        ) from exc
    if not isinstance(report, dict) or "package_structural_failed" not in report:
        raise DatasetQaReportError(
            f"{dataset_id}: qa_report {report_path} has no 'package_structural_failed' field"
        )
    failed = report["package_structural_failed"]
    if not isinstance(failed, bool):
        # Fail loud: do NOT coerce. bool("false") is True, which would silently invert intent.
        raise DatasetQaReportError(
            f"{dataset_id}: qa_report {report_path} 'package_structural_failed' must be a JSON "
            f"boolean, got {failed!r}"
        )
    failed_resources = sorted(
        str(resource.get("resource", ""))
        for resource in report.get("resources", [])
        if isinstance(resource, dict) and resource.get("status") == "fail"
    )
    report_hash = "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return failed, failed_resources, report_hash


def emit_dataset_qa_layer(knowledge: Graph, provenance: Graph, sources: ProjectSources) -> None:
    project_root = Path(sources.project_root)
    failed_datasets: set[URIRef] = set()
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        qa_report = getattr(entity, "qa_report", "")
        if not isinstance(qa_report, str):
            raise DatasetQaReportError(f"{entity.canonical_id}: qa_report must be a string")
        if not qa_report:
            continue
        dataset_uri = project_entity_uri(entity.canonical_id)
        failed, failed_resources, report_hash = _read_structural_verdict(
            project_root / qa_report, entity.canonical_id
        )
        provenance.add((dataset_uri, SCI_NS.qaStructuralFailed, RDFLiteral(failed)))
        provenance.add((dataset_uri, SCI_NS.qaReport, RDFLiteral(qa_report)))
        provenance.add((dataset_uri, SCI_NS.qaReportHash, RDFLiteral(report_hash)))
        for resource in failed_resources:
            provenance.add((dataset_uri, SCI_NS.qaFailedResource, RDFLiteral(resource)))
        if failed:
            failed_datasets.add(dataset_uri)

    if not failed_datasets:
        return
    for line, datasets in dependence_datasets_by_line(knowledge, provenance).items():
        evidence_type = next(provenance.objects(line, SCI_NS.evidenceType), None)
        token = normalize_evidence_type(str(evidence_type) if evidence_type is not None else None)
        if token != EvidenceType.EMPIRICAL_DATA:
            continue
        for dataset in sorted(datasets & failed_datasets, key=str):
            provenance.add((line, SCI_NS.qaFailedDataset, dataset))
