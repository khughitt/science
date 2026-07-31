"""Validation health producer: envelope canonical validation observations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from science_model.audit import ProducerMetrics

from science_tool.findings.producers import FindingProducer, FindingProducerResult
from science_tool.graph.health_checks.base import HealthCheck, HealthContext
from science_tool.instruments import InstrumentResult
from science_tool.validate.checks.prose_lints import NumericVerificationMetrics
from science_tool.validate.runner import RunResult

if TYPE_CHECKING:
    from science_tool.graph.sources import ProjectSources


PRODUCER = FindingProducer(
    producer_id="validate",
    namespace="health_checks",
    source_module="graph/health_checks/validate.py",
    rules=(),
    metrics_schema=NumericVerificationMetrics,
)


@dataclass(frozen=True)
class ValidationHealthRun:
    run_result: RunResult
    producer_result: FindingProducerResult


def execute_validation(
    project_root: Path,
    *,
    project_sources: ProjectSources | None = None,
) -> ValidationHealthRun:
    from science_tool.validate import runner as validate_runner

    run_result = validate_runner.run(
        project_root,
        strict=False,
        verbose=False,
        project_sources=project_sources,
    )
    unwired_producers = tuple(
        sorted(
            producer_id
            for producer_id, result in run_result.producer_results.items()
            if result.instrument.status == "unwired"
        )
    )
    if unwired_producers:
        producer_result = FindingProducerResult(
            instrument=InstrumentResult.unwired(
                code="validation-checks-unwired",
                reason=("validation checks unwired: " + ", ".join(unwired_producers)),
            )
        )
    else:
        numeric_result = run_result.producer_results["validate.prose-lints"]
        findings = [finding for finding in run_result.results if finding.severity != "info"]
        numeric = numeric_result.metrics
        producer_result = FindingProducerResult(
            instrument=InstrumentResult.from_rows(findings),
            metrics=ProducerMetrics.model_validate(numeric.model_dump(mode="json")),
        )
    return ValidationHealthRun(run_result=run_result, producer_result=producer_result)


def run_check(context: HealthContext) -> FindingProducerResult:
    return execute_validation(
        context.project_root,
        project_sources=context.sources,
    ).producer_result


CHECK = HealthCheck(
    name="validate",
    description="Run canonical project validation and surface warnings/errors.",
    requires_sources=False,
    run=run_check,
    producer=PRODUCER,
)
