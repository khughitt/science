"""Pydantic v2 schema models for DAG edges YAML files with fail-fast validators."""

from __future__ import annotations

import warnings
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class SchemaError(ValueError):
    """Raised when a DAG edges YAML file violates a structural invariant."""


class EdgeStatus(str, Enum):
    supported = "supported"
    tentative = "tentative"
    structural = "structural"
    unknown = "unknown"
    eliminated = "eliminated"


class Identification(str, Enum):
    interventional = "interventional"
    longitudinal = "longitudinal"
    observational = "observational"
    structural = "structural"
    none = "none"


# Kind tags that identify the type of a reference entry.
REF_KINDS: frozenset[str] = frozenset(
    {
        "task",
        "interpretation",
        "discussion",
        "proposition",
        "paper",
        "doi",
        "accession",
        "dataset",
    }
)


class RefEntry(BaseModel):
    """A single reference entry.

    Exactly one of REF_KINDS must appear as a key **with a non-null value**.
    All other keys (e.g. ``author_year``, ``notes``) are kept as-is via
    ``extra="allow"``.

    ``doi: null`` (and any other ``kind: null``) is treated as **no kind tag
    present** — such an entry is a dishonest citation and is rejected.
    Projects migrating from the legacy pattern should replace ``doi: null``
    with a concrete ``paper: <citekey>`` ref.
    """

    model_config = {"extra": "allow"}

    description: str

    @model_validator(mode="after")
    def _exactly_one_kind(self) -> "RefEntry":
        extra: dict = self.__pydantic_extra__ or {}
        found = [k for k, v in extra.items() if k in REF_KINDS and v is not None]
        if len(found) != 1:
            raise SchemaError(
                f"ref entry must have exactly one non-null kind tag from "
                f"{sorted(REF_KINDS)}; got {found!r}"
            )
        return self


class PosteriorBlock(BaseModel):
    """Optional posterior-estimate block attached to an edge."""

    model_config = {"extra": "allow"}

    beta: float | None = None
    hdi_low: float | None = None
    hdi_high: float | None = None
    prob_sign: float | None = None
    fit_task: str | None = None
    datasets: int | None = None
    model: str | None = None
    notes: str | None = None
    hr: float | None = None
    hr_range: list[float] | None = None
    adjusted_for: list[str] | None = None
    # Permissive: list of partial posterior dicts; not validated deeply in v1.
    variants: list[dict] | None = None

    @model_validator(mode="after")
    def _hdi_requires_beta(self) -> "PosteriorBlock":
        if (self.hdi_low is not None or self.hdi_high is not None) and self.beta is None:
            raise SchemaError("posterior HDI (hdi_low/hdi_high) provided without beta")
        return self


class EdgeRecord(BaseModel):
    """One edge in a DAG edges YAML file."""

    model_config = {"extra": "allow"}

    id: int
    source: str
    target: str
    edge_status: EdgeStatus = EdgeStatus.unknown
    description: str

    # Optional labelling / style fields present in mm30 edges.yaml files.
    source_label: str | None = None
    target_label: str | None = None
    original_label: str | None = None
    edge_style: str | None = None
    relation: str | None = None
    caveats: list[str] = Field(default_factory=list)

    # Reference lists.
    data_support: list[RefEntry] = Field(default_factory=list)
    lit_support: list[RefEntry] = Field(default_factory=list)
    eliminated_by: list[RefEntry] | None = None

    # Posterior block.
    posterior: PosteriorBlock | None = None

    # identification has a sentinel default so we can emit a DeprecationWarning
    # when it is absent from the source file (to surface implicit cases during
    # migrations).  The public value is always Identification.none when omitted.
    identification: Identification = Field(default=Identification.none)

    @field_validator("identification", mode="before")
    @classmethod
    def _warn_if_identification_missing(cls, v: object) -> object:
        # Pydantic calls field_validator even for defaults when the field is
        # absent; when the raw value equals the default sentinel string we can't
        # easily distinguish "explicit none" from "missing".  Instead we rely on
        # the model_validator below for the missing-key case.
        return v

    @model_validator(mode="before")
    @classmethod
    def _emit_identification_deprecation(cls, values: dict) -> dict:
        if "identification" not in values:
            warnings.warn(
                "Edge is missing 'identification' field; defaulting to Identification.none. "
                "Set 'identification: none' explicitly to suppress this warning.",
                DeprecationWarning,
                stacklevel=2,
            )
        return values

    @model_validator(mode="after")
    def _eliminated_requires_provenance(self) -> "EdgeRecord":
        is_eliminated = self.edge_status == EdgeStatus.eliminated
        has_provenance = bool(self.eliminated_by)
        if is_eliminated and not has_provenance:
            raise SchemaError(
                "edge_status=eliminated requires a non-empty eliminated_by provenance list"
            )
        if not is_eliminated and self.eliminated_by:
            raise SchemaError(
                "eliminated_by is only valid when edge_status=eliminated; "
                f"got edge_status={self.edge_status.value!r}"
            )
        return self


class EdgesYamlFile(BaseModel):
    """Top-level structure of a ``<slug>.edges.yaml`` file."""

    model_config = {"extra": "allow"}

    dag: str
    source_dot: str | None = None
    edges: list[EdgeRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_source_target_pairs(self) -> "EdgesYamlFile":
        seen: set[tuple[str, str]] = set()
        for e in self.edges:
            key = (e.source, e.target)
            if key in seen:
                raise SchemaError(
                    f"duplicate edge (source={e.source!r}, target={e.target!r}) in DAG {self.dag!r}"
                )
            seen.add(key)
        return self
