from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1"

WarningSeverity = Literal["error", "warning", "info"]


class InventorySourceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: str
    path: str
    address: str | None = None
    line: int | None = Field(default=None, ge=1)


class InventoryAlias(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str
    canonical_id: str


class InventoryReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: str
    target_id: str


class InventoryGraphAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str
    kind: str
    source: InventorySourceLocation
    canonical_id: str | None = None
    label: str | None = None


class InventoryFindingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    title: str
    targets: list[str] = Field(default_factory=list)
    source: InventorySourceLocation
    reason: str


class InventoryWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: WarningSeverity
    message: str
    path: str | None = None
    canonical_id: str | None = None


class InventoryProjectMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    path: str | None = None
    summary: str | None = None
    status: str | None = None
    aspects: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class InventoryEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class InventoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
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


def _payload_for_content_hash(payload: InventoryPayload) -> dict[str, Any]:
    data = payload.model_dump(mode="json", exclude_none=True)
    for key in ("generated_at", "content_hash", "audit_hash", "warnings"):
        data.pop(key, None)
    data["entities"] = sorted(data.get("entities", []), key=lambda item: item["id"])
    data["aliases"] = sorted(data.get("aliases", []), key=lambda item: item["alias"])
    data["graph_addresses"] = sorted(data.get("graph_addresses", []), key=lambda item: item["address"])
    data["finding_candidates"] = sorted(data.get("finding_candidates", []), key=lambda item: item["candidate_id"])
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
        key=lambda item: (item["severity"], item["code"], item.get("path") or "", item.get("canonical_id") or ""),
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
