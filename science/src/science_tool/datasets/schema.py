"""Pydantic v2 models for the science Data Resource profile (Spec 1).

Native Frictionless Table Schema (invariants) + a small `qa:` extension
(distribution checks). Targets Data Package Standard v2 while accepting v1
compatibility forms for primaryKey and foreignKeys. These models are the single
source of truth; the published JSON Schema profile is emitted from them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROFILE_MARKER = "science-data-resource/v1"
PROFILE_PATH = Path(__file__).parent / "profiles" / "science-data-resource-v1.json"

FrictionlessType = Literal[
    "string", "number", "integer", "boolean", "object", "array", "list",
    "datetime", "date", "time", "year", "yearmonth", "duration",
    "geopoint", "geojson", "any",
]

NUMERIC_TYPES = {"integer", "number"}
TEMPORAL_TYPES = {"date", "datetime", "time", "year", "yearmonth", "duration"}
QA_STAT_TYPES = {"integer", "number", "boolean"}
FLAG_TYPES = {"boolean", "integer"}


def _as_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


class MissingValue(BaseModel):
    """A null sentinel: a bare string, or a labelled object (DP v2)."""

    model_config = ConfigDict(extra="allow")
    value: str
    label: str = ""


class FieldConstraints(BaseModel):
    model_config = ConfigDict(extra="allow")
    required: bool = False
    unique: bool = False
    minimum: str | int | float | None = None
    maximum: str | int | float | None = None
    exclusiveMinimum: str | int | float | None = None
    exclusiveMaximum: str | int | float | None = None
    enum: list[object] | None = None
    pattern: str | None = None

    @model_validator(mode="after")
    def _enum_non_empty(self) -> "FieldConstraints":
        if self.enum is not None and len(self.enum) == 0:
            raise ValueError("enum, when present, must be non-empty")
        return self


class FieldQA(BaseModel):
    """The distribution-severity extension carried per field (closed namespace)."""

    model_config = ConfigDict(extra="forbid")
    low_variance: bool = False
    zero_fraction: bool = False


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    type: FrictionlessType = "any"          # DP v2: omitted type ⇒ "any" (NOT "string")
    constraints: FieldConstraints = Field(default_factory=FieldConstraints)
    # Field-level missingValues override (DP v2) — accepted/round-tripped, but not
    # consumed until a later spec; table-level missingValues remains the primary path.
    missingValues: list[str | MissingValue] | None = None
    qa: FieldQA = Field(default_factory=FieldQA)

    @model_validator(mode="after")
    def _semantic_applicability(self) -> "FieldSpec":
        has_bound = any(
            getattr(self.constraints, b) is not None
            for b in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
        )
        if has_bound and self.type not in (NUMERIC_TYPES | TEMPORAL_TYPES):
            raise ValueError(
                f"field {self.name!r}: bounds require a numeric or temporal type, "
                f"got {self.type!r}"
            )
        if (self.qa.low_variance or self.qa.zero_fraction) and self.type not in QA_STAT_TYPES:
            raise ValueError(
                f"field {self.name!r}: qa.low_variance/zero_fraction require an "
                f"integer/number/boolean type, got {self.type!r}"
            )
        return self


class ForeignKeyReference(BaseModel):
    model_config = ConfigDict(extra="allow")
    resource: str = ""                       # "" (or absent) = self-reference
    fields: str | list[str]


class ForeignKey(BaseModel):
    model_config = ConfigDict(extra="allow")
    fields: str | list[str]
    reference: ForeignKeyReference

    @model_validator(mode="after")
    def _cardinality(self) -> "ForeignKey":
        if len(_as_list(self.fields)) != len(_as_list(self.reference.fields)):
            raise ValueError(
                "foreignKey cardinality mismatch between fields and reference.fields"
            )
        return self


class TableQA(BaseModel):
    """The distribution-severity extension carried at table level (closed namespace)."""

    model_config = ConfigDict(extra="forbid")
    exclusive_flags: list[tuple[str, str]] = Field(default_factory=list)


class TableSchema(BaseModel):
    model_config = ConfigDict(extra="allow")
    fields: list[FieldSpec]
    primaryKey: str | list[str] | None = None
    # `None` = absent. When present, DP v2 requires uniqueKeys non-empty with non-empty
    # inner groups; the validator distinguishes absent from explicit `[]`.
    uniqueKeys: list[list[str]] | None = None
    foreignKeys: list[ForeignKey] = Field(default_factory=list)
    missingValues: list[str | MissingValue] = Field(default_factory=lambda: [""])
    qa: TableQA = Field(default_factory=TableQA)

    @model_validator(mode="after")
    def _unique_and_missing(self) -> "TableSchema":
        field_names = [f.name for f in self.fields]
        dupes = sorted({n for n in field_names if field_names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate field name(s): {dupes}")
        if self.uniqueKeys is not None:
            if not self.uniqueKeys:
                raise ValueError("uniqueKeys, when present, must be non-empty")
            if any(not group for group in self.uniqueKeys):
                raise ValueError("each uniqueKeys group must be non-empty")
        # Sentinel *values* are the key and must be unique; labels are descriptive
        # and intentionally NOT required to be unique.
        seen: set[str] = set()
        for mv in self.missingValues:
            key = mv if isinstance(mv, str) else mv.value
            if key in seen:
                raise ValueError(f"missingValues entries must be unique; duplicate {key!r}")
            seen.add(key)
        return self
