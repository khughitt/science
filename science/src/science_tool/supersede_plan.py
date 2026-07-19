from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from science_tool.plan_common import PathTransition, SupersedeSelection


class SupersededChainReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    survivor: str
    members: list[str]
    linear: bool


class NonLinearReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[str]
    reason: str


class SkippedKind(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str


class InvalidRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    path: str
    subject: str
    predicate: str
    object: str
    message: str


class TargetReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    superseder: str
    path: str
    reason: str


class UnbackedInverse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    superseder: str
    reason: str


class SupersedePreviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chains: list[SupersededChainReport]
    non_linear: list[NonLinearReport]
    to_mark: list[str]
    skipped_kinds: list[SkippedKind]
    to_repair: list[str]
    invalid_relations: list[InvalidRelation]
    archived_targets: list[TargetReport]
    unmanaged_targets: list[TargetReport]
    unbacked_inverses: list[UnbackedInverse]


class SupersedePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    project_root: str
    material_version: int
    preview_date: str
    selection: SupersedeSelection
    decision_inputs_sha256: str
    to_mark: list[str]
    to_repair: list[str]
    writes: list[PathTransition]
    preview_report: SupersedePreviewReport
