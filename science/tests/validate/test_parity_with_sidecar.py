from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import shutil
from typing import Any

from click.testing import CliRunner
import pytest

from science_tool.cli import main
from test_parity_canonical_body import (
    DiagnosticItem,
    REAL_PROJECTS_CONFIG,
    _assert_semantic_parity,
    _extract_bash_diagnostic_items,
    _load_project_paths,
    _resolved_project_paths,
    _run_bash_validate,
    _sort_diagnostic_items,
)


CopyProject = Callable[[Path], Path]
_LEGACY_SIDECAR_DEPRECATION_RULE = "validate.sidecar.legacy_deprecated"


@pytest.fixture
def sidecar_included_copy(tmp_path: Path) -> CopyProject:
    copy_count = 0

    def copy_project(project_path: Path) -> Path:
        nonlocal copy_count
        copy_count += 1
        destination = tmp_path / f"{project_path.name}-{copy_count}"
        return shutil.copytree(project_path, destination, ignore=_ignore_transient_paths)

    return copy_project


def _ignore_transient_paths(_directory: str, names: list[str]) -> set[str]:
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
    return {name for name in names if name in ignored_names}


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
def test_synthetic_legacy_sidecars_match_bash_validate_semantics(
    sidecar_included_copy: CopyProject,
    tmp_path: Path,
    severity: str,
) -> None:
    source_project = _synthetic_project(tmp_path / "sources", severity=severity)

    _assert_sidecar_semantic_parity(
        source_project,
        copy_project=sidecar_included_copy,
        tmp_path=tmp_path,
        label=source_project.name,
    )


def test_real_downstream_projects_with_sidecars_match_bash_validate_semantics(
    sidecar_included_copy: CopyProject,
    tmp_path: Path,
) -> None:
    project_paths = _resolved_project_paths(_load_project_paths(REAL_PROJECTS_CONFIG))
    if not project_paths:
        pytest.skip(f"No real downstream project paths from {REAL_PROJECTS_CONFIG} resolve")

    failures: list[str] = []
    for project_path in project_paths:
        try:
            _assert_sidecar_semantic_parity(
                project_path,
                copy_project=sidecar_included_copy,
                tmp_path=tmp_path,
                label=str(project_path),
            )
        except AssertionError as exc:
            failures.append(str(exc))

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


def test_cli_validate_uses_bash_parity_environment(
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

    payload = _without_legacy_deprecation_results(_run_cli_validate(project))
    messages = {item[3] for item in _extract_cli_diagnostic_items(payload, project)}

    assert "dotenv was not skipped" not in messages
    assert "tool path leaked into sidecar" not in messages


def test_cli_validate_forces_sidecars_on_for_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _synthetic_project(tmp_path / "sources", severity="warn")
    monkeypatch.setenv("SCIENCE_VALIDATE_DISABLE_SIDECAR", "1")

    payload = _without_legacy_deprecation_results(_run_cli_validate(project))

    assert (
        "warn",
        None,
        None,
        "synthetic warn from validate.local.sh",
    ) in _extract_cli_diagnostic_items(payload, project)


def test_legacy_deprecation_filter_uses_raw_cli_rule_not_message(tmp_path: Path) -> None:
    message = "validate.local.sh is deprecated; migrate validation hooks to validate_local.py"
    payload = {
        "results": [
            {
                "severity": "warn",
                "path": None,
                "line": None,
                "message": message,
                "rule": "validate.sidecar.legacy_deprecated",
            },
            {
                "severity": "warn",
                "path": None,
                "line": None,
                "message": message,
                "rule": "local.same_text",
            },
        ]
    }

    assert _extract_cli_diagnostic_items(_without_legacy_deprecation_results(payload), tmp_path) == [
        ("warn", None, None, message),
    ]


def _assert_sidecar_semantic_parity(
    source_project: Path,
    *,
    copy_project: CopyProject,
    tmp_path: Path,
    label: str,
) -> None:
    bash_project = copy_project(source_project)
    python_project = copy_project(source_project)

    bash_items = _extract_bash_diagnostic_items(_run_bash_validate(bash_project, tmp_path))
    python_items = _extract_cli_diagnostic_items(
        _without_legacy_deprecation_results(_run_cli_validate(python_project)),
        python_project,
    )

    _assert_semantic_parity(bash_items, python_items, label=label)


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


def _without_legacy_deprecation_results(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
        "results": [item for item in payload["results"] if item.get("rule") != _LEGACY_SIDECAR_DEPRECATION_RULE],
    }


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
