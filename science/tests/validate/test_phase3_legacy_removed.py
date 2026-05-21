from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock

import pytest

from science_tool.validate import Check, Result, Severity, ValidateContext
from science_tool.validate._legacy import runner as legacy_runner
from science_tool.validate.checks import clear_checks_for_tests
from science_tool.validate.runner import clear_hooks_for_tests, run


PORTING_GUIDE = "docs/migration/2026-05-19-validate-local-sh-porting-guide.md"


@pytest.fixture(autouse=True)
def clean_registries() -> Generator[None]:
    clear_checks_for_tests()
    clear_hooks_for_tests()
    yield
    clear_hooks_for_tests()
    clear_checks_for_tests()


def _project(root: Path) -> Path:
    root.joinpath("science.yaml").write_text("name: demo\n", encoding="utf-8")
    return root


def test_legacy_validate_local_sh_emits_error_without_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    project.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_extra() {",
                '  warn "legacy sidecar executed"',
                "}",
                "register_validation_hook extra_checks legacy_extra",
                "",
            ]
        ),
        encoding="utf-8",
    )
    subprocess_run = Mock()
    monkeypatch.setattr(legacy_runner.subprocess, "run", subprocess_run)

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    subprocess_run.assert_not_called()
    assert result.errors == 1
    assert result.results == [
        Result(
            Severity.ERROR,
            None,
            None,
            f"validate.local.sh is no longer supported; migrate it using {PORTING_GUIDE}",
            "validate.sidecar.legacy_removed",
            None,
        )
    ]


def test_legacy_validate_local_sh_error_does_not_stop_canonical_checks(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    project.joinpath("validate.local.sh").write_text("", encoding="utf-8")

    @Check(section="canonical", order=10)
    def canonical(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, None, None, "canonical still ran", "canonical", None)]

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.severity for item in result.results] == [Severity.ERROR, Severity.WARN]
    assert [item.message for item in result.results] == [
        f"validate.local.sh is no longer supported; migrate it using {PORTING_GUIDE}",
        "canonical still ran",
    ]


def test_disabled_sidecar_env_skips_legacy_validate_local_sh_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    project.joinpath("validate.local.sh").write_text("", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_VALIDATE_DISABLE_SIDECAR", "1")

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert result.results == []


def test_legacy_validate_local_sh_directory_still_emits_error(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("validate.local.sh").mkdir()

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert result.results == [
        Result(
            Severity.ERROR,
            None,
            None,
            f"validate.local.sh is no longer supported; migrate it using {PORTING_GUIDE}",
            "validate.sidecar.legacy_removed",
            None,
        )
    ]


def test_legacy_validate_local_sh_errors_even_when_python_sidecar_exists(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    project.joinpath("validate.local.sh").write_text("", encoding="utf-8")
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                '    return [Result(Severity.WARN, None, None, "python sidecar ran", "py", None)]',
            ]
        ),
        encoding="utf-8",
    )

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.severity for item in result.results] == [Severity.ERROR, Severity.WARN]
    assert [item.message for item in result.results] == [
        f"validate.local.sh is no longer supported; migrate it using {PORTING_GUIDE}",
        "python sidecar ran",
    ]
