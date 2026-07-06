"""Dataset usage projection and graph helpers for Pillar B1."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Callable, Literal

from rdflib import Graph, URIRef
from rdflib import Literal as RDFLiteral
from rdflib.namespace import RDF
from science_model.entities import Entity
from science_model.packages.schema import DerivationBlock

from science_tool.graph.store import PROJECT_NS, SCI_NS

UsageSource = Literal[
    "authored",
    "derivation.inputs",
    "derivation.transformations",
    "geneset.members_resource",
    "reference_graph.node_index_resource",
]

_UNRESERVED = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


class DatasetUsageMaterializationError(ValueError):
    """A usage record cannot be safely materialized into graph truth."""


@dataclass(frozen=True, slots=True)
class DatasetUsageRecord:
    consumer_id: str
    dataset_ref: str
    role: str
    overlap: str
    source: UsageSource
    source_path: str
    row_key: str = ""

    def payload(self) -> dict[str, str]:
        return {
            "consumer_id": self.consumer_id,
            "dataset_ref": self.dataset_ref,
            "role": self.role,
            "overlap": self.overlap,
            "source": self.source,
            "source_path": self.source_path,
            "row_key": self.row_key,
        }


def usage_records_for_entity(
    entity: Entity,
    *,
    resolve_dataset_ref: Callable[[str], str] | None = None,
) -> list[DatasetUsageRecord]:
    records: list[DatasetUsageRecord] = []
    materialized_refs: set[str] = set()
    source_path = str(getattr(entity, "file_path", "") or "")

    for usage in getattr(entity, "dataset_usage", []) or []:
        dataset_ref = _canonical_dataset_ref(str(usage.ref), resolve_dataset_ref)
        _reject_self_reference(entity, dataset_ref)
        materialized_refs.add(dataset_ref)
        records.append(
            DatasetUsageRecord(
                consumer_id=entity.canonical_id,
                dataset_ref=dataset_ref,
                role=str(usage.role),
                overlap=str(usage.overlap or "unknown"),
                source="authored",
                source_path=source_path,
            )
        )

    if entity.kind == "paper" and getattr(entity, "datasets", None):
        raise DatasetUsageMaterializationError(
            f"{entity.canonical_id}: paper.datasets is retired; use dataset_usage entries instead"
        )

    derivation = getattr(entity, "derivation", None)
    if entity.kind == "dataset" and isinstance(derivation, DerivationBlock):
        for dataset_ref in derivation.inputs:
            dataset_ref = _canonical_dataset_ref(str(dataset_ref), resolve_dataset_ref)
            _reject_self_reference(entity, dataset_ref)
            records.append(
                DatasetUsageRecord(
                    consumer_id=entity.canonical_id,
                    dataset_ref=dataset_ref,
                    role="upstream",
                    overlap="unknown",
                    source="derivation.inputs",
                    source_path=source_path,
                )
            )
        for index, transformation in enumerate(getattr(derivation, "transformations", []) or []):
            if not isinstance(transformation, dict):
                raise DatasetUsageMaterializationError(
                    f"{entity.canonical_id}: derivation.transformations[{index}] is not an object"
                )
            raw_ref = transformation.get("dataset")
            if not isinstance(raw_ref, str) or not raw_ref.startswith("dataset:"):
                raise DatasetUsageMaterializationError(
                    f"{entity.canonical_id}: derivation.transformations[{index}].dataset "
                    "must be a dataset:<slug> entity reference"
                )
            dataset_ref = _canonical_dataset_ref(raw_ref, resolve_dataset_ref)
            _reject_self_reference(entity, dataset_ref)
            records.append(
                DatasetUsageRecord(
                    consumer_id=entity.canonical_id,
                    dataset_ref=dataset_ref,
                    role="reference",
                    overlap="unknown",
                    source="derivation.transformations",
                    source_path=source_path,
                )
            )

    return records


def usage_records_for_geneset_rows(
    *,
    collection_id: str,
    source_path: str,
    rows,
    resolve_dataset_ref: Callable[[str], str] | None = None,
) -> list[DatasetUsageRecord]:
    records: list[DatasetUsageRecord] = []
    seen_virtual: dict[str, str] = {}
    for row in rows:
        consumer_uri = virtual_geneset_member_uri(collection_id, row.set_key)
        previous = seen_virtual.get(str(consumer_uri))
        if previous is not None and previous != row.set_key:
            raise DatasetUsageMaterializationError(
                f"{collection_id}: set_key {row.set_key!r} collides with {previous!r}"
            )
        seen_virtual[str(consumer_uri)] = row.set_key
        for usage in row.dataset_usage:
            dataset_ref = _canonical_dataset_ref(str(usage["ref"]), resolve_dataset_ref)
            overlap = str(usage.get("overlap") or "unknown")
            records.append(
                DatasetUsageRecord(
                    consumer_id=str(consumer_uri),
                    dataset_ref=dataset_ref,
                    role=str(usage["role"]),
                    overlap=overlap,
                    source="geneset.members_resource",
                    source_path=source_path,
                    row_key=row.set_key,
                )
            )
    return records


def usage_records_for_reference_graph_nodes(
    *,
    collection_id: str,
    source_path: str,
    rows,
    resolve_dataset_ref: Callable[[str], str] | None = None,
) -> list[DatasetUsageRecord]:
    records: list[DatasetUsageRecord] = []
    seen_virtual: dict[str, str] = {}
    for row in rows:
        consumer_uri = virtual_reference_graph_member_uri(collection_id, row.member_key)
        previous = seen_virtual.get(str(consumer_uri))
        if previous is not None and previous != row.member_key:
            raise DatasetUsageMaterializationError(
                f"{collection_id}: member_key {row.member_key!r} collides with {previous!r}"
            )
        seen_virtual[str(consumer_uri)] = row.member_key
        for usage in row.dataset_usage:
            dataset_ref = _canonical_dataset_ref(str(usage["ref"]), resolve_dataset_ref)
            overlap = str(usage.get("overlap") or "unknown")
            records.append(
                DatasetUsageRecord(
                    consumer_id=str(consumer_uri),
                    dataset_ref=dataset_ref,
                    role=str(usage["role"]),
                    overlap=overlap,
                    source="reference_graph.node_index_resource",
                    source_path=source_path,
                    row_key=row.member_key,
                )
            )
    return records


def _canonical_dataset_ref(raw_ref: str, resolve_dataset_ref: Callable[[str], str] | None) -> str:
    if resolve_dataset_ref is None:
        return raw_ref
    return resolve_dataset_ref(raw_ref)


def _reject_self_reference(entity: Entity, dataset_ref: str) -> None:
    if entity.kind == "dataset" and dataset_ref == entity.canonical_id:
        raise DatasetUsageMaterializationError(f"{entity.canonical_id}: self-referential dataset usage {dataset_ref!r}")


def project_entity_uri(canonical_id: str) -> URIRef:
    if canonical_id.startswith("http://") or canonical_id.startswith("https://"):
        return URIRef(canonical_id)
    kind, slug = canonical_id.split(":", 1)
    return URIRef(PROJECT_NS[f"{kind}/{slug.lower()}"])


def virtual_geneset_member_uri(collection_id: str, set_key: str) -> URIRef:
    if not collection_id.startswith("dataset:"):
        raise DatasetUsageMaterializationError(f"gene-set collection id must be dataset:<slug>, got {collection_id!r}")
    dataset_slug = collection_id.split(":", 1)[1].lower()
    return URIRef(PROJECT_NS[f"virtual/geneset-member/{dataset_slug}/{_encode_path_segment(set_key)}"])


def virtual_reference_graph_member_uri(collection_id: str, member_key: str) -> URIRef:
    if not collection_id.startswith("dataset:"):
        raise DatasetUsageMaterializationError(
            f"reference-graph collection id must be dataset:<slug>, got {collection_id!r}"
        )
    dataset_slug = collection_id.split(":", 1)[1].lower()
    return URIRef(PROJECT_NS[f"virtual/reference-graph-member/{dataset_slug}/{_encode_path_segment(member_key)}"])


def _encode_path_segment(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    out: list[str] = []
    for byte in normalized.encode("utf-8"):
        if byte in _UNRESERVED:
            out.append(chr(byte))
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def usage_node_uri(record: DatasetUsageRecord) -> URIRef:
    payload = json.dumps(record.payload(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return URIRef(PROJECT_NS[f"dataset-usage/{digest}"])


def _consumer_uri(consumer_id: str) -> URIRef:
    if consumer_id.startswith(("http://", "https://")):
        return URIRef(consumer_id)
    if ":" in consumer_id:
        return project_entity_uri(consumer_id)
    return URIRef(consumer_id)


def add_usage_record_to_graph(record: DatasetUsageRecord, graph: Graph) -> None:
    node = usage_node_uri(record)
    consumer = _consumer_uri(record.consumer_id)
    dataset_uri = project_entity_uri(record.dataset_ref)
    graph.add((consumer, SCI_NS.hasDatasetUsage, node))
    graph.add((node, RDF.type, SCI_NS.DatasetUsage))
    graph.add((node, SCI_NS.dataset, dataset_uri))
    graph.add((node, SCI_NS.usageRole, RDFLiteral(record.role)))
    graph.add((node, SCI_NS.usageOverlap, RDFLiteral(record.overlap)))
    graph.add((node, SCI_NS.usageSource, RDFLiteral(record.source)))
