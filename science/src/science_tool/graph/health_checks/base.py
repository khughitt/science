"""Shared machinery for health checks: context, timing, and check registration.

Moved out of `graph/health.py` so check modules can import it without a cycle
back into `health.py` (which imports the checks).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from time import perf_counter
from typing import Callable, TypedDict, TypeVar

from science_model.audit import AuditFinding, ProducerMetrics

from science_tool.findings.producers import FindingProducer, FindingProducerResult
from science_tool.graph.sources import ProjectSources
from science_tool.instruments import InstrumentResult

#: An unscannable project does not raise — ``load_project_sources`` simply returns zero
#: entities, and every entity-driven check then "finds" nothing. That is the silent
#: instrument this code exists to stop, so the three checks that walk ``sources.entities``
#: share one precondition and one code.
PROJECT_SOURCES_EMPTY = "project_sources_empty"
NO_ENTITIES_REASON = "project sources loaded zero entities; nothing was scanned"

_T = TypeVar("_T")


class HealthTiming(TypedDict):
    name: str
    duration_seconds: float


@dataclass
class HealthContext:
    project_root: Path
    collect_timings: bool = False
    sources: ProjectSources | None = None
    selected_checks: tuple[HealthCheck, ...] = ()
    timings: list[HealthTiming] = dataclass_field(default_factory=list)

    def run(self, name: str, fn: Callable[[], _T]) -> _T:
        started = perf_counter()
        result = fn()
        if self.collect_timings:
            self.timings.append(
                {
                    "name": name,
                    "duration_seconds": perf_counter() - started,
                }
            )
        return result


@dataclass(frozen=True)
class HealthCheck:
    name: str
    description: str
    requires_sources: bool
    run: Callable[[HealthContext], FindingProducerResult]
    producer: FindingProducer


def composed_result(
    source: InstrumentResult[object],
    findings: list[AuditFinding],
    *,
    metrics: ProducerMetrics | None = None,
) -> FindingProducerResult:
    """Preserve an instrument's status/caveat while replacing its rows atomically."""
    if source.status == "unwired":
        instrument = InstrumentResult[AuditFinding].unwired(
            code=source.code or "health_check_unwired",
            reason=source.reason,
        )
    else:
        instrument = InstrumentResult.from_rows(
            findings,
            code=source.code,
            reason=source.reason,
        )
    return FindingProducerResult(
        instrument=instrument,
        metrics=metrics or ProducerMetrics(),
    )


def context_sources(context: HealthContext) -> ProjectSources:
    if context.sources is None:
        raise RuntimeError("health check requires loaded project sources")
    return context.sources


IDENTITY_REFERENCE_FIELDS = (
    "related",
    "commits_to",
    "source_refs",
    "evidence_refs",
    "same_as",
    "blocked_by",
    "consumed_by",
)
