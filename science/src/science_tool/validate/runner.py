from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from science_model.audit import AuditFinding, ProjectSubject

from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import (
    FindingProducerResult,
    FindingRegistry,
    validate_producer_result,
)
from science_tool.instruments import InstrumentResult
from science_tool.validate.checks import (
    CANONICAL_CHECKS,
    CheckEntry,
)
from science_tool.validate.context import ValidateContext, ValidateContextError
from science_tool.validate.gates import gated_findings, resolve_gate_tier
from science_tool.validate.observations import (
    ValidationMetricObservation,
    ValidationNotice,
    ValidationObservationBatch,
)
from science_tool.validate.result import Result
from science_tool.validate.runtime import (
    RULE_CHECK_ERROR,
    RULE_PYTHON_SIDECAR_REMOVED,
    RULE_SIDECAR_REMOVED,
    VALIDATION_RUNTIME_PRODUCER,
)

if TYPE_CHECKING:
    ValidationProfile = Literal["full", "commit"]
else:
    ValidationProfile = str


_LEGACY_SIDECAR_PORTING_GUIDE = "docs/migration/2026-05-19-validate-local-sh-porting-guide.md"
VALIDATE_PROFILES = ("full", "commit")
_COMMIT_EXCLUDED_SECTIONS = {"knowledge graph..."}
_COMMIT_EXCLUDED_FUNCTIONS = {"check_belief_authoring"}


@dataclass(frozen=True)
class RunResult:
    results: list[AuditFinding]
    producer_results: Mapping[str, FindingProducerResult]
    notices: tuple[ValidationNotice, ...]
    registry: FindingRegistry
    errors: int
    warnings: int
    infos: int
    gate_tier: str = "report"
    gated: tuple[AuditFinding, ...] = ()
    sections: tuple[str, ...] = ()
    skipped_sections: tuple[str, ...] = ()
    profile: ValidationProfile = "full"


def run(
    project_root: Path,
    *,
    strict: bool,
    verbose: bool,
    fail_on: str | None = None,
    profile: ValidationProfile = "full",
    include_all_checks: bool = False,
) -> RunResult:
    checks = _checks_for_profile(profile)
    skipped_checks = _skipped_checks_for_profile(profile)
    ctx = ValidateContext.from_project_root(
        project_root,
        strict=strict,
        verbose=verbose,
        include_all_checks=include_all_checks,
    )
    registry = _validation_registry(ctx.project_root)
    producer_results: dict[str, FindingProducerResult] = {}
    notices: list[ValidationNotice] = []
    runtime_findings: list[AuditFinding] = []

    if (ctx.project_root / "validate.local.sh").exists():
        runtime_findings.append(
            RULE_SIDECAR_REMOVED.build(
                subject=ProjectSubject(),
                severity="error",
                qualifiers={},
                message=(
                    "validate.local.sh is no longer supported; migrate it using "
                    f"{_LEGACY_SIDECAR_PORTING_GUIDE}"
                ),
            )
        )
    if (ctx.project_root / "validate_local.py").is_file():
        runtime_findings.append(
            RULE_PYTHON_SIDECAR_REMOVED.build(
                subject=ProjectSubject(),
                severity="error",
                qualifiers={},
                message=(
                    "validate_local.py is no longer executed; project checks belong "
                    f"in the toolkit. See {_LEGACY_SIDECAR_PORTING_GUIDE}"
                ),
            )
        )

    for entry in checks:
        try:
            raw_observations = tuple(entry.fn(ctx))
        except Exception as exc:  # noqa: BLE001 - operational check failure
            detail = (
                f"check {entry.fn.__name__!r} (section "
                f"{entry.section!r}) could not run: "
                f"{type(exc).__name__}: {exc}"
            )
            runtime_findings.append(
                RULE_CHECK_ERROR.build(
                    subject=ProjectSubject(),
                    severity="error",
                    qualifiers={"check": entry.fn.__name__},
                    message=detail,
                )
            )
            producer_results[entry.producer.producer_id] = validate_producer_result(
                registry,
                entry.producer.producer_id,
                FindingProducerResult(
                    instrument=InstrumentResult.unwired(
                        code="check-error",
                        reason=detail,
                    )
                ),
            )
            continue
        producer_result, check_notices = _execute_check(
            entry,
            ctx,
            registry,
            raw_observations,
        )
        producer_results[entry.producer.producer_id] = producer_result
        notices.extend(check_notices)
    runtime_result = FindingProducerResult(
        instrument=InstrumentResult.from_rows(runtime_findings),
    )
    producer_results[VALIDATION_RUNTIME_PRODUCER.producer_id] = validate_producer_result(
        registry,
        VALIDATION_RUNTIME_PRODUCER.producer_id,
        runtime_result,
    )
    results = [
        finding for producer_result in producer_results.values() for finding in producer_result.instrument.rows
    ]
    run_result = _tally(
        results,
        producer_results,
        tuple(notices),
        registry,
        checks,
        skipped_checks,
        profile,
    )
    try:
        tier = resolve_gate_tier(fail_on, ctx.manifest)
    except ValueError as exc:
        raise ValidateContextError(str(exc)) from exc
    return replace(run_result, gate_tier=tier, gated=tuple(gated_findings(results, tier)))


