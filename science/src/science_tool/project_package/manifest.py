"""Strict manifest model for serialized project-package v1 bundles."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "science-project-serialized.v1"

_SAFE_PROJECT_ID_RE = re.compile(r"\A[A-Za-z0-9._-]+\Z")
_SHA256_RE = r"^[0-9a-f]{64}$"


class ProjectInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    label: str
    summary: str | None

    @field_validator("id")
    @classmethod
    def _safe_id(cls, value: str) -> str:
        if (
            value in ("", ".", "..")
            or "/" in value
            or "\\" in value
            or not _SAFE_PROJECT_ID_RE.match(value)
        ):
            raise ValueError(f"unsafe project id: {value!r}")
        return value


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    git_commit: str
    tool: str


class BoundaryAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    passed: bool
    forced: bool


class _ManifestPathMixin(BaseModel):
    path: str

    @field_validator("path")
    @classmethod
    def _safe_manifest_path(cls, value: str) -> str:
        parts = value.split("/")
        if (
            value == ""
            or value.startswith("/")
            or "\\" in value
            or any(part in ("", ".", "..") for part in parts)
        ):
            raise ValueError(f"unsafe manifest path: {value!r}")
        return value


class FileRecord(_ManifestPathMixin):
    model_config = ConfigDict(extra="forbid", strict=True)

    sha256: str = Field(pattern=_SHA256_RE)
    bytes: int = Field(ge=0)


class PayloadRecord(_ManifestPathMixin):
    model_config = ConfigDict(extra="forbid", strict=True)

    sha256: str = Field(pattern=_SHA256_RE)
    bytes: int = Field(ge=0)
    git_tracked: bool


class SerializedManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["science-project-serialized.v1"]
    project: ProjectInfo
    data_version: str
    provenance: Provenance
    boundary_audit: BoundaryAudit
    files: list[FileRecord]
    payloads: list[PayloadRecord]

    @model_validator(mode="after")
    def _records_are_unique_and_sorted(self) -> SerializedManifest:
        file_paths = [record.path for record in self.files]
        payload_paths = [record.path for record in self.payloads]
        _validate_ordered_unique("files", file_paths)
        _validate_ordered_unique("payloads", payload_paths)
        if set(file_paths) & set(payload_paths):
            raise ValueError("duplicate path across files and payloads")
        return self


def _validate_ordered_unique(label: str, paths: list[str]) -> None:
    if len(set(paths)) != len(paths):
        raise ValueError(f"duplicate {label} path")
    if paths != sorted(paths):
        raise ValueError(f"{label} must be sorted ascending by path")


def data_version_chunks(
    files: Iterable[Mapping[str, object]],
    payloads: Iterable[Mapping[str, object]],
) -> list[bytes]:
    chunks: list[bytes] = []
    for record in files:
        chunks.append(
            json.dumps(
                {
                    "path": record["path"],
                    "sha256": record["sha256"],
                    "bytes": record["bytes"],
                },
                sort_keys=True,
            ).encode("utf-8")
        )
    for record in payloads:
        chunks.append(
            json.dumps(
                {
                    "path": record["path"],
                    "sha256": record["sha256"],
                    "bytes": record["bytes"],
                    "git_tracked": record["git_tracked"],
                },
                sort_keys=True,
            ).encode("utf-8")
        )
    return chunks
