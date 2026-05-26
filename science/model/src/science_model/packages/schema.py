"""Pydantic models for Frictionless research package descriptors."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ResourceSchema(BaseModel):
    """A tabular data resource within the package."""

    name: str
    path: str
    schema_: dict[str, Any] | None = Field(None, alias="schema")
    model_config = {"populate_by_name": True}


class FigureRef(BaseModel):
    """A static figure (image) included in the package."""

    name: str
    path: str
    caption: str


class CodeExcerpt(BaseModel):
    """An extracted code snippet with source provenance."""

    name: str
    path: str
    source: str
    lines: tuple[int, int]
    github_permalink: str = ""


class VegaLiteSpec(BaseModel):
    """A Vega-Lite visualization specification."""

    name: str
    path: str
    caption: str | None = None


class ProvenanceInput(BaseModel):
    """An input file tracked for freshness via SHA-256."""

    path: str
    sha256: str


class Provenance(BaseModel):
    """Execution provenance for a research package."""

    workflow: str
    config: str
    last_run: str
    git_commit: str
    repository: str
    inputs: list[ProvenanceInput]
    scripts: list[str]


class ResearchExtension(BaseModel):
    """Custom extension block within the Frictionless descriptor."""

    target_route: str | None = None
    cells: str
    figures: list[FigureRef] = Field(default_factory=list)
    vegalite_specs: list[VegaLiteSpec] = Field(default_factory=list)
    code_excerpts: list[CodeExcerpt] = Field(default_factory=list)
    provenance: Provenance


class ResearchPackageDescriptor(BaseModel):
    """A Frictionless data package with science research extensions."""

    name: str
    title: str
    profile: Literal["science-research-package"]
    version: str
    resources: list[ResourceSchema]
    research: ResearchExtension


class AccessException(BaseModel):
    """Structured Branch-B decision for an unverified-but-consumable external dataset."""

    mode: Literal["", "scope-reduced", "expanded-to-acquire", "substituted"] = ""
    decision_date: str = ""
    followup_task: str = ""
    superseded_by_dataset: str = ""
    rationale: str = ""


class AccessBlock(BaseModel):
    """External dataset access verification gate state."""

    level: Literal["public", "registration", "controlled", "commercial", "mixed"]
    availability: Literal["available", "embargoed", "withdrawn"] = "available"
    available_after: str = ""
    verified: bool
    verification_method: Literal["", "retrieved", "credential-confirmed"] = ""
    last_reviewed: str = ""
    verified_by: str = ""
    source_url: str = ""
    credentials_required: str = ""
    exception: AccessException = Field(default_factory=AccessException)

    @model_validator(mode="after")
    def _validate_availability(self) -> "AccessBlock":
        if self.available_after and self.availability != "embargoed":
            raise ValueError("available_after may only be set when availability == 'embargoed'")
        return self


class DerivationBlock(BaseModel):
    """Derived dataset provenance pointing at the producing workflow-run."""

    workflow: str
    workflow_run: str
    git_commit: str
    config_snapshot: str
    produced_at: str
    inputs: list[str] = Field(default_factory=list)

    @field_validator("workflow")
    @classmethod
    def _wf_id(cls, v: str) -> str:
        if not v.startswith("workflow:"):
            raise ValueError("workflow must be a workflow:<slug> entity reference")
        return v

    @field_validator("workflow_run")
    @classmethod
    def _wfrun_id(cls, v: str) -> str:
        if not v.startswith("workflow-run:"):
            raise ValueError("workflow_run must be a workflow-run:<slug> entity reference")
        return v

    @field_validator("inputs")
    @classmethod
    def _input_ids(cls, v: list[str]) -> list[str]:
        for item in v:
            if not item.startswith("dataset:"):
                raise ValueError(f"inputs must be dataset:<slug> entity references; got {item!r}")
        return v


class MemberOfDerivationBlock(BaseModel):
    """Reference-collection member promotion derivation (RCM-D5).

    A promoted member declares `derivation.kind: member_of` with a
    `parent_dataset` entity reference and a `member_key` identifying the
    specific row within that collection. No workflow provenance is expected
    (the promotion is a structural declaration, not a compute step).
    """

    kind: Literal["member_of"]
    parent_dataset: str
    member_key: str

    @field_validator("parent_dataset")
    @classmethod
    def _parent_id(cls, v: str) -> str:
        if not v.startswith("dataset:"):
            raise ValueError("parent_dataset must be a dataset:<slug> entity reference")
        return v


# Backward-compatible alias kept for callers that imported WorkflowDerivationBlock.
WorkflowDerivationBlock = DerivationBlock