def _validation_registry(project_root: Path) -> FindingRegistry:
    return build_project_registry(project_root)


def _execute_check(
    entry: CheckEntry,
    ctx: ValidateContext,
    registry: FindingRegistry,
    raw_observations: tuple[object, ...],
) -> tuple[FindingProducerResult, tuple[ValidationNotice, ...]]:
    observations: list[AuditFinding | ValidationMetricObservation | ValidationNotice] = []
    for item in raw_observations:
        if isinstance(item, Result):
            observations.append(item.to_finding(ctx.project_root))
        elif isinstance(item, ValidationMetricObservation | ValidationNotice):
            observations.append(item)
        else:
            raise TypeError(f"unsupported validation observation {type(item).__name__}")
    batch = ValidationObservationBatch.from_observations(observations)
    result = entry.produce(batch)
    return (
        validate_producer_result(
            registry,
            entry.producer.producer_id,
            result,
        ),
        batch.notices,
    )


def _checks_for_profile(profile: ValidationProfile) -> list[CheckEntry]:
    if profile == "full":
        return list(CANONICAL_CHECKS)
    if profile == "commit":
        return [entry for entry in CANONICAL_CHECKS if not _commit_profile_excludes(entry)]
    raise ValueError(f"unknown validation profile: {profile}")


def _skipped_checks_for_profile(profile: ValidationProfile) -> list[CheckEntry]:
    if profile == "full":
        return []
    if profile == "commit":
        return [entry for entry in CANONICAL_CHECKS if _commit_profile_excludes(entry)]
    raise ValueError(f"unknown validation profile: {profile}")


def _commit_profile_excludes(entry: CheckEntry) -> bool:
    return entry.section in _COMMIT_EXCLUDED_SECTIONS or entry.fn.__name__ in _COMMIT_EXCLUDED_FUNCTIONS


def _tally(
    results: list[AuditFinding],
    producer_results: Mapping[str, FindingProducerResult],
    notices: tuple[ValidationNotice, ...],
    registry: FindingRegistry,
    checks: list[CheckEntry],
    skipped_checks: list[CheckEntry],
    profile: ValidationProfile,
) -> RunResult:
    return RunResult(
        results=results,
        producer_results=producer_results,
        notices=notices,
        registry=registry,
        errors=sum(1 for result in results if result.severity == "error"),
        warnings=sum(1 for result in results if result.severity == "warn"),
        infos=sum(1 for result in results if result.severity == "info"),
        sections=tuple(dict.fromkeys(entry.section for entry in checks)),
        skipped_sections=tuple(dict.fromkeys(entry.section for entry in skipped_checks)),
        profile=profile,
    )
