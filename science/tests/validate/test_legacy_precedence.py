from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from science_tool.validate import Check, Result, Severity, ValidateContext
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


def _register_canonical_result(message: str = "CANONICAL-FIRED") -> None:
    @Check(section="canonical", order=10)
    def canonical(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.ERROR, None, None, message, "canonical", None)]


def _write_python_sidecar(project: Path) -> None:
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                '    return [Result(Severity.WARN, None, None, "PY-FIRED", "py", None)]',
            ]
        ),
        encoding="utf-8",
    )


def _write_bash_sidecar(project: Path) -> None:
    project.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_extra() {",
                '  warn "SH-FIRED"',
                "}",
                "register_validation_hook extra_checks legacy_extra",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_no_sidecar_runs_no_sidecar_and_emits_no_deprecation(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _register_canonical_result()

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == ["CANONICAL-FIRED"]
    assert result.warnings == 0


def test_python_sidecar_takes_python_path_without_deprecation(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _register_canonical_result()
    _write_python_sidecar(project)

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == ["CANONICAL-FIRED", "PY-FIRED"]
    assert [item.rule for item in result.results] == ["canonical", "py"]


def test_bash_sidecar_emits_hard_error_without_running_legacy_hooks(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _register_canonical_result()
    _write_bash_sidecar(project)

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == [
        f"validate.local.sh is no longer supported; migrate it using {PORTING_GUIDE}",
        "CANONICAL-FIRED",
    ]
    assert result.results[0].severity is Severity.ERROR
    assert result.results[0].rule == "validate.sidecar.legacy_removed"
    assert result.errors == 2


def test_stale_bash_sidecar_errors_even_when_python_sidecar_exists(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _register_canonical_result()
    _write_python_sidecar(project)
    _write_bash_sidecar(project)

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == [
        f"validate.local.sh is no longer supported; migrate it using {PORTING_GUIDE}",
        "CANONICAL-FIRED",
        "PY-FIRED",
    ]
    assert result.results[0].severity is Severity.ERROR
    assert result.results[0].rule == "validate.sidecar.legacy_removed"
    assert result.errors == 2


def test_bash_pre_validation_hook_does_not_run(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _register_canonical_result()
    project.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_pre() {",
                '  warn "PRE-FIRED"',
                "}",
                "register_validation_hook pre_validation legacy_pre",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == [
        f"validate.local.sh is no longer supported; migrate it using {PORTING_GUIDE}",
        "CANONICAL-FIRED",
    ]


def test_bash_extra_checks_hook_does_not_run(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _register_canonical_result()
    project.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_extra() {",
                '  warn "POST-FIRED"',
                "}",
                "register_validation_hook extra_checks legacy_extra",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == [
        f"validate.local.sh is no longer supported; migrate it using {PORTING_GUIDE}",
        "CANONICAL-FIRED",
    ]


def test_integrated_bash_sidecar_is_never_sourced(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _register_canonical_result()
    project.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                'printf "sourced\\n" >> source-count.txt',
                "legacy_pre() {",
                '  warn "PRE-FIRED"',
                "}",
                "legacy_extra() {",
                '  warn "EXTRA-FIRED"',
                "}",
                "register_validation_hook pre_validation legacy_pre",
                "register_validation_hook extra_checks legacy_extra",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert not project.joinpath("source-count.txt").exists()
    assert [item.message for item in result.results] == [
        f"validate.local.sh is no longer supported; migrate it using {PORTING_GUIDE}",
        "CANONICAL-FIRED",
    ]


def test_integrated_bash_pre_failure_is_not_executed_and_canonical_checks_continue(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _register_canonical_result()
    project.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_pre() {",
                '  warn "PRE-FIRED"',
                '  printf "pre failed" >&2',
                "  exit 23",
                "}",
                "legacy_extra() {",
                '  warn "EXTRA-FIRED"',
                "}",
                "register_validation_hook pre_validation legacy_pre",
                "register_validation_hook extra_checks legacy_extra",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == [
        f"validate.local.sh is no longer supported; migrate it using {PORTING_GUIDE}",
        "CANONICAL-FIRED",
    ]
    assert [item.severity for item in result.results] == [
        Severity.ERROR,
        Severity.ERROR,
    ]
