from __future__ import annotations

import hashlib
from typing import Any, Final, Literal

from pydantic import Field

from science_model.contracts.inventory_common import (
    InventoryAlias,
    InventoryEntity,
    InventoryFindingCandidate,
    InventoryGraphAddress,
    InventoryProjectMetadata,
    InventoryReference,
    InventorySourceLocation,
    InventoryWarning,
    WarningSeverity,
    _InventoryContractModel,
    _normalize_entity_for_content_hash,
    _normalize_finding_candidate_for_content_hash,
    _normalize_project_for_content_hash,
    _sort_key_with_canonical_tie_breaker,
    canonical_json_bytes,
)

__all__ = [
    "SCHEMA_VERSION",
    "WarningSeverity",
    "InventoryAlias",
    "InventoryEntity",
    "InventoryFindingCandidate",
    "InventoryGraphAddress",
    "InventoryPayload",
    "InventoryProjectMetadata",
    "InventoryReference",
    "InventorySourceLocation",
    "InventoryWarning",
    "canonical_json_bytes",
    "compute_audit_hash",
    "compute_content_hash",
    "finalize_inventory_payload",
]

SCHEMA_VERSION: Final = "1"


class InventoryPayload(_InventoryContractModel):
    schema_version: Literal["1"] = SCHEMA_VERSION
    generated_at: str
    project_id: str
    project_path: str | None = None
    project: InventoryProjectMetadata | None = None
    content_hash: str | None = None
    audit_hash: str | None = None
    entities: list[InventoryEntity] = Field(default_factory=list)
    aliases: list[InventoryAlias] = Field(default_factory=list)
    graph_addresses: list[InventoryGraphAddress] = Field(default_factory=list)
    finding_candidates: list[InventoryFindingCandidate] = Field(default_factory=list)
    warnings: list[InventoryWarning] = Field(default_factory=list)
    watch_paths: list[str] = Field(default_factory=list)


def _payload_for_content_hash(payload: InventoryPayload) -> dict[str, Any]:
    data = payload.model_dump(mode="json", exclude_none=True)
    for key in ("generated_at", "content_hash", "audit_hash", "warnings"):
        data.pop(key, None)
    if "project" in data:
        data["project"] = _normalize_project_for_content_hash(data["project"])
    data["entities"] = sorted(
        (_normalize_entity_for_content_hash(item) for item in data.get("entities", [])),
        key=lambda item: _sort_key_with_canonical_tie_breaker(item, ("id",)),
    )
    data["aliases"] = sorted(
        data.get("aliases", []),
        key=lambda item: _sort_key_with_canonical_tie_breaker(item, ("alias",)),
    )
    data["graph_addresses"] = sorted(
        data.get("graph_addresses", []),
        key=lambda item: _sort_key_with_canonical_tie_breaker(item, ("address",)),
    )
    data["finding_candidates"] = sorted(
        (_normalize_finding_candidate_for_content_hash(item) for item in data.get("finding_candidates", [])),
        key=lambda item: _sort_key_with_canonical_tie_breaker(item, ("candidate_id",)),
    )
    data["watch_paths"] = sorted(data.get("watch_paths", []))
    return data


def _payload_for_audit_hash(payload: InventoryPayload) -> dict[str, Any]:
    data = payload.model_dump(mode="json", exclude_none=True)
    for key in (
        "generated_at",
        "content_hash",
        "audit_hash",
        "entities",
        "aliases",
        "graph_addresses",
        "finding_candidates",
    ):
        data.pop(key, None)
    if "project" in data:
        data["project"] = _normalize_project_for_content_hash(data["project"])
    data["warnings"] = sorted(
        data.get("warnings", []),
        key=lambda item: _sort_key_with_canonical_tie_breaker(
            item,
            ("severity", "code", "path", "canonical_id"),
        ),
    )
    data["watch_paths"] = sorted(data.get("watch_paths", []))
    return data


def compute_content_hash(payload: InventoryPayload) -> str:
    return hashlib.sha256(canonical_json_bytes(_payload_for_content_hash(payload))).hexdigest()


def compute_audit_hash(payload: InventoryPayload) -> str:
    return hashlib.sha256(canonical_json_bytes(_payload_for_audit_hash(payload))).hexdigest()


def finalize_inventory_payload(payload: InventoryPayload) -> InventoryPayload:
    content_hash = compute_content_hash(payload)
    audit_hash = compute_audit_hash(payload)
    return payload.model_copy(update={"content_hash": content_hash, "audit_hash": audit_hash})
