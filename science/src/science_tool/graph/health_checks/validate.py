"""Validation health producer: envelope canonical validation observations."""

from __future__ import annotations

from science_model.audit import ProducerMetrics

from science_tool.findings.producers import FindingProducer, FindingProducerResult
from science_tool.graph.health_checks.base import HealthCheck, HealthContext
from science_tool.instruments import InstrumentResult
from science_tool.validate.checks.prose_lints import NumericVerificationMetrics


PRODUCER = FindingProducer(
    producer_id="validate",
    namespace="health_checks",
    source_module="graph/health_checks/validate.py",
    rules=(),
    metrics_schema=NumericVerificationMetrics,
)


def run_check(context: HealthContext) -> FindingProducerResult:
    from science_tool.validate import runner as validate_runner

    run_result = validate_runner.run(
        context.project_root,
        strict=False,
        verbose=False,
        enable_python_sidecar=False,
    )
    findings = [finding for finding in run_result.results if finding.severity != "info"]
    numeric = run_result.producer_results["validate.prose-lints"].metrics
    return FindingProducerResult(
        instrument=InstrumentResult.from_rows(findings),
        metrics=ProducerMetrics.model_validate(numeric.model_dump(mode="json")),
    )


CHECK = HealthCheck(
    name="validate",
    description="Run canonical project validation and surface warnings/errors.",
    requires_sources=False,
    run=run_check,
    producer=PRODUCER,
)
