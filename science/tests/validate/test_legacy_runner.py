from __future__ import annotations

from pathlib import Path

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
