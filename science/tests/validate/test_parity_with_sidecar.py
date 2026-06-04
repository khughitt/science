from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import shutil
from typing import Any

from click.testing import CliRunner
import pytest

from _copy_filters import oversized_payload_names
from science_tool.cli import main
from test_parity_canonical_body import (
    DiagnosticItem,
    REAL_PROJECTS_CONFIG,
    _load_project_paths,
    _resolved_project_paths,
    _run_bash_validate,
    _sort_diagnostic_items,
)


CopyProject = Callable[[Path], Path]
_LEGACY_SIDECAR_REMOVED_RULE = "validate.sidecar.legacy_removed"
_PORTING_GUIDE = "docs/migration/2026-05-19-validate-local-sh-porting-guide.md"
_REMOVED_MESSAGE = f"validate.local.sh is no longer supported; migrate it using {_PORTING_GUIDE}"


@pytest.fixture
def sidecar_included_copy(tmp_path: Path) -> CopyProject:
    copy_count = 0

    def copy_project(project_path: Path) -> Path:
        nonlocal copy_count
        copy_count += 1
        destination = tmp_path / f"{project_path.name}-{copy_count}"
        return shutil.copytree(project_path, destination, ignore=_ignore_transient_paths)

    return copy_project


def _ignore_transient_paths(directory: str, names: list[str]) -> set[str]:
    ignored_names = {
        ".git",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "node_modules",
    }
    transient = {name for name in names if name in ignored_names}
    return transient | oversized_payload_names(directory, names)


