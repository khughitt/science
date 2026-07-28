"""The public audit output contract (design §11).

Findings are ENVELOPED with their producer. A bare `AuditFinding` cannot populate an
occurrence's required `producer_id`, and rule ownership cannot supply it either —
several producers must be able to emit one rule, which is the premise of
cross-producer dedup.

`ingestion_ref`, `generated_at`, and producer IDs are report-level actor claims.
Trusted ingestion compares them exactly with independent supervisor attestation
before any occurrence or idempotency key is constructed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_serializer,
    model_validator,
)

from science_model.audit.finding import (
    AuditFinding,
    HashComponent,
    freeze_json_value,
    thaw_json_value,
)

REPORT_SCHEMA_VERSION = 2


def _nonblank_producer_id(value: str) -> str:
    if not value.strip():
        raise ValueError("producer id must not be blank")
    return value


ProducerId = Annotated[
    HashComponent,
    AfterValidator(_nonblank_producer_id),
]


def _tuple_input(value: object) -> object:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return value


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(value))


def _freeze_json_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    frozen = freeze_json_value(value)
    if not isinstance(frozen, Mapping):
        raise ValueError("expected a JSON object")
    return frozen


def _serialize_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {key: thaw_json_value(item) for key, item in value.items()}


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReportedFinding(_Base):
    #: `HashComponent`: ingestion copies this straight onto an `Occurrence`, where it
    #: is joined with `\0` into the idempotency key. Refusing here rather than there
    #: keeps the failure a report-validation error the caller asked for, instead of a
    #: `ValidationError` surfacing from inside the write path.
    producer_id: ProducerId
    finding: AuditFinding


class AcceptedFinding(_Base):
    producer_id: ProducerId
    finding: AuditFinding
    acceptance_key: str = Field(pattern=r"^[0-9a-f]{32}$")
    reason: str = Field(min_length=1)


class UnwiredProducer(_Base):
    producer_id: ProducerId
    code: str = Field(min_length=1)
    reason: str | None = None


class ProducerCaveat(_Base):
    producer_id: ProducerId
    code: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _has_meaningful_detail(self) -> "ProducerCaveat":
        if not any(value is not None and value.strip() for value in (self.code, self.reason)):
            raise ValueError("producer caveat requires a nonblank code or reason")
        return self


class ProducerMetrics(BaseModel):
    """Validated against the schema the producer declared at registration (§6).

    `extra="allow"` here and strict validation there: this type is the transport,
    the producer's declared schema is the contract. `science_tool.findings.producers`
    performs that validation; `science_model` cannot, because it does not know the
    registry.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    @model_validator(mode="after")
    def _freeze_extras(self) -> "ProducerMetrics":
        extra = self.__pydantic_extra__ or {}
        frozen = freeze_json_value(extra)
        if not isinstance(frozen, Mapping):
            raise ValueError("metrics extras must be a JSON object")
        object.__setattr__(
            self,
            "__pydantic_extra__",
            frozen,
        )
        return self

    @model_serializer(mode="plain")
    def _serialize(self) -> dict[str, object]:
        return _serialize_mapping(self.__pydantic_extra__ or {})


FrozenSeverityCounts = Annotated[
    Mapping[str, int],
    AfterValidator(_freeze_mapping),
    PlainSerializer(_serialize_mapping, return_type=dict, when_used="always"),
]
FrozenTiming = Annotated[
    Mapping[str, object],
    AfterValidator(_freeze_json_mapping),
    PlainSerializer(_serialize_mapping, return_type=dict, when_used="always"),
]
ReportedArray = Annotated[
    tuple[ReportedFinding, ...],
    BeforeValidator(_tuple_input),
]
AcceptedArray = Annotated[
    tuple[AcceptedFinding, ...],
    BeforeValidator(_tuple_input),
]
UnwiredArray = Annotated[
    tuple[UnwiredProducer, ...],
    BeforeValidator(_tuple_input),
]
ProducerCaveatArray = Annotated[
    tuple[ProducerCaveat, ...],
    BeforeValidator(_tuple_input),
]
ProducerIdArray = Annotated[
    tuple[ProducerId, ...],
    BeforeValidator(_tuple_input),
]
TimingArray = Annotated[
    tuple[FrozenTiming, ...],
    BeforeValidator(_tuple_input),
]
FrozenMetrics = Annotated[
    Mapping[str, ProducerMetrics],
    AfterValidator(_freeze_mapping),
    PlainSerializer(_serialize_mapping, return_type=dict, when_used="always"),
]


