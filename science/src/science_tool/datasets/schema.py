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

    @model_validator(mode="after")
    def _reference_checks(self) -> "TableSchema":
        names = {f.name for f in self.fields}
        types = {f.name: f.type for f in self.fields}

        for key in (_as_list(self.primaryKey) if self.primaryKey is not None else []):
            if key not in names:
                raise ValueError(f"primaryKey references unknown field {key!r}")
        for group in (self.uniqueKeys or []):
            for key in group:
                if key not in names:
                    raise ValueError(f"uniqueKeys references unknown field {key!r}")
        for fk in self.foreignKeys:
            for key in _as_list(fk.fields):
                if key not in names:
                    raise ValueError(f"foreignKey references unknown local field {key!r}")
        for a, b in self.qa.exclusive_flags:
            for key in (a, b):
                if key not in names:
                    raise ValueError(f"qa.exclusive_flags references unknown field {key!r}")
            for key in (a, b):
                if types[key] not in FLAG_TYPES:
                    raise ValueError(
                        f"qa.exclusive_flags field {key!r} must be boolean/integer, "
                        f"got {types[key]!r}"
                    )
        return self


class ResourceDescriptor(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    # Explicitly modelled so the marker is documented in the emitted profile and an
    # invalid value fails rather than passing silently via extra="allow".
    profile: Literal["science-data-resource/v1"] | None = Field(default=None, alias="$schema")
    name: str
    path: str                                # required in Spec 1 (no inline-data support yet)
    schema_: TableSchema | None = Field(default=None, alias="schema")


def package_consistency_issues(descriptors: list[ResourceDescriptor]) -> list[str]:
    """Cross-resource checks needing whole-package context (foreign-key resolution).

    Returns human-readable issue strings (empty list = consistent). Within-descriptor
    invariants are enforced at parse time by the model validators, not here.
    """
    issues: list[str] = []
    seen: set[str] = set()
    for d in descriptors:
        if d.name in seen:
            issues.append(f"duplicate resource name {d.name!r}")
        seen.add(d.name)
    by_name: dict[str, ResourceDescriptor] = {d.name: d for d in descriptors}
    for d in descriptors:
        if d.schema_ is None:
            continue
        for fk in d.schema_.foreignKeys:
            ref = fk.reference
            target = d if ref.resource == "" else by_name.get(ref.resource)
            if target is None:
                issues.append(f"{d.name}: foreignKey references unknown resource {ref.resource!r}")
                continue
            if target.schema_ is None:
                issues.append(
                    f"{d.name}: foreignKey target resource {ref.resource!r} has no schema"
                )
                continue
            target_names = {f.name for f in target.schema_.fields}
            for key in _as_list(ref.fields):
                if key not in target_names:
                    issues.append(
                        f"{d.name}: foreignKey reference field {key!r} not in resource "
                        f"{(ref.resource or d.name)!r}"
                    )
    return issues


def emit_profile() -> str:
    """Deterministic JSON Schema for the Data Resource descriptor (the $schema target)."""
    schema = ResourceDescriptor.model_json_schema(by_alias=True)
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_profile() -> Path:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(emit_profile(), encoding="utf-8")
    return PROFILE_PATH


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="science Data Resource profile tools")
    parser.add_argument(
        "--emit", action="store_true", help="(re)write the committed JSON Schema profile"
    )
    args = parser.parse_args()
    if args.emit:
        print(f"wrote {write_profile()}")
    else:
        parser.error("nothing to do; pass --emit")