def _synthetic_project(root: Path, *, severity: str) -> Path:
    project = root / f"synthetic-{severity}"
    project.mkdir(parents=True)
    project.joinpath("science.yaml").write_text(
        "\n".join(
            [
                f"id: synthetic-{severity}",
                f"name: Synthetic {severity} sidecar parity fixture",
                "created: 2026-05-20",
                "last_modified: 2026-05-20",
                "status: active",
                "summary: Synthetic project for sidecar parity tests.",
                "profile: research",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: local",
                "  curated: []",
                "ontologies: []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    project.joinpath(".env").write_text("SCIENCE_TOOL_PATH=/tmp/science\n", encoding="utf-8")
    project.joinpath("AGENTS.md").write_text("# Instructions\n", encoding="utf-8")
    project.joinpath("CLAUDE.md").write_text("# Instructions\n", encoding="utf-8")
    project.joinpath("pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                f'name = "synthetic-{severity}-sidecar-parity"',
                'version = "0.1.0"',
                'description = "Synthetic science validate sidecar parity fixture."',
                "",
            ]
        ),
        encoding="utf-8",
    )
    for directory in [
        "code",
        "data",
        "doc",
        "knowledge",
        "models",
        "papers",
        "results",
        "specs",
        "tasks",
    ]:
        project.joinpath(directory).mkdir()
    project.joinpath("tasks", "active.md").write_text("# Active Tasks\n", encoding="utf-8")
    project.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_extra() {",
                f'  {severity} "synthetic {severity} from validate.local.sh"',
                "}",
                "register_validation_hook extra_checks legacy_extra",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return project


@pytest.mark.parametrize("severity", ["warn", "error"])
def test_synthetic_legacy_sidecars_report_phase3_hard_error(
    sidecar_included_copy: CopyProject,
    tmp_path: Path,
    severity: str,
) -> None:
    source_project = _synthetic_project(tmp_path / "sources", severity=severity)
    bash_project = sidecar_included_copy(source_project)
    python_project = sidecar_included_copy(source_project)

    bash_payload = json.loads(_run_bash_validate(bash_project, tmp_path, "--format", "json"))
    python_payload = _run_cli_validate(python_project)

    assert _phase3_legacy_removed_items(bash_payload) == [
        ("error", None, None, _REMOVED_MESSAGE),
    ]
    assert _phase3_legacy_removed_items(python_payload) == [
        ("error", None, None, _REMOVED_MESSAGE),
    ]


@pytest.mark.real_projects
def test_real_downstream_projects_with_sidecars_report_phase3_hard_error(
    sidecar_included_copy: CopyProject,
    tmp_path: Path,
) -> None:
    project_paths = _resolved_project_paths(_load_project_paths(REAL_PROJECTS_CONFIG))
    if not project_paths:
        pytest.skip(f"No real downstream project paths from {REAL_PROJECTS_CONFIG} resolve")

    failures: list[str] = []
    for project_path in project_paths:
        if not project_path.joinpath("validate.local.sh").exists():
            continue
        bash_project = sidecar_included_copy(project_path)
        python_project = sidecar_included_copy(project_path)

        bash_items = _phase3_legacy_removed_items(
            json.loads(_run_bash_validate(bash_project, tmp_path, "--format", "json"))
        )
        python_items = _phase3_legacy_removed_items(_run_cli_validate(python_project))
        expected_items = [("error", None, None, _REMOVED_MESSAGE)]
        if bash_items != expected_items:
            failures.append(f"{project_path} bash hard-error items: {bash_items!r}")
        if python_items != expected_items:
            failures.append(f"{project_path} python hard-error items: {python_items!r}")

    if failures:
        raise AssertionError("\n\n".join(failures))


def test_cli_diagnostic_extractor_filters_info_and_normalizes_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    payload = {
        "results": [
            {
                "severity": "info",
                "path": None,
                "line": None,
                "message": "advisory chatter",
            },
            {
                "severity": "warn",
                "path": str(project_root / "doc" / "a.md"),
                "line": 7,
                "message": "doc/a.md missing section",
            },
            {
                "severity": "error",
                "path": "tasks/active.md",
                "line": None,
                "message": "task t001 missing field",
            },
        ]
    }

    assert _extract_cli_diagnostic_items(payload, project_root) == [
        ("error", "tasks/active.md", None, "task t001 missing field"),
        ("warn", "doc/a.md", 7, "doc/a.md missing section"),
    ]


def test_cli_validate_does_not_execute_legacy_sidecar_environment_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _synthetic_project(tmp_path / "sources", severity="warn")
    project.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_extra() {",
                '  if [ "${SCIENCE_VALIDATE_SKIP_DOTENV:-}" != "1" ]; then',
                '    warn "dotenv was not skipped"',
                "  fi",
                '  if [ -n "${SCIENCE_TOOL:-}" ] || [ -n "${SCIENCE_TOOL_PATH:-}" ]; then',
                '    warn "tool path leaked into sidecar"',
                "  fi",
                "}",
                "register_validation_hook extra_checks legacy_extra",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_TOOL", "ambient-science")
    monkeypatch.setenv("SCIENCE_TOOL_PATH", "ambient-science-path")

    payload = _run_cli_validate(project)
    messages = {item[3] for item in _extract_cli_diagnostic_items(payload, project)}

    assert _phase3_legacy_removed_items(payload) == [("error", None, None, _REMOVED_MESSAGE)]
    assert "dotenv was not skipped" not in messages
    assert "tool path leaked into sidecar" not in messages


def test_cli_validate_hard_errors_despite_ambient_disable_sidecar_env_for_parity_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _synthetic_project(tmp_path / "sources", severity="warn")
    monkeypatch.setenv("SCIENCE_VALIDATE_DISABLE_SIDECAR", "1")

    payload = _run_cli_validate(project)

    assert _phase3_legacy_removed_items(payload) == [("error", None, None, _REMOVED_MESSAGE)]
    assert (
        "warn",
        None,
        None,
        "synthetic warn from validate.local.sh",
    ) not in _extract_cli_diagnostic_items(payload, project)


def test_legacy_removed_filter_uses_raw_cli_rule_not_message(tmp_path: Path) -> None:
    message = _REMOVED_MESSAGE
    payload = {
        "results": [
            {
                "severity": "error",
                "path": None,
                "line": None,
                "message": message,
                "rule": "validate.sidecar.legacy_removed",
            },
            {
                "severity": "error",
                "path": None,
                "line": None,
                "message": message,
                "rule": "local.same_text",
            },
        ]
    }

    assert _extract_cli_diagnostic_items(_without_legacy_removed_results(payload), tmp_path) == [
        ("error", None, None, message),
    ]


def _run_cli_validate(project_root: Path) -> dict[str, Any]:
    result = CliRunner().invoke(
        main,
        ["validate", "--format", "json", "--project-root", str(project_root)],
        env=_cli_validate_env(),
    )
    if result.exit_code not in {0, 1}:
        raise AssertionError(f"science validate exited {result.exit_code}\n{result.output}")
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        raise AssertionError(f"science validate raised {result.exception!r}\n{result.output}") from result.exception
    return dict(json.loads(result.output))


def _cli_validate_env() -> dict[str, str | None]:
    return {
        "PATH": os.pathsep.join(["/bin", "/usr/sbin", "/sbin"]),
        "SCIENCE_VALIDATE_DISABLE_SIDECAR": None,
        "SCIENCE_VALIDATE_SKIP_DOTENV": "1",
        "SCIENCE_TOOL": None,
        "SCIENCE_TOOL_PATH": None,
    }


def _without_legacy_removed_results(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
        "results": [item for item in payload["results"] if item.get("rule") != _LEGACY_SIDECAR_REMOVED_RULE],
    }


def _phase3_legacy_removed_items(payload: dict[str, Any]) -> list[DiagnosticItem]:
    return _extract_cli_diagnostic_items(
        {
            **payload,
            "results": [item for item in payload["results"] if item.get("rule") == _LEGACY_SIDECAR_REMOVED_RULE],
        },
        Path(),
    )


def _extract_cli_diagnostic_items(payload: dict[str, Any], project_root: Path) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = []
    for item in payload["results"]:
        if item["severity"] == "info":
            continue
        items.append(
            (
                item["severity"],
                _normalize_cli_path(item["path"], project_root),
                item["line"],
                item["message"],
            )
        )
    return _sort_diagnostic_items(items)


def _normalize_cli_path(path: str | None, project_root: Path) -> str | None:
    if path is None:
        return None
    result_path = Path(path)
    if result_path.is_absolute():
        try:
            return result_path.relative_to(project_root).as_posix()
        except ValueError:
            return result_path.as_posix()
    return result_path.as_posix()
