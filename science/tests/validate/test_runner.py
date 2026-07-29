from dataclasses import replace
from pathlib import Path

import pytest
from science_model.audit import IdentifierSubject, ProducerMetrics, ProjectSubject

from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import FindingProducerResult, RegistryError
from science_tool.graph.health_checks import validate as validate_health
from science_tool.graph.health_checks.base import HealthContext
from science_tool.instruments import InstrumentResult
from science_tool.validate.checks import CANONICAL_CHECKS
from science_tool.validate.checks.accepted_validation import RULE_INVALID_ENTRY
from science_tool.validate.checks.manifest import RULES as MANIFEST_RULES
from science_tool.validate.result import Result, Severity
from science_tool.validate.runner import run


def _project(root: Path) -> Path:
    (root / "science.yaml").write_text("name: test\n", encoding="utf-8")
    return root


def _wired_numeric_result() -> FindingProducerResult:
    return FindingProducerResult(
        instrument=InstrumentResult.empty(),
        metrics=ProducerMetrics.model_validate(
            {
                "verified": 0,
                "unverifiable": 0,
                "mismatch": 0,
                "error": 0,
            }
        ),
    )


def _run_result_with_producer_results(
    root: Path,
    producer_results: dict[str, FindingProducerResult],
):
    from science_tool.validate.runner import RunResult

    return RunResult(
        results=[],
        producer_results=producer_results,
        notices=(),
        registry=build_project_registry(root),
        errors=0,
        warnings=0,
        infos=0,
    )


def test_result_to_finding_preserves_subject_override_exactly(
    tmp_path: Path,
) -> None:
    subject = IdentifierSubject(namespace="accepted-validation", value="a" * 32)
    result = Result(
        severity=Severity.ERROR,
        path=None,
        line=None,
        message="invalid entry",
        rule=RULE_INVALID_ENTRY,
        task=None,
        qualifiers={},
        subject=subject,
    )

    assert result.to_finding(tmp_path).subject == subject


def test_result_rejects_subject_override_with_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="subject.*path"):
        Result(
            severity=Severity.ERROR,
            path=tmp_path / "science.yaml",
            line=None,
            message="invalid entry",
            rule=RULE_INVALID_ENTRY,
            task=None,
            qualifiers={},
            subject=IdentifierSubject(
                namespace="accepted-validation",
                value="a" * 32,
            ),
        )


def test_runner_returns_only_audit_findings_and_validated_results(
    tmp_path: Path,
) -> None:
    result = run(
        _project(tmp_path),
        strict=False,
        verbose=False,
    )
    assert result.registry.producers_by_id
    assert result.producer_results
    assert all(item.__class__.__name__ == "AuditFinding" for item in result.results)
    assert result.errors == sum(item.severity == "error" for item in result.results)
    assert result.warnings == sum(item.severity == "warn" for item in result.results)
    assert result.infos == sum(item.severity == "info" for item in result.results)


def test_runner_keeps_numeric_coverage_in_metrics(tmp_path: Path) -> None:
    result = run(
        _project(tmp_path),
        strict=False,
        verbose=False,
    )
    metrics = result.producer_results["validate.prose-lints"].metrics
    assert metrics.model_dump(mode="json") == {
        "verified": 0,
        "unverifiable": 0,
        "mismatch": 0,
        "error": 0,
    }
    assert not [item for item in result.results if "numeric-verification.coverage" in item.rule_id]


