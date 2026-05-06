"""Pydantic schema for the managed-artifact registry capabilities matrix."""

from __future__ import annotations

import re
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Consumer(str, Enum):
    DIRECT_EXECUTE = "direct_execute"
    SCIENCE_LOADER = "science_loader"
    NATIVE_TOOL = "native_tool"


class HeaderKind(str, Enum):
    SHEBANG_COMMENT = "shebang_comment"
    COMMENT = "comment"
    SIDECAR_METADATA = "sidecar_metadata"
    NONE_WITH_REGISTRY_HASH_ONLY = "none_with_registry_hash_only"


class ExtensionKind(str, Enum):
    SOURCED_SIDECAR = "sourced_sidecar"
    MERGED_SIDECAR = "merged_sidecar"
    GENERATED_EFFECTIVE_FILE = "generated_effective_file"
    NONE = "none"


class TransactionKind(str, Enum):
    TEMP_COMMIT = "temp_commit"
    MANIFEST = "manifest"


class MigrationKind(str, Enum):
    BYTE_REPLACE = "byte_replace"
    PROJECT_ACTION = "project_action"
    HYBRID = "hybrid"


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MODE_RE = re.compile(r"^0[0-7]{3}$")
_VERSION_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}(?:\.\d+)?$")


class HeaderProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: HeaderKind
    comment_prefix: str | None = None

    @model_validator(mode="after")
    def _check_kind_specific(self) -> "HeaderProtocol":
        if self.kind in (HeaderKind.SHEBANG_COMMENT, HeaderKind.COMMENT) and not self.comment_prefix:
            raise ValueError(f"header_protocol kind {self.kind.value} requires comment_prefix")
        return self


class ExtensionProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ExtensionKind
    sidecar_path: str | None = None
    hook_namespace: str | None = None
    contract: str | None = None
    rationale: str | None = None

    @model_validator(mode="after")
    def _check_kind_specific(self) -> "ExtensionProtocol":
        if self.kind in (ExtensionKind.SOURCED_SIDECAR, ExtensionKind.MERGED_SIDECAR) and not self.sidecar_path:
            raise ValueError(f"extension_protocol kind {self.kind.value} requires sidecar_path")
        if self.kind is ExtensionKind.NONE and not self.rationale:
            raise ValueError("extension_protocol kind none requires rationale")
        return self


class MutationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requires_clean_worktree: bool = True
    commit_default: bool = True
    transaction_kind: TransactionKind = TransactionKind.TEMP_COMMIT


class HashEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Annotated[str, Field(pattern=_VERSION_RE.pattern)]
    hash: Annotated[str, Field(pattern=_SHA256_RE.pattern)]


class BashImpl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["bash"]
    shell: Literal["bash", "sh"] = "bash"
    working_dir: str = "."
    timeout_seconds: int = Field(gt=0, le=600)
    check: str
    apply: str


class PythonImpl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["python"]
    module: str  # dotted import path


class MigrationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    description: str
    impl: PythonImpl | BashImpl = Field(discriminator="kind")
    touched_paths: list[str] = Field(default_factory=list)
    reversible: bool = False
    idempotent: bool = True


class MigrationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_version: Annotated[str, Field(alias="from", pattern=_VERSION_RE.pattern)]
    to_version: Annotated[str, Field(alias="to", pattern=_VERSION_RE.pattern)]
    kind: MigrationKind
    summary: str
    steps: list[MigrationStep] = Field(default_factory=list)

    @model_validator(mode="after")
    def _byte_replace_has_no_steps(self) -> "MigrationEntry":
        if self.kind is MigrationKind.BYTE_REPLACE and self.steps:
            raise ValueError("kind byte_replace must not declare steps")
        if self.kind is MigrationKind.PROJECT_ACTION and not self.steps:
            raise ValueError("kind project_action requires at least one step")
        return self


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source: str
    install_target: str
    description: str

    content_type: Literal["text", "binary"]
    newline: Literal["lf", "crlf", "preserve"] = "lf"
    mode: Annotated[str, Field(pattern=_MODE_RE.pattern)]
    consumer: Consumer

    header_protocol: HeaderProtocol
    extension_protocol: ExtensionProtocol
    mutation_policy: MutationPolicy

    version: Annotated[str, Field(pattern=_VERSION_RE.pattern)]
    current_hash: Annotated[str, Field(pattern=_SHA256_RE.pattern)]
    previous_hashes: list[HashEntry] = Field(default_factory=list)

    migrations: list[MigrationEntry] = Field(default_factory=list)
    changelog: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consumer_extension_pairing(self) -> "Artifact":
        c = self.consumer
        ek = self.extension_protocol.kind
        valid_pairs: dict[Consumer, set[ExtensionKind]] = {
            Consumer.DIRECT_EXECUTE: {ExtensionKind.SOURCED_SIDECAR, ExtensionKind.NONE},
            Consumer.SCIENCE_LOADER: {ExtensionKind.MERGED_SIDECAR, ExtensionKind.NONE},
            Consumer.NATIVE_TOOL: {ExtensionKind.GENERATED_EFFECTIVE_FILE, ExtensionKind.NONE},
        }
        if ek not in valid_pairs[c]:
            raise ValueError(
                f"extension_protocol.kind {ek.value!r} is invalid for consumer {c.value!r}; "
                f"allowed: {sorted(k.value for k in valid_pairs[c])}"
            )
        return self

    @model_validator(mode="after")
    def _no_duplicate_hash(self) -> "Artifact":
        prev_hashes = {h.hash for h in self.previous_hashes}
        if self.current_hash in prev_hashes:
            raise ValueError("duplicate hash: current_hash also appears in previous_hashes")
        if len(prev_hashes) != len(self.previous_hashes):
            raise ValueError("duplicate hash: previous_hashes contains repeats")
        return self


class Pin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    pinned_to: Annotated[str, Field(pattern=_VERSION_RE.pattern)]
    pinned_hash: Annotated[str, Field(pattern=_SHA256_RE.pattern)]
    rationale: str
    revisit_by: str  # ISO date YYYY-MM-DD; not regex-validated here


class Registry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifacts: list[Artifact] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_names(self) -> "Registry":
        names = [a.name for a in self.artifacts]
        if len(names) != len(set(names)):
            raise ValueError("registry artifacts must have unique names")
        return self
