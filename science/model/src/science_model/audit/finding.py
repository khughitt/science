"""The shared emitted payload (design §1)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
)

from science_model.audit.evidence import MAX_EVIDENCE_ENTRIES, Evidence
from science_model.audit.subjects import FindingSubject

Severity = Literal["error", "warn", "info"]

_SEVERITY_ALIASES = {"warning": "warn", "warn": "warn", "error": "error", "info": "info"}


def _freeze_qualifiers(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return a read-only view over a private copy of a qualifier mapping."""
    return MappingProxyType(dict(value))


QualifierMap = Annotated[
    Mapping[str, object],
    AfterValidator(_freeze_qualifiers),
    PlainSerializer(dict, return_type=dict, when_used="always"),
]
"""A frozen, JSON-serializable qualifier mapping."""


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
    evidence: list[Evidence] = Field(default_factory=list, max_length=MAX_EVIDENCE_ENTRIES)

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize(cls, value: object) -> object:
        return normalize_severity(value) if isinstance(value, str) else value