def test_runner_exception_uses_declared_runtime_rule(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import science_tool.validate.runner as runner

    manifest = next(entry for entry in CANONICAL_CHECKS if entry.producer.producer_id == "validate.manifest")
    broken = replace(
        manifest,
        fn=lambda _ctx: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    monkeypatch.setattr(runner, "_checks_for_profile", lambda _profile: (broken,))
    monkeypatch.setattr(runner, "_skipped_checks_for_profile", lambda _profile: ())
    result = runner.run(
        _project(tmp_path),
        strict=False,
        verbose=False,
    )
    crashes = [item for item in result.results if item.rule_id == "validate.check-error"]
    assert len(crashes) == 1
    assert crashes[0].subject == ProjectSubject()
    assert crashes[0].qualifiers["check"] == "<lambda>"
    failed = result.producer_results["validate.manifest"]
    assert failed.instrument.status == "unwired"
    assert failed.instrument.code == "check-error"


def test_runner_fails_early_on_wrong_observation_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.validate.runner as runner

    manifest = next(entry for entry in CANONICAL_CHECKS if entry.producer.producer_id == "validate.manifest")
    malformed = replace(manifest, fn=lambda _ctx: (object(),))
    monkeypatch.setattr(runner, "_checks_for_profile", lambda _profile: (malformed,))
    monkeypatch.setattr(runner, "_skipped_checks_for_profile", lambda _profile: ())

    with pytest.raises(TypeError, match="unsupported validation observation"):
        runner.run(
            _project(tmp_path),
            strict=False,
            verbose=False,
        )


def test_runner_fails_early_on_duplicate_finding_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.validate.runner as runner

    manifest = next(entry for entry in CANONICAL_CHECKS if entry.producer.producer_id == "validate.manifest")
    duplicate = Result(
        severity=Severity.ERROR,
        path=tmp_path / "science.yaml",
        line=None,
        message="duplicate",
        rule=MANIFEST_RULES["manifest.check"],
        task=None,
        qualifiers={"key": ["duplicate"]},
    )
    malformed = replace(manifest, fn=lambda _ctx: (duplicate, duplicate))
    monkeypatch.setattr(runner, "_checks_for_profile", lambda _profile: (malformed,))
    monkeypatch.setattr(runner, "_skipped_checks_for_profile", lambda _profile: ())

    with pytest.raises(RegistryError, match="duplicate finding identity"):
        runner.run(
            _project(tmp_path),
            strict=False,
            verbose=False,
        )


def test_health_validation_reports_required_metric_check_failure_as_unwired(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.validate.runner as runner

    prose = next(entry for entry in CANONICAL_CHECKS if entry.producer.producer_id == "validate.prose-lints")
    broken = replace(
        prose,
        fn=lambda _ctx: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(runner, "_checks_for_profile", lambda _profile: (broken,))
    monkeypatch.setattr(runner, "_skipped_checks_for_profile", lambda _profile: ())

    result = validate_health.run_check(
        HealthContext(project_root=_project(tmp_path)),
    )

    assert result.instrument.status == "unwired"
    assert result.instrument.code == "validation-checks-unwired"
    assert result.instrument.reason == ("validation checks unwired: validate.prose-lints")


def test_health_validation_reports_any_canonical_check_failure_as_unwired(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.validate.runner as validate_runner

    project = _project(tmp_path)
    expected = _run_result_with_producer_results(
        project,
        {
            "validate.manifest": FindingProducerResult(
                instrument=InstrumentResult.unwired(
                    code="check-error",
                    reason="manifest failed",
                )
            ),
            "validate.prose-lints": _wired_numeric_result(),
        },
    )
    monkeypatch.setattr(validate_runner, "run", lambda *_args, **_kwargs: expected)

    result = validate_health.execute_validation(project).producer_result

    assert result.instrument.status == "unwired"
    assert result.instrument.code == "validation-checks-unwired"
    assert result.instrument.reason == "validation checks unwired: validate.manifest"
    assert result.instrument.rows == []
    assert result.metrics.model_dump(mode="json") == {}


def test_health_validation_sorts_multiple_unwired_producer_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.validate.runner as validate_runner

    project = _project(tmp_path)
    expected = _run_result_with_producer_results(
        project,
        {
            "validate.tasks": FindingProducerResult(
                instrument=InstrumentResult.unwired(
                    code="check-error",
                    reason="tasks failed",
                )
            ),
            "validate.manifest": FindingProducerResult(
                instrument=InstrumentResult.unwired(
                    code="check-error",
                    reason="manifest failed",
                )
            ),
            "validate.prose-lints": _wired_numeric_result(),
        },
    )
    monkeypatch.setattr(validate_runner, "run", lambda *_args, **_kwargs: expected)

    result = validate_health.execute_validation(project).producer_result

    assert result.instrument.status == "unwired"
    assert result.instrument.reason == ("validation checks unwired: validate.manifest, validate.tasks")


def test_execute_validation_projects_one_fixed_run_result_without_a_second_stream(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.validate.runner as validate_runner

    expected = run(
        _project(tmp_path),
        strict=False,
        verbose=False,
    )
    monkeypatch.setattr(validate_runner, "run", lambda *_args, **_kwargs: expected)

    execution = validate_health.execute_validation(tmp_path)

    assert execution.run_result is expected
    assert execution.producer_result.instrument.rows == [
        finding for finding in expected.results if finding.severity != "info"
    ]


def test_graph_health_reports_the_legacy_sidecar(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "validate.local.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    execution = validate_health.execute_validation(project)

    rows = [
        finding
        for finding in execution.producer_result.instrument.rows
        if finding.rule_id == "validate.sidecar-removed"
    ]
    assert len(rows) == 1
    assert rows[0].severity == "error"


def test_graph_health_is_clean_without_a_legacy_sidecar(tmp_path: Path) -> None:
    execution = validate_health.execute_validation(_project(tmp_path))

    assert not [
        finding
        for finding in execution.producer_result.instrument.rows
        if finding.rule_id == "validate.sidecar-removed"
    ]


def test_runner_uses_global_project_registry(tmp_path: Path) -> None:
    result = run(
        _project(tmp_path),
        strict=False,
        verbose=False,
    )
    expected = build_project_registry(tmp_path)
    assert result.registry.rules_by_id == expected.rules_by_id
