"""inventory_v2: sibling export contract to inventory_v1.

Adds a top-level `overlays[]` list (the project-overlay projection) and pins
`schema_version` to "2". All v1 models except `InventoryPayload` are reused
verbatim; the `_`-prefixed v1 helpers are imported here on purpose, so a future
v1 rename fails this module's tests loudly.

The commons inventory is an `InventoryPayload` with `project_id="commons"`
(a fixed sentinel - the commons store is not a project), `project=None`,
`project_path` set to the commons root, and `overlays=[]`. A project payload
has `entities` of `scope="project"` only and may carry a non-empty `overlays`.
"""

# ruff: noqa: F401, F822
from __future__ import annotations

import hashlib
from typing import Any, Final, Literal

from pydantic import Field, field_validator

from science_model.contracts.inventory_v1 import (
    InventoryAlias,
    InventoryEntity,
    InventoryFindingCandidate,
    InventoryGraphAddress,
    InventoryProjectMetadata,
    InventoryReference,
    InventorySourceLocation,
    InventoryWarning,
    _InventoryContractModel,
    _normalize_entity_for_content_hash,
    _normalize_finding_candidate_for_content_hash,
    _normalize_project_for_content_hash,
    _sort_key_with_canonical_tie_breaker,
    _validate_json_value,
    canonical_json_bytes,
)

__all__ = [
    "SCHEMA_VERSION",
    "InventoryAlias",
    "InventoryEntity",
    "InventoryFindingCandidate",
    "InventoryGraphAddress",
    "InventoryOverlay",
    "InventoryPayload",
    "InventoryProjectMetadata",
    "InventoryReference",
    "InventorySourceLocation",
    "InventoryWarning",
    "compute_audit_hash",
    "compute_content_hash",
    "finalize_inventory_payload",
]

SCHEMA_VERSION: Final = "2"


class InventoryOverlay(_InventoryContractModel):
    overlay_of: str
    project_id: str
    source: InventorySourceLocation
    pin_version: str | None = None
    pin_effective_version: str | None = None
    project_only_fields: dict[str, Any] = Field(default_factory=dict)
    append_fields: dict[str, Any] = Field(default_factory=dict)
    body_sections: list[str] = Field(default_factory=list)

    @field_validator("overlay_of")
    @classmethod
    def overlay_of_has_separator(cls, value: str) -> str:
        kind, separator, local_id = value.partition(":")
        if not separator or not kind or not local_id:
            msg = (
                "Inventory overlay overlay_of must be canonical "
                f"'<kind>:<local-id>', got {value!r}."
            )
            raise ValueError(msg)
        return value

    @field_validator("project_only_fields", "append_fields")
    @classmethod
    def merge_fields_are_json_serializable(
        cls, value: dict[str, Any]
    ) -> dict[str, Any]:
        _validate_json_value(value, "merge_fields")
        return value


class InventoryPayload(_InventoryContractModel):
    schema_version: Literal["2"] = SCHEMA_VERSION
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
    overlays: list[InventoryOverlay] = Field(default_factory=list)


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
        (
            _normalize_finding_candidate_for_content_hash(item)
            for item in data.get("finding_candidates", [])
        ),
        key=lambda item: _sort_key_with_canonical_tie_breaker(item, ("candidate_id",)),
    )
    data["overlays"] = sorted(
        data.get("overlays", []),
        key=lambda item: _sort_key_with_canonical_tie_breaker(
            item, ("overlay_of", "project_id")
        ),
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
        "overlays",
    ):
        data.pop(key, None)
    if "project" in data:
        data["project"] = _normalize_project_for_content_hash(data["project"])
    data["warnings"] = sorted(
        data.get("warnings", []),
        key=lambda item: _sort_key_with_canonical_tie_breaker(
            item, ("severity", "code", "path", "canonical_id")
        ),
    )
    data["watch_paths"] = sorted(data.get("watch_paths", []))
    return data


def compute_content_hash(payload: InventoryPayload) -> str:
    return hashlib.sha256(
        canonical_json_bytes(_payload_for_content_hash(payload))
    ).hexdigest()


def compute_audit_hash(payload: InventoryPayload) -> str:
    return hashlib.sha256(
        canonical_json_bytes(_payload_for_audit_hash(payload))
    ).hexdigest()


def finalize_inventory_payload(payload: InventoryPayload) -> InventoryPayload:
    content_hash = compute_content_hash(payload)
    audit_hash = compute_audit_hash(payload)
    return payload.model_copy(
        update={"content_hash": content_hash, "audit_hash": audit_hash}
    )
