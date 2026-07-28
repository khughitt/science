from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict
from science_model.audit import AuditFinding, ProducerMetrics

from science_tool.findings.producers import FindingProducerResult
from science_tool.instruments import InstrumentResult


class ValidationMetricObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    metrics: ProducerMetrics


class ValidationNotice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: Path | None
    line: int | None
    message: str

    @property
    def severity(self) -> Literal["info"]:
        """Notices are informational observations, not policy findings."""
        return "info"

    @property
    def rule_id(self) -> None:
        """Notices deliberately have no rule declaration or finding identity."""
        return None


@dataclass(frozen=True)
class ValidationObservationBatch:
    findings: tuple[AuditFinding, ...]
    metrics: ProducerMetrics
    notices: tuple[ValidationNotice, ...]

    @classmethod
    def from_observations(
        cls,
        observations: Iterable[AuditFinding | ValidationMetricObservation | ValidationNotice],
    ) -> "ValidationObservationBatch":
        findings: list[AuditFinding] = []
        metrics: list[ValidationMetricObservation] = []
        notices: list[ValidationNotice] = []
        for observation in observations:
            if isinstance(observation, AuditFinding):
                findings.append(observation)
            elif isinstance(observation, ValidationMetricObservation):
                metrics.append(observation)
            elif isinstance(observation, ValidationNotice):
                notices.append(observation)
            else:
                raise TypeError(f"unsupported validation observation {type(observation).__name__}")
        if len(metrics) > 1:
            raise ValueError("multiple metrics observations")
        return cls(
            findings=tuple(findings),
            metrics=metrics[0].metrics if metrics else ProducerMetrics(),
            notices=tuple(notices),
        )

    def producer_result(self) -> FindingProducerResult:
        return FindingProducerResult(
            instrument=InstrumentResult.from_rows(list(self.findings)),
            metrics=self.metrics,
        )
