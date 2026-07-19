"""Fail-closed YAML binding schema for numeric-provenance entries.

Pure module -- no disk I/O. `validate_entry` is the single public entry point:
it takes a raw (already YAML-parsed) entry mapping and returns either a
`ParsedEntry` on success or a `BindingError` describing why the entry was
rejected. Every rejection path is deliberate: an entry that does not
unambiguously identify one locator shape, or that pairs `tolerance` with an
`opaque` locator, or that mismatches its declared artifact extension, is
refused rather than guessed at.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class PointerLocator(BaseModel):
    """Locates a value via a JSON Pointer into a `.json` artifact."""

    model_config = ConfigDict(extra="forbid")

    pointer: str = Field(min_length=1)


class ColumnLocator(BaseModel):
    """Locates a value via a column (optionally filtered by `where`) in a `.feather` artifact."""

    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1)
    where: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _where_non_empty_if_present(self) -> "ColumnLocator":
        if self.where is not None and len(self.where) == 0:
            raise ValueError("where must be a non-empty mapping when present")
        return self


class OpaqueLocator(BaseModel):
    """Locates a value by free-text description (e.g. 'read off panel B'). Any artifact extension."""

    model_config = ConfigDict(extra="forbid")

    opaque: str = Field(min_length=1)


# The locator's type dictates the extension its artifact must carry. A locator
# type absent from this map (currently just OpaqueLocator) is unconstrained --
# opaque claims may point at any artifact extension.
_REQUIRED_EXTENSION_BY_LOCATOR: dict[type[BaseModel], str] = {
    PointerLocator: ".json",
    ColumnLocator: ".feather",
}

_LOCATOR_MODELS: tuple[type[BaseModel], ...] = (PointerLocator, ColumnLocator, OpaqueLocator)


class _EntryModel(BaseModel):
    """Entry-level shape: only `artifact`, `locator`, and optional `tolerance` are legal."""

    model_config = ConfigDict(extra="forbid")

    artifact: str = Field(min_length=1)
    locator: dict[str, Any]
    tolerance: Any = None


@dataclass(frozen=True)
class ParsedEntry:
    artifact: str
    locator: PointerLocator | ColumnLocator | OpaqueLocator
    tolerance: Decimal | None


@dataclass(frozen=True)
class BindingError:
    id: str | None
    line: int | None
    message: str


def validate_entry(id: str, raw: Any, artifact_ext: str) -> ParsedEntry | BindingError:
    """Validate one raw binding entry. Fail-closed: any ambiguity or malformation rejects.

    On success, returns a `ParsedEntry` holding the resolved locator (exactly one of
    `PointerLocator`, `ColumnLocator`, `OpaqueLocator`) and the parsed `tolerance`
    (`None` if absent). On any failure -- non-mapping entry, schema violation, ambiguous
    or absent locator shape, artifact-extension mismatch, or an invalid `tolerance` --
    returns a `BindingError` describing the first problem found.
    """
    if not isinstance(raw, Mapping):
        return BindingError(id, None, "entry must be a mapping")

    try:
        entry = _EntryModel.model_validate(raw)
    except ValidationError as exc:
        return BindingError(id, None, str(exc))

    if not isinstance(entry.locator, Mapping):
        return BindingError(id, None, "locator must be a mapping")

    matches: list[BaseModel] = []
    for model_cls in _LOCATOR_MODELS:
        try:
            matches.append(model_cls.model_validate(entry.locator))
        except ValidationError:
            continue

    if len(matches) != 1:
        return BindingError(
            id, None, "locator must match exactly one of {pointer, column, opaque} with a non-empty value"
        )

    locator = matches[0]

    required_ext = _REQUIRED_EXTENSION_BY_LOCATOR.get(type(locator))
    if required_ext is not None and artifact_ext != required_ext:
        return BindingError(
            id, None, f"{type(locator).__name__} requires artifact extension {required_ext!r}, got {artifact_ext!r}"
        )

    tolerance: Decimal | None = None
    if entry.tolerance is not None:
        if isinstance(locator, OpaqueLocator):
            return BindingError(id, None, "tolerance is forbidden together with an opaque locator")
        try:
            tolerance = Decimal(str(entry.tolerance))
        except InvalidOperation:
            return BindingError(id, None, f"tolerance is not a valid decimal number: {entry.tolerance!r}")
        if not tolerance.is_finite():
            return BindingError(id, None, "tolerance must be finite")
        if not tolerance > 0:
            return BindingError(id, None, "tolerance must be > 0")

    return ParsedEntry(artifact=entry.artifact, locator=locator, tolerance=tolerance)
