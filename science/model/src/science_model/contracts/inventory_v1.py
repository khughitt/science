from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION: Final = "1"

WarningSeverity = Literal["error", "warning", "info"]


class _InventoryContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InventorySourceLocation(_InventoryContractModel):
    adapter: str
    path: str
    address: str | None = None
    line: int | None = Field(default=None, ge=1)


class InventoryAlias(_InventoryContractModel):
    alias: str
    canonical_id: str


class InventoryReference(_InventoryContractModel):
    relation: str
    target_id: str


class InventoryGraphAddress(_InventoryContractModel):
    address: str
    kind: str
    source: InventorySourceLocation
    canonical_id: str | None = None
    label: str | None = None


class InventoryFindingCandidate(_InventoryContractModel):
    candidate_id: str
    title: str
    targets: list[str] = Field(default_factory=list)
    source: InventorySourceLocation
    reason: str


class InventoryWarning(_InventoryContractModel):
    code: str
    severity: WarningSeverity
    message: str
    path: str | None = None
    canonical_id: str | None = None


class InventoryProjectMetadata(_InventoryContractModel):
    id: str
    name: str
    path: str | None = None
    summary: str | None = None
    status: str | None = None
    aspects: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class InventoryEntity(_InventoryContractModel):
    id: str
    kind: str
    local_id: str
    title: str | None = None
    status: str | None = None
    activity: str | None = None
    registration_state: Literal["core", "ontology", "local", "unknown"] = "unknown"
    scope: Literal["project", "cross-project"] = "project"
    source: InventorySourceLocation
    aliases: list[str] = Field(default_factory=list)
    related: list[InventoryReference] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    review_state: str | None = None
    deprecated_ids: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def canonical_id_has_separator(cls, value: str) -> str:
        if ":" not in value:
            msg = f"Inventory entity id must be canonical '<kind>:<local-id>', got {value!r}."
            raise ValueError(msg)
        return value

    @field_validator("data")
    @classmethod
    def data_values_are_json_serializable(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_json_value(value, "data")
        return value

    @model_validator(mode="after")
    def canonical_id_matches_kind_and_local_id(self) -> Self:
        expected = f"{self.kind}:{self.local_id}"
        if self.id != expected:
            msg = f"Inventory entity id must match kind and local_id, expected {expected!r}, got {self.id!r}."
            raise ValueError(msg)
        return self


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


def canonical_json_bytes(value: BaseModel | dict[str, Any]) -> bytes:
    data = value.model_dump(mode="json", exclude_none=True) if isinstance(value, BaseModel) else value
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _validate_json_value(value: Any, path: str) -> None:
    if value is None or isinstance(value, str | bool | int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            msg = f"{path} must contain JSON-serializable values."
            raise ValueError(msg)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                msg = f"{path} must contain only string object keys."
                raise ValueError(msg)
            _validate_json_value(item, f"{path}.{key}")
        return
    msg = f"{path} must contain JSON-serializable values."
    raise ValueError(msg)


def _sort_key_with_canonical_tie_breaker(item: dict[str, Any], fields: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(item.get(field) or "" for field in fields) + (canonical_json_bytes(item),)


def _normalize_entity_for_content_hash(entity: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entity)
    for key in ("aliases", "source_refs", "targets", "deprecated_ids"):
        normalized[key] = sorted(normalized.get(key, []))
    normalized["related"] = sorted(
        normalized.get("related", []),
        key=lambda item: (item["relation"], item["target_id"]),
    )
    return normalized


def _normalize_project_for_content_hash(project: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(project)
    normalized["aspects"] = sorted(normalized.get("aspects", []))
    normalized["tags"] = sorted(normalized.get("tags", []))
    return normalized


def _normalize_finding_candidate_for_content_hash(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(candidate)
    normalized["targets"] = sorted(normalized.get("targets", []))
    return normalized


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
