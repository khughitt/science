"""RG1 parser for bio.reference_graph node and edge projections."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, get_args

from science_model.packages.schema import DatasetUsage

REFERENCE_GRAPH_PROFILE_TOKEN = "+bio.reference_graph/"
REFERENCE_GRAPH_MEMBER_PROFILE_TOKEN = "+bio.reference_graph.member/"
REFERENCE_GRAPH_REQUIRED_NODE_COLUMNS = frozenset(
    {"member_key", "member_kind", "label", "status", "replaced_by", "dataset_usage"}
)
REFERENCE_GRAPH_REQUIRED_EDGE_COLUMNS = frozenset({"subject", "predicate", "object"})
REFERENCE_GRAPH_STATUSES = frozenset({"active", "deprecated", "withdrawn"})
REFERENCE_GRAPH_FORMATS = frozenset({"rdf_turtle", "rdf_ntriples", "jsonl_edges"})
REFERENCE_GRAPH_USAGE_ROLES = frozenset(get_args(DatasetUsage.model_fields["role"].annotation))
REFERENCE_GRAPH_USAGE_OVERLAPS = frozenset(get_args(DatasetUsage.model_fields["overlap"].annotation))


class ReferenceGraphCollectionError(ValueError):
    """A bio.reference_graph projection row violates the RG1 row contract."""


@dataclass(frozen=True, slots=True)
class ReferenceGraphNode:
    member_key: str
    member_kind: str
    label: str
    status: str
    replaced_by: tuple[str, ...]
    dataset_usage: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ReferenceGraphEdge:
    subject: str
    predicate: str
    object: str
    evidence: str | None
    dataset_usage: tuple[dict[str, Any], ...]


def is_reference_graph_frontmatter(fm: dict[str, Any]) -> bool:
    profile = str(fm.get("schema_profile") or "")
    return (fm.get("kind") or fm.get("type")) == "dataset" and REFERENCE_GRAPH_PROFILE_TOKEN in f"+{profile}"


def is_reference_graph_member_frontmatter(fm: dict[str, Any]) -> bool:
    profile = str(fm.get("schema_profile") or "")
    return (fm.get("kind") or fm.get("type")) == "dataset" and REFERENCE_GRAPH_MEMBER_PROFILE_TOKEN in f"+{profile}"


def _split_semicolon(raw: str, *, field: str, row_number: int) -> tuple[str, ...]:
    text = raw.strip()
    if not text:
        return ()
    parts = tuple(part.strip() for part in raw.split(";"))
    if any(not part for part in parts):
        raise ReferenceGraphCollectionError(f"row {row_number}: {field} contains an empty token")
    if len(set(parts)) != len(parts):
        raise ReferenceGraphCollectionError(f"row {row_number}: {field} contains a duplicate token")
    return parts


def _dataset_usage_defect(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return "entry is not an object"
    ref = entry.get("ref")
    if not isinstance(ref, str) or not ref.startswith("dataset:"):
        return "ref must be a 'dataset:' reference"
    role = entry.get("role")
    if role not in REFERENCE_GRAPH_USAGE_ROLES:
        return f"role must be one of {sorted(REFERENCE_GRAPH_USAGE_ROLES)}"
    if "overlap" in entry and entry["overlap"] not in REFERENCE_GRAPH_USAGE_OVERLAPS:
        return f"overlap must be one of {sorted(REFERENCE_GRAPH_USAGE_OVERLAPS)}"
    return None


def _parse_dataset_usage(raw: str, *, row_number: int) -> tuple[dict[str, Any], ...]:
    text = raw.strip()
    if not text:
        return ()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReferenceGraphCollectionError(f"row {row_number}: dataset_usage is not valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, list):
        raise ReferenceGraphCollectionError(f"row {row_number}: dataset_usage must be a JSON list")
    out: list[dict[str, Any]] = []
    for index, entry in enumerate(parsed):
        defect = _dataset_usage_defect(entry)
        if defect is not None:
            raise ReferenceGraphCollectionError(f"row {row_number}: dataset_usage[{index}] malformed -- {defect}")
        out.append(entry)
    return tuple(out)


def parse_node_index_rows(rows: list[dict[str, Any]]) -> list[ReferenceGraphNode]:
    out: list[ReferenceGraphNode] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        missing = [col for col in sorted(REFERENCE_GRAPH_REQUIRED_NODE_COLUMNS) if col not in row]
        if missing:
            raise ReferenceGraphCollectionError(f"row {row_number}: missing required columns {missing}")
        member_key = str(row.get("member_key") or "").strip()
        if not member_key:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank member_key")
        if member_key in seen:
            raise ReferenceGraphCollectionError(f"row {row_number}: duplicate member_key {member_key!r}")
        seen.add(member_key)
        member_kind = str(row.get("member_kind") or "").strip()
        if not member_kind:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank member_kind")
        label = str(row.get("label") or "").strip()
        if not label:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank label")
        status = str(row.get("status") or "").strip()
        if status not in REFERENCE_GRAPH_STATUSES:
            raise ReferenceGraphCollectionError(
                f"row {row_number}: status must be one of {sorted(REFERENCE_GRAPH_STATUSES)}"
            )
        out.append(
            ReferenceGraphNode(
                member_key=member_key,
                member_kind=member_kind,
                label=label,
                status=status,
                replaced_by=_split_semicolon(
                    str(row.get("replaced_by") or ""), field="replaced_by", row_number=row_number
                ),
                dataset_usage=_parse_dataset_usage(str(row.get("dataset_usage") or ""), row_number=row_number),
            )
        )
    return out


def parse_edge_rows(rows: list[dict[str, Any]]) -> list[ReferenceGraphEdge]:
    out: list[ReferenceGraphEdge] = []
    for row_number, row in enumerate(rows, start=1):
        missing = [col for col in sorted(REFERENCE_GRAPH_REQUIRED_EDGE_COLUMNS) if col not in row]
        if missing:
            raise ReferenceGraphCollectionError(f"row {row_number}: missing required columns {missing}")
        subject = str(row.get("subject") or "").strip()
        predicate = str(row.get("predicate") or "").strip()
        object_ = str(row.get("object") or "").strip()
        if not subject:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank subject")
        if not predicate:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank predicate")
        if not object_:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank object")
        evidence = str(row["evidence"]).strip() if row.get("evidence") not in (None, "") else None
        out.append(
            ReferenceGraphEdge(
                subject=subject,
                predicate=predicate,
                object=object_,
                evidence=evidence,
                dataset_usage=_parse_dataset_usage(str(row.get("dataset_usage") or ""), row_number=row_number),
            )
        )
    return out
