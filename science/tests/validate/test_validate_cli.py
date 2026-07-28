import json
from pathlib import Path

from click.testing import CliRunner
from science_model.audit import PathSubject

from science_tool.cli import main
from science_tool.findings.catalog import build_project_registry
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
        notices=(
            ValidationNotice(path=Path("science.yaml"), line=2, message="checked manifest"),
        ),
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
