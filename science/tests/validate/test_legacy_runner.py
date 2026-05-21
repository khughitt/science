from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.validate import Severity
from science_tool.validate._legacy.runner import run_legacy_sidecar


def test_run_legacy_sidecar_dispatches_registered_legacy_hook(tmp_path: Path) -> None:
    tmp_path.joinpath("doc").mkdir()
    tmp_path.joinpath("doc", "note.md").write_text("note\n", encoding="utf-8")
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_warning() {",
                '  warn "doc/note.md: legacy warning"',
                "}",
                "register_validation_hook extra_checks legacy_warning",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(tmp_path)

    assert log_lines == []
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert results[0].path == Path("doc/note.md")
    assert results[0].message == "legacy warning"


def test_run_legacy_sidecar_strips_ansi_from_sidecar_messages(tmp_path: Path) -> None:
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_warning() {",
                r'  printf "\033[33mWARN: ANSI warning\033[0m\n"',
                "}",
                "register_validation_hook pre_validation legacy_warning",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(tmp_path)

    assert log_lines == []
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert results[0].path is None
    assert results[0].message == "ANSI warning"


def test_run_legacy_sidecar_disable_env_skips_local_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCIENCE_VALIDATE_DISABLE_SIDECAR", "1")
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_warning() {",
                '  warn "SHOULD-NOT-FIRE"',
                "}",
                "register_validation_hook pre_validation legacy_warning",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(tmp_path)

    assert log_lines == []
    assert results == []


def test_run_legacy_sidecar_preserves_stdout_results_when_hook_exits_nonzero(tmp_path: Path) -> None:
    stderr_prefix = "legacy failure details: "
    stderr_tail = "x" * 2100
    long_stderr = f"{stderr_prefix}{stderr_tail}"
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "failing_warning() {",
                '  warn "stdout warning"',
                f"  printf '%s' {long_stderr!r} >&2",
                "  exit 23",
                "}",
                "register_validation_hook extra_checks failing_warning",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(tmp_path)

    assert log_lines == []
    assert len(results) == 2
    assert results[0].severity is Severity.WARN
    assert results[0].message == "stdout warning"
    assert results[1].severity is Severity.ERROR
    assert results[1].message.startswith("legacy sidecar exited with code 23: legacy failure details: ")
    assert results[1].message.endswith("...")
    assert long_stderr not in results[1].message


def test_run_legacy_sidecar_pre_validation_phase_omits_extra_checks_and_post_output(
    tmp_path: Path,
) -> None:
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_pre() {",
                '  warn "PRE-FIRED"',
                "}",
                "legacy_extra() {",
                '  warn "EXTRA-FIRED"',
                "}",
                "legacy_post() {",
                '  printf "yes" > post-ran.txt',
                '  warn "POST-FIRED"',
                "}",
                "register_validation_hook pre_validation legacy_pre",
                "register_validation_hook extra_checks legacy_extra",
                "register_validation_hook post_validation legacy_post",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(
        tmp_path,
        phase="pre_validation",
        count_post_validation=False,
    )

    assert log_lines == []
    assert tmp_path.joinpath("post-ran.txt").read_text(encoding="utf-8") == "yes"
    assert [result.message for result in results] == ["PRE-FIRED"]


def test_run_legacy_sidecar_pre_validation_phase_omits_post_exit_error(
    tmp_path: Path,
) -> None:
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_pre() {",
                '  warn "PRE-FIRED"',
                "}",
                "legacy_post() {",
                '  printf "yes" > post-ran.txt',
                '  warn "POST-FIRED"',
                "  exit 23",
                "}",
                "register_validation_hook pre_validation legacy_pre",
                "register_validation_hook post_validation legacy_post",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(
        tmp_path,
        phase="pre_validation",
        count_post_validation=False,
    )

    assert log_lines == []
    assert tmp_path.joinpath("post-ran.txt").read_text(encoding="utf-8") == "yes"
    assert [result.message for result in results] == ["PRE-FIRED"]


def test_run_legacy_sidecar_pre_validation_phase_omits_post_stderr_from_pre_failure(
    tmp_path: Path,
) -> None:
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_pre() {",
                '  printf "pre-stderr" >&2',
                "  exit 23",
                "}",
                "legacy_post() {",
                '  printf "post-stderr" >&2',
                "}",
                "register_validation_hook pre_validation legacy_pre",
                "register_validation_hook post_validation legacy_post",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(
        tmp_path,
        phase="pre_validation",
        count_post_validation=False,
    )

    assert log_lines == []
    assert len(results) == 1
    assert results[0].severity is Severity.ERROR
    assert results[0].message == "legacy sidecar exited with code 23: pre-stderr"
    assert "post-stderr" not in results[0].message


def test_run_legacy_sidecar_extra_checks_phase_counts_post_output(tmp_path: Path) -> None:
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_pre() {",
                '  warn "PRE-FIRED"',
                "}",
                "legacy_extra() {",
                '  warn "EXTRA-FIRED"',
                "}",
                "legacy_post() {",
                '  warn "POST-FIRED"',
                "}",
                "register_validation_hook pre_validation legacy_pre",
                "register_validation_hook extra_checks legacy_extra",
                "register_validation_hook post_validation legacy_post",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(tmp_path, phase="extra_checks")

    assert log_lines == []
    assert [result.message for result in results] == ["EXTRA-FIRED", "POST-FIRED"]


def test_run_legacy_sidecar_default_dispatches_both_phases_and_post_output(
    tmp_path: Path,
) -> None:
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_pre() {",
                '  warn "PRE-FIRED"',
                "}",
                "legacy_extra() {",
                '  warn "EXTRA-FIRED"',
                "}",
                "legacy_post() {",
                '  warn "POST-FIRED"',
                "}",
                "register_validation_hook pre_validation legacy_pre",
                "register_validation_hook extra_checks legacy_extra",
                "register_validation_hook post_validation legacy_post",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(tmp_path)

    assert log_lines == []
    assert [result.message for result in results] == [
        "PRE-FIRED",
        "EXTRA-FIRED",
        "POST-FIRED",
    ]


def test_run_legacy_sidecar_default_ignores_ambient_dispatch_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCIENCE_LEGACY_DISPATCH_PHASE", "pre_validation")
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_pre() {",
                '  warn "PRE-FIRED"',
                "}",
                "legacy_extra() {",
                '  warn "EXTRA-FIRED"',
                "}",
                "legacy_post() {",
                '  warn "POST-FIRED"',
                "}",
                "register_validation_hook pre_validation legacy_pre",
                "register_validation_hook extra_checks legacy_extra",
                "register_validation_hook post_validation legacy_post",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(tmp_path)

    assert log_lines == []
    assert [result.message for result in results] == [
        "PRE-FIRED",
        "EXTRA-FIRED",
        "POST-FIRED",
    ]


def test_run_legacy_sidecar_extra_checks_counts_post_despite_ambient_count_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCIENCE_LEGACY_COUNT_POST_VALIDATION", "0")
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_extra() {",
                '  warn "EXTRA-FIRED"',
                "}",
                "legacy_post() {",
                '  warn "POST-FIRED"',
                "}",
                "register_validation_hook extra_checks legacy_extra",
                "register_validation_hook post_validation legacy_post",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(tmp_path, phase="extra_checks")

    assert log_lines == []
    assert [result.message for result in results] == ["EXTRA-FIRED", "POST-FIRED"]


def test_run_legacy_sidecar_default_ignores_project_env_control_overrides(
    tmp_path: Path,
) -> None:
    tmp_path.joinpath(".env").write_text(
        "\n".join(
            [
                "SCIENCE_LEGACY_DISPATCH_PHASE=pre_validation",
                "SCIENCE_LEGACY_COUNT_POST_VALIDATION=0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    tmp_path.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_pre() {",
                '  warn "PRE-FIRED"',
                "}",
                "legacy_extra() {",
                '  warn "EXTRA-FIRED"',
                "}",
                "legacy_post() {",
                '  warn "POST-FIRED"',
                "}",
                "register_validation_hook pre_validation legacy_pre",
                "register_validation_hook extra_checks legacy_extra",
                "register_validation_hook post_validation legacy_post",
                "",
            ]
        ),
        encoding="utf-8",
    )

    results, log_lines = run_legacy_sidecar(tmp_path)

    assert log_lines == []
    assert [result.message for result in results] == [
        "PRE-FIRED",
        "EXTRA-FIRED",
        "POST-FIRED",
    ]
