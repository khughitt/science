from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from science_tool.validate import Check, Result, Severity, ValidateContext
from science_tool.validate.checks import clear_checks_for_tests
from science_tool.validate.runner import clear_hooks_for_tests, run


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


def test_bash_sidecar_runs_legacy_phases_with_single_deprecation_first(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _register_canonical_result()
    _write_bash_sidecar(project)

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == [
        "validate.local.sh is deprecated; migrate validation hooks to validate_local.py",
        "CANONICAL-FIRED",
        "SH-FIRED",
    ]
    assert result.results[0].severity is Severity.WARN
    assert result.results[0].rule == "validate.sidecar.legacy_deprecated"
    assert result.warnings == 2


def test_python_sidecar_takes_precedence_over_stale_bash_sidecar(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _register_canonical_result()
    _write_python_sidecar(project)
    _write_bash_sidecar(project)

    result = run(project, strict=False, verbose=False, enable_python_sidecar=True)

    assert [item.message for item in result.results] == [
        "validate.local.sh is deprecated and ignored because validate_local.py takes precedence",
        "CANONICAL-FIRED",
        "PY-FIRED",
    ]
    assert result.results[0].severity is Severity.WARN
    assert result.results[0].rule == "validate.sidecar.legacy_deprecated"
    assert result.warnings == 2


def test_bash_pre_validation_hook_runs_before_canonical_checks(tmp_path: Path) -> None:
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
    messages = [item.message for item in result.results]

    assert messages.index("PRE-FIRED") < messages.index("CANONICAL-FIRED")


def test_bash_extra_checks_hook_runs_after_canonical_checks(tmp_path: Path) -> None:
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
    messages = [item.message for item in result.results]

    assert messages.index("CANONICAL-FIRED") < messages.index("POST-FIRED")


def test_integrated_bash_sidecar_sources_top_level_once_per_legacy_phase(
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

    assert project.joinpath("source-count.txt").read_text(encoding="utf-8").splitlines() == [
        "sourced",
        "sourced",
    ]
    assert [item.message for item in result.results] == [
        "validate.local.sh is deprecated; migrate validation hooks to validate_local.py",
        "PRE-FIRED",
        "CANONICAL-FIRED",
        "EXTRA-FIRED",
    ]


def test_integrated_bash_pre_failure_records_error_and_continues(
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
        "validate.local.sh is deprecated; migrate validation hooks to validate_local.py",
        "PRE-FIRED",
        "legacy sidecar exited with code 23: pre failed",
        "CANONICAL-FIRED",
        "EXTRA-FIRED",
    ]
    assert [item.severity for item in result.results] == [
        Severity.WARN,
        Severity.WARN,
        Severity.ERROR,
        Severity.ERROR,
        Severity.WARN,
    ]
