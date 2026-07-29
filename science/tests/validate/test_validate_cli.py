import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from science_model.audit import PathSubject

from science_tool.cli import main
from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import validate_finding
from science_tool.validate.checks.manifest import RULES
from science_tool.validate.observations import ValidationNotice
from science_tool.validate.runner import RunResult


def _run_result(root: Path, *, severity: str = "warn") -> RunResult:
    from science_tool.validate.result import Severity

    finding = RULES["manifest.check"].build(
        subject=PathSubject(path="science.yaml"),
        severity=severity,
        qualifiers={"key": ["profile"]},
        message="missing profile",
    )
    return RunResult(
        results=[finding],
        producer_results={},
        notices=(ValidationNotice(path=Path("science.yaml"), line=2, message="checked manifest"),),
        registry=build_project_registry(root),
        errors=int(severity == Severity.ERROR.value),
        warnings=int(severity == Severity.WARN.value),
        infos=int(severity == Severity.INFO.value),
        sections=("manifest",),
    )


def test_validate_json_preserves_legacy_result_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import science_tool.validate.cli as cli

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: _run_result(tmp_path))
    result = CliRunner().invoke(
        main,
        ["validate", "--project-root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["results"] == [
        {
            "severity": "warn",
            "path": "science.yaml",
            "line": None,
            "message": "missing profile",
            "rule": "manifest.check",
            "task": None,
        }
    ]


def test_validate_text_verbose_appends_notices_without_rule_label(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import science_tool.validate.cli as cli

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: _run_result(tmp_path))
    result = CliRunner().invoke(
        main,
        ["validate", "--project-root", str(tmp_path), "--verbose"],
    )
    assert result.exit_code == 0, result.output
    assert "checked manifest" in result.output
    assert "[None]" not in result.output


def test_validate_error_exits_nonzero_from_full_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import science_tool.validate.cli as cli

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "run",
        lambda *args, **kwargs: _run_result(tmp_path, severity="error"),
    )
    result = CliRunner().invoke(
        main,
        ["validate", "--project-root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 1
    assert json.loads(result.output)["summary"]["errors"] == 1


def test_validate_suppresses_current_fingerprint_warn_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import science_tool.validate.cli as cli

    run_result = _run_result(tmp_path)
    finding_id = validate_finding(
        run_result.registry,
        "validate",
        run_result.results[0],
    )
    (tmp_path / "science.yaml").write_text(
        "name: test\nhealth:\n  accepted_validation:\n"
        f"    - finding_id: {finding_id}\n"
        "      fingerprint_version: 1\n"
        "      severity_scope: [warn]\n"
        "      reason: reviewed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: run_result)

    result = CliRunner().invoke(
        main,
        ["validate", "--project-root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["results"] == []


def test_validate_warn_scope_leaves_error_with_same_fingerprint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import science_tool.validate.cli as cli

    warn_result = _run_result(tmp_path)
    error_result = _run_result(tmp_path, severity="error")
    finding_id = validate_finding(
        warn_result.registry,
        "validate",
        warn_result.results[0],
    )
    (tmp_path / "science.yaml").write_text(
        "name: test\nhealth:\n  accepted_validation:\n"
        f"    - finding_id: {finding_id}\n"
        "      fingerprint_version: 1\n"
        "      severity_scope: [warn]\n"
        "      reason: reviewed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: error_result)

    result = CliRunner().invoke(
        main,
        ["validate", "--project-root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 1
    assert [item["severity"] for item in json.loads(result.output)["results"]] == ["error"]


@pytest.mark.parametrize(
    "entry",
    [
        {"rule": "manifest.check", "reason": "reviewed"},
        {"finding_id": "not-a-fingerprint", "reason": "reviewed"},
    ],
)
def test_validate_legacy_or_invalid_entry_suppresses_nothing(
    tmp_path: Path,
    monkeypatch,
    entry: dict[str, object],
) -> None:
    import science_tool.validate.cli as cli

    import yaml

    run_result = _run_result(tmp_path)
    (tmp_path / "science.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "test",
                "health": {"accepted_validation": [entry]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: run_result)

    result = CliRunner().invoke(
        main,
        ["validate", "--project-root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    assert len(json.loads(result.output)["results"]) == 1
