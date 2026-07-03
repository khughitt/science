"""Pydantic models for Frictionless research package descriptors."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _validate_dataset_ref(value: str, field_name: str) -> str:
    if not value.startswith("dataset:"):
        raise ValueError(f"{field_name} must be a dataset:<slug> entity reference")
    return value


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


class AccessReproducibility(BaseModel):
    """Third-party reproducibility controls (Five Safes) for an external dataset.

    Canonical source of truth. The reproducibility *class* is DERIVED from these
    (see science_tool.datasets.semantics.reproducibility_class_for), never stored.
    """

    obtainability: Literal[
        "public",
        "registration",
        "self-service-dua",
        "approved-researcher",
        "approved-project",
        "named-collaboration",
        "unavailable",
        "unknown",
    ] = "unknown"
    execution: Literal[
        "local",
        "hosted-workspace",
        "trusted-environment",
        "federated-code-to-data",
        "custodian-run",
        "unknown",
    ] = "unknown"
    extractability: Literal[
        "full-dataset",
        "analysis-dataset",
        "synthetic-dataset",
        "aggregate-unreviewed",
        "aggregate-reviewed",
        "none",
        "unknown",
    ] = "unknown"
    notes: str = ""


class AccessBlock(BaseModel):
    """External dataset access verification gate state."""

    level: Literal["public", "registration", "controlled", "commercial", "mixed"]
    availability: Literal["available", "embargoed", "withdrawn"] = "available"
    available_after: str = ""
    verified: bool
    verification_method: Literal[
        "",
        "retrieved",
        "credential-confirmed",
        "landing-confirmed",
        "metadata-confirmed",
    ] = ""
    last_reviewed: str = ""
    verified_by: str = ""
    source_url: str = ""
    credentials_required: str = ""
    exception: AccessException = Field(default_factory=AccessException)
    reproducibility: AccessReproducibility = Field(default_factory=AccessReproducibility)

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


class WorkflowRecipeDerivationBlock(BaseModel):
    """Commons recipe-level derivation for promoted derived datasets."""

    kind: Literal["workflow"]
    workflow_recipe: str
    inputs: list[str] = Field(default_factory=list)
    recipe_lockfile: str = ""

    @field_validator("workflow_recipe")
    @classmethod
    def _recipe_id(cls, v: str) -> str:
        if not v.startswith("workflow:"):
            raise ValueError("workflow_recipe must be a workflow:<slug> entity reference")
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

    @field_validator("member_key")
    @classmethod
    def _non_empty_member_key(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("member_key must be a non-empty row key")
        return v


class IdentityTransform(BaseModel):
    """Dataset-backed identity transform used for assemblies or molecular IDs."""

    type: Literal["liftover", "symbol_remap", "namespace_map"]
    from_: str = Field(alias="from", min_length=1)
    method: str | None = Field(default=None, min_length=1)
    dataset: str
    model_config = ConfigDict(
        extra="forbid",
        validate_by_alias=True,
        validate_by_name=False,
        serialize_by_alias=True,
    )

    @field_validator("dataset")
    @classmethod
    def _dataset_id(cls, value: str) -> str:
        return _validate_dataset_ref(value, "dataset")


class ProxySourceAssembly(BaseModel):
    """Minimal assembly descriptor accepted inside an identity proxy source."""

    label: str | None = Field(default=None, min_length=1)
    seqcol_digest: str | None = Field(default=None, min_length=1)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_single_identifier(self) -> "ProxySourceAssembly":
        identifiers = [value for value in (self.label, self.seqcol_digest) if value is not None]
        if len(identifiers) != 1:
            raise ValueError("proxy source assembly requires exactly one of label or seqcol_digest")
        return self


class ProxySource(BaseModel):
    """A source dataset and assembly descriptor used by an identity proxy."""

    dataset: str
    assembly: Literal["inherit"] | ProxySourceAssembly
    model_config = ConfigDict(extra="forbid")

    @field_validator("dataset")
    @classmethod
    def _dataset_id(cls, value: str) -> str:
        return _validate_dataset_ref(value, "sources[].dataset")


class IdentityProxy(BaseModel):
    """Assembly identity proxy derived through another dataset-backed source."""

    type: Literal["cytoband_proxy", "interval_overlap_proxy", "symbol_space_proxy"]
    via: str
    sources: list[ProxySource] = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")

    @field_validator("via")
    @classmethod
    def _via_dataset_id(cls, value: str) -> str:
        return _validate_dataset_ref(value, "via")


class AssemblyIdentity(BaseModel):
    """Reference assembly identity and optional proxy/transform provenance."""

    label: str | None = Field(default=None, min_length=1)
    seqcol_digest: str | None = Field(default=None, min_length=1)
    registry: str
    resolution_status: Literal["resolved", "declared_unresolved"]
    proxy: IdentityProxy | None = None
    transform: IdentityTransform | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("registry")
    @classmethod
    def _registry_dataset_id(cls, value: str) -> str:
        return _validate_dataset_ref(value, "registry")

    @model_validator(mode="after")
    def _validate_resolution(self) -> "AssemblyIdentity":
        if self.resolution_status == "resolved" and (self.seqcol_digest is None or self.seqcol_digest == "UNKNOWN"):
            raise ValueError("resolved assembly requires seqcol_digest other than UNKNOWN")
        if self.proxy is not None and self.resolution_status != "declared_unresolved":
            raise ValueError("assembly proxy requires resolution_status declared_unresolved")
        return self


class MolecularTierIdentity(BaseModel):
    """Molecular identifier tier metadata and optional transform provenance."""

    namespace: str = Field(min_length=1)
    canonical: bool | None = None
    registry: str | None = None
    resolution_status: Literal["resolved", "declared_unresolved"] | None = None
    transform: IdentityTransform | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("registry")
    @classmethod
    def _registry_dataset_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_dataset_ref(value, "registry")


class IdentityContext(BaseModel):
    """Biological identity context block for dataset-like entities."""

    taxon: int = Field(strict=True, ge=1)
    molecular_ids: dict[str, MolecularTierIdentity] = Field(default_factory=dict)
    assembly: AssemblyIdentity | None = None
    model_config = ConfigDict(extra="allow")


class WorkflowOutputIdentityInheritSelector(BaseModel):
    """Explicit workflow output inheritance source selector."""

    from_: str = Field(alias="from", min_length=1)
    model_config = ConfigDict(
        extra="forbid",
        validate_by_alias=True,
        validate_by_name=False,
        serialize_by_alias=True,
    )

    @field_validator("from_")
    @classmethod
    def _from_dataset_id(cls, value: str) -> str:
        return _validate_dataset_ref(value, "inherit.from")


class WorkflowOutputIdentityInheritFrom(BaseModel):
    """Explicit workflow output inheritance declaration."""

    inherit: WorkflowOutputIdentityInheritSelector
    model_config = ConfigDict(extra="forbid")


class WorkflowOutputAssemblyIdentity(BaseModel):
    """Workflow output assembly identity contract.

    Literal assembly declarations use the same fields as ``AssemblyIdentity``.
    Transform-only contracts may omit registry/resolution fields because P3.2
    resolves them from inputs when materializing the derived entity.
    """

    label: str | None = Field(default=None, min_length=1)
    seqcol_digest: str | None = Field(default=None, min_length=1)
    registry: str | None = None
    resolution_status: Literal["resolved", "declared_unresolved"] | None = None
    proxy: IdentityProxy | None = None
    transform: IdentityTransform | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("registry")
    @classmethod
    def _registry_dataset_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_dataset_ref(value, "registry")

    @model_validator(mode="after")
    def _validate_resolution(self) -> "WorkflowOutputAssemblyIdentity":
        if self.resolution_status == "resolved" and (self.seqcol_digest is None or self.seqcol_digest == "UNKNOWN"):
            raise ValueError("resolved assembly requires seqcol_digest other than UNKNOWN")
        if self.proxy is not None and self.resolution_status != "declared_unresolved":
            raise ValueError("assembly proxy requires resolution_status declared_unresolved")
        return self


WorkflowOutputTaxonIdentity = (
    Annotated[int, Field(strict=True, ge=1)] | Literal["inherit"] | WorkflowOutputIdentityInheritFrom
)
WorkflowOutputAssemblyIdentityValue = (
    Literal["inherit"] | WorkflowOutputIdentityInheritFrom | WorkflowOutputAssemblyIdentity
)
WorkflowOutputMolecularTierIdentity = Literal["inherit"] | WorkflowOutputIdentityInheritFrom | MolecularTierIdentity


class WorkflowOutputIdentity(BaseModel):
    """Identity contract declared on a workflow ``outputs[]`` entry."""

    taxon: WorkflowOutputTaxonIdentity | None = None
    assembly: WorkflowOutputAssemblyIdentityValue | None = None
    molecular_ids: dict[str, WorkflowOutputMolecularTierIdentity] = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")


class DatasetUsage(BaseModel):
    """Forward-provenance: a consumer's declared use of one dataset (Pillar A/B).

    Co-owned by Pillar A (which uses the `{upstream, training}` projection for the
    external-derived independence contract, A-D3) and Pillar B (which adds the
    materialization, role semantics, and auto-independence). A1 defines the full
    shape so B1 does not migrate a partial field.
    """

    ref: str
    role: Literal["analyzed", "set_definition_source", "validation_source", "cited", "upstream", "training"]
    overlap: Literal["full", "partial", "unknown"] = "unknown"

    @field_validator("ref")
    @classmethod
    def _ref_id(cls, v: str) -> str:
        if not v.startswith("dataset:"):
            raise ValueError("dataset_usage.ref must be a dataset:<slug> entity reference")
        return v


_BENCHMARK_TASK_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class GroundTruth(BaseModel):
    """What a benchmark task treats as ground truth."""

    type: str = ""
    description: str = ""


class BenchmarkTask(BaseModel):
    """A locally named evaluation task inside a dataset benchmark block.

    The required fields to make a task an actual *test* are ``prediction_target``
    (what the model predicts) and ``held_out_unit`` (what is withheld). v1 keeps
    them as free-text; vocabularies promote to enums in a later phase.
    """

    id: str
    task_type: str = ""
    prediction_target: str = ""
    held_out_unit: str = ""
    metric: str = ""
    baseline: str = ""
    ground_truth: GroundTruth | None = None
    interpretation_limits: list[str] = Field(default_factory=list)
    intervention: str = ""
    timepoints: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not 2 <= len(value) <= 64 or not _BENCHMARK_TASK_ID_RE.fullmatch(value):
            raise ValueError("tasks.id must be lowercase kebab-case, 2-64 characters")
        return value


class BenchmarkBlock(BaseModel):
    """Benchmark-capable dataset metadata.

    V1 keeps vocabularies as free-text strings. Later phases can promote stable
    terms to enums once seed records show which facets actually recur.
    """

    domains: list[str] = Field(default_factory=list)
    modalities: list[str] = Field(default_factory=list)
    signal_types: list[str] = Field(default_factory=list)
    benchmark_kinds: list[str] = Field(default_factory=list)
    source_datasets: list[str] = Field(default_factory=list)
    related_beliefs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    tasks: list[BenchmarkTask] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_task_ids(self) -> "BenchmarkBlock":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for task in self.tasks:
            if task.id in seen:
                duplicates.add(task.id)
            seen.add(task.id)
        if duplicates:
            ordered = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate benchmark task id: {ordered}")
        return self