class ReportTotals(_Base):
    findings_total: int = Field(ge=0)
    findings_by_severity: FrozenSeverityCounts = Field(
        default_factory=dict,
        validate_default=True,
    )
    accepted_total: int = Field(ge=0)
    unwired_total: int = Field(ge=0)


class ReportMeta(_Base):
    producers_run: ProducerIdArray = Field(default=(), validate_default=True)
    total_duration_seconds: float
    timings: TimingArray = Field(default=(), validate_default=True)

    @field_validator("producers_run")
    @classmethod
    def _unique_producers_run(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("producers_run contains duplicate producer ids")
        return value


class AuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2]
    fingerprint_version: Literal[1]
    #: Actor-claimed `HashComponent`. Trusted ingestion writes the independently
    #: attested equal value, never this field on its own authority.
    ingestion_ref: HashComponent = Field(min_length=1)
    #: Actor-claimed ISO-8601 timestamp, validated here for report shape. Trusted
    #: ingestion requires exact equality with supervisor attestation and turns the
    #: attested value into `observed_at`.
    generated_at: str = Field(min_length=1)
    findings: ReportedArray
    accepted: AcceptedArray = Field(default=(), validate_default=True)
    metrics: FrozenMetrics = Field(default_factory=dict, validate_default=True)
    caveats: ProducerCaveatArray = Field(default=(), validate_default=True)
    unwired: UnwiredArray = Field(default=(), validate_default=True)
    totals: ReportTotals
    meta: ReportMeta

    @field_validator("generated_at")
    @classmethod
    def _iso_8601(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"generated_at must be ISO-8601, got {value!r}: {exc}") from exc
        return value

    @model_validator(mode="after")
    def _validate(self) -> "AuditReport":
        # NOTE: the "at most one finding per (producer_id, finding_id)" rule is NOT
        # enforced here. It cannot be: `finding_id` is a fingerprint over the rule's
        # DECLARED identity qualifiers, and this module does not know the registry.
        # Keying on the whole serialized payload instead would pass two observations
        # with identical identity and different prose -- precisely the collision the
        # rule exists to prevent. Ingestion enforces it after computing fingerprints
        # (`science_tool.findings.ingest._plan`).
        if self.totals.findings_total != len(self.findings):
            raise ValueError(f"totals.findings_total {self.totals.findings_total} != {len(self.findings)} findings")
        if self.totals.accepted_total != len(self.accepted):
            raise ValueError("totals.accepted_total disagrees with the accepted channel")
        if self.totals.unwired_total != len(self.unwired):
            raise ValueError("totals.unwired_total disagrees with the unwired channel")
        # `findings_by_severity` counts the UNSUPPRESSED channel only -- it is the
        # severity breakdown of what is being shown. Checking the scalar total while
        # leaving the breakdown unchecked is how a summary comes to disagree with the
        # rows underneath it. Equality is exact: a `{"warn": 0}` entry for a severity
        # nothing emitted is a disagreement, not a harmless zero.
        actual = Counter(item.finding.severity for item in self.findings)
        if dict(self.totals.findings_by_severity) != dict(actual):
            raise ValueError(
                f"totals.findings_by_severity {dict(self.totals.findings_by_severity)} "
                f"disagrees with the findings channel {dict(actual)}"
            )
        producers_run = set(self.meta.producers_run)
        unwired = [item.producer_id for item in self.unwired]
        if len(unwired) != len(set(unwired)):
            raise ValueError("duplicate unwired producer ids are forbidden")
        overlap = producers_run & set(unwired)
        if overlap:
            raise ValueError(f"producer ids cannot appear in both producers_run and unwired: {sorted(overlap)}")
        caveat_producers = [item.producer_id for item in self.caveats]
        if len(caveat_producers) != len(set(caveat_producers)):
            raise ValueError("duplicate caveat producer ids are forbidden")
        output_producers = {
            *(item.producer_id for item in self.findings),
            *(item.producer_id for item in self.accepted),
            *self.metrics,
            *caveat_producers,
        }
        missing = output_producers - producers_run
        if missing:
            raise ValueError(f"output producer ids must be named in meta.producers_run; missing {sorted(missing)}")
        return self
