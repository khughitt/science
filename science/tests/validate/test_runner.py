from pathlib import Path

import pytest
from science_model.audit import ProjectSubject

from science_tool.findings.catalog import build_project_registry
from science_tool.validate.checks.manifest import RULES as MANIFEST_RULES
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity
from science_tool.validate.runner import run


def _project(root: Path) -> Path:
    (root / "science.yaml").write_text("name: test\n", encoding="utf-8")
    return root


def test_runner_returns_only_audit_findings_and_validated_results(
    tmp_path: Path,
) -> None:
    result = run(
        _project(tmp_path),
        strict=False,
        verbose=False,
        enable_python_sidecar=False,
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
        enable_python_sidecar=False,
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

    class Broken:
        section = "broken"
        fn = staticmethod(lambda _ctx: (_ for _ in ()).throw(RuntimeError("boom")))
        producer = type("Producer", (), {"producer_id": "validate.manifest"})()

    monkeypatch.setattr(runner, "_checks_for_profile", lambda _profile: (Broken(),))
    monkeypatch.setattr(runner, "_skipped_checks_for_profile", lambda _profile: ())
    result = runner.run(
        _project(tmp_path),
        strict=False,
        verbose=False,
        enable_python_sidecar=False,
    )
    crashes = [item for item in result.results if item.rule_id == "validate.check-error"]
    assert len(crashes) == 1
    assert crashes[0].subject == ProjectSubject()
    assert crashes[0].qualifiers["check"] == "<lambda>"


def test_runner_uses_global_project_registry(tmp_path: Path) -> None:
    result = run(
        _project(tmp_path),
        strict=False,
        verbose=False,
        enable_python_sidecar=False,
    )
    expected = build_project_registry(tmp_path)
    assert result.registry.rules_by_id == expected.rules_by_id


def test_sidecar_hook_rejects_nonpolicy_info_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.validate.runner as runner

    result = Result(
        severity=Severity.INFO,
        path=None,
        line=None,
        message="ordinary progress",
        rule=MANIFEST_RULES["manifest.check"],
        task=None,
        qualifiers={"key": ["progress"]},
    )
    monkeypatch.setitem(
        runner._HOOKS,
        "pre_validation",
        [lambda _ctx: (result,)],
    )
    ctx = ValidateContext.from_project_root(
        _project(tmp_path),
        strict=False,
        verbose=False,
    )

    with pytest.raises(TypeError, match="informational observations must use"):
        runner._dispatch_hooks("pre_validation", ctx)
