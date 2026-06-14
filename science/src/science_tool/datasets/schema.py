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
