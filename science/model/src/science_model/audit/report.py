"""The public audit output contract (design §11).

Findings are ENVELOPED with their producer. A bare `AuditFinding` cannot populate an
occurrence's required `producer_id`, and rule ownership cannot supply it either —
several producers must be able to emit one rule, which is the premise of
cross-producer dedup.

`ingestion_ref` and `generated_at` are report-level and TRUSTED: supplied by the
supervisor or the ingesting command, never by a finding.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from science_model.audit.finding import AuditFinding, HashComponent

REPORT_SCHEMA_VERSION = 2

#: The ceiling applies to `findings + accepted` TOGETHER. Both channels are ingested
#: (design §8), so a bound on one alone is a bound on nothing: 5000 accepted
#: observations cost exactly what 5000 unsuppressed ones cost.
MAX_REPORT_FINDINGS = 5000


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReportedFinding(_Base):
    #: `HashComponent`: ingestion copies this straight onto an `Occurrence`, where it
    #: is joined with `\0` into the idempotency key. Refusing here rather than there
    #: keeps the failure a report-validation error the caller asked for, instead of a
    #: `ValidationError` surfacing from inside the write path.
    producer_id: HashComponent = Field(min_length=1)
    finding: AuditFinding


class AcceptedFinding(_Base):
    producer_id: HashComponent = Field(min_length=1)
    finding: AuditFinding
    acceptance_key: str = Field(pattern=r"^[0-9a-f]{32}$")
    reason: str = Field(min_length=1)


class UnwiredProducer(_Base):
    producer_id: HashComponent
    code: str = Field(min_length=1)
    reason: str | None = None


class ProducerMetrics(BaseModel):
    """Validated against the schema the producer declared at registration (§6).

    `extra="allow"` here and strict validation there: this type is the transport,
    the producer's declared schema is the contract. `science_tool.findings.producers`
    performs that validation; `science_model` cannot, because it does not know the
    registry.
    """

    model_config = ConfigDict(extra="allow")


class ReportTotals(_Base):
    findings_total: int = Field(ge=0)
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    accepted_total: int = Field(ge=0)
    unwired_total: int = Field(ge=0)


class ReportMeta(_Base):
    producers_run: list[str] = Field(default_factory=list)
    total_duration_seconds: float
    timings: list[dict[str, object]] = Field(default_factory=list)


class AuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2]
    fingerprint_version: int
    #: `HashComponent`: this becomes the `ingestion_ref` of every occurrence written.
    ingestion_ref: HashComponent = Field(min_length=1)
    #: ISO-8601, and validated as such HERE. Ingestion turns this into the
    #: `observed_at` of every occurrence it writes; a bare `min_length=1` would push a
    #: raw `ValueError` from `datetime.fromisoformat` out of the write path, where it
    #: is neither an `IngestError` nor a validation failure the caller can report.
    generated_at: str = Field(min_length=1)
    findings: list[ReportedFinding] = Field(max_length=MAX_REPORT_FINDINGS)
    accepted: list[AcceptedFinding] = Field(
        default_factory=list, max_length=MAX_REPORT_FINDINGS
    )
    metrics: dict[str, ProducerMetrics] = Field(default_factory=dict)
    unwired: list[UnwiredProducer] = Field(default_factory=list)
    totals: ReportTotals
    meta: ReportMeta

    @field_validator("generated_at")
    @classmethod
    def _iso_8601(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"generated_at must be ISO-8601, got {value!r}: {exc}"
            ) from exc
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
        if len(self.findings) + len(self.accepted) > MAX_REPORT_FINDINGS:
            raise ValueError(
                f"{len(self.findings)} findings + {len(self.accepted)} accepted exceeds "
                f"the {MAX_REPORT_FINDINGS} ceiling; both channels are ingested, so the "
                "bound is on their sum"
            )
        if self.totals.findings_total != len(self.findings):
            raise ValueError(
                f"totals.findings_total {self.totals.findings_total} != "
                f"{len(self.findings)} findings"
            )
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
        return self
