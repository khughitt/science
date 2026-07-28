"""The shared emitted payload (design §1)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal, cast

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
)

from science_model.audit.evidence import MAX_EVIDENCE_ENTRIES, Evidence
from science_model.audit.subjects import FindingSubject, normalize_utf8_nfc

Severity = Literal["error", "warn", "info"]

_SEVERITY_ALIASES = {"warning": "warn", "warn": "warn", "error": "error", "info": "info"}


class JsonValueError(ValueError):
    """A value is outside the deterministic JSON data model."""


def freeze_json_value(value: object) -> object:
    """Validate and recursively freeze one deterministic JSON value."""
    return _freeze_json_value(value, set())


def _freeze_json_value(value: object, active: set[int]) -> object:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise JsonValueError(
                "JSON numbers must be finite; NaN and infinities are forbidden"
            )
        return value
    if isinstance(value, Mapping):
        marker = id(value)
        if marker in active:
            raise JsonValueError("JSON containers must not be cyclic")
        active.add(marker)
        try:
            frozen: dict[str, object] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise JsonValueError(
                        f"JSON object keys must be strings, got {type(key).__name__}"
                    )
                frozen[key] = _freeze_json_value(item, active)
            return MappingProxyType(frozen)
        finally:
            active.remove(marker)
    if type(value) in (list, tuple):
        sequence = cast(list[object] | tuple[object, ...], value)
        marker = id(value)
        if marker in active:
            raise JsonValueError("JSON containers must not be cyclic")
        active.add(marker)
        try:
            return tuple(_freeze_json_value(item, active) for item in sequence)
        finally:
            active.remove(marker)
    raise JsonValueError(
        f"value of type {type(value).__name__} is not in the deterministic JSON domain"
    )


def _freeze_qualifiers(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return a recursively immutable copy of a qualifier mapping."""
    frozen = freeze_json_value(value)
    if not isinstance(frozen, Mapping):
        raise JsonValueError("qualifiers must be a JSON object")
    return frozen


def thaw_json_value(value: object) -> object:
    """Return a detached JSON-shaped copy of recursively frozen data.

    Strict schema validation must inspect the wire representation, where arrays are
    lists. Feeding the immutable internal tuples to a schema declaring ``list[T]``
    makes one valid payload fail merely because it has already crossed a model
    boundary.
    """
    if isinstance(value, Mapping):
        return {
            key: thaw_json_value(item) for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [thaw_json_value(item) for item in value]
    return value


def _serialize_qualifiers(value: Mapping[str, object]) -> dict[str, object]:
    return {key: thaw_json_value(item) for key, item in value.items()}


QualifierMap = Annotated[
    Mapping[str, object],
    AfterValidator(_freeze_qualifiers),
    PlainSerializer(_serialize_qualifiers, return_type=dict, when_used="always"),
]
"""A frozen, JSON-serializable qualifier mapping."""


def _tuple_input(value: object) -> object:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return value


EvidenceArray = Annotated[
    tuple[Evidence, ...],
    BeforeValidator(_tuple_input),
]


def reject_nul(value: str) -> str:
    """Reject the separator used by occurrence and review hash encodings."""
    if "\0" in value:
        raise ValueError(
            f"{value!r} contains a NUL, which separates the fields of the occurrence "
            "and review hashes; a NUL inside a value would let two different tuples "
            "produce one key"
        )
    return value


HashComponent = Annotated[str, AfterValidator(reject_nul)]
"""A string safe for use as a component of a NUL-delimited hash."""


def normalize_severity(raw: str) -> str:
    """Normalize the accepted severity spelling to its wire value."""
    try:
        return _SEVERITY_ALIASES[raw]
    except KeyError:
        raise ValueError(f"unknown severity {raw!r}") from None


class AuditFinding(BaseModel):
    """What a producer says for one observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    subject: FindingSubject
    severity: Severity
    qualifiers: QualifierMap = Field(default_factory=dict, validate_default=True)
    message: str
    evidence: EvidenceArray = Field(
        default=(),
        max_length=MAX_EVIDENCE_ENTRIES,
        validate_default=True,
    )

    @field_validator("rule_id")
    @classmethod
    def _normalize_rule_id(cls, value: str) -> str:
        return normalize_utf8_nfc(value)

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize(cls, value: object) -> object:
        return normalize_severity(value) if isinstance(value, str) else value
