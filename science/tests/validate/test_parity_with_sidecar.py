from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import shutil

import pytest

from test_parity_canonical_body import (
    DiagnosticItem,
    REAL_PROJECTS_CONFIG,
    _assert_semantic_parity,
    _extract_bash_diagnostic_items,
    _extract_python_diagnostic_items,
    _load_project_paths,
    _resolved_project_paths,
    _run_bash_validate,
    _run_python_validate,
)


CopyProject = Callable[[Path], Path]
_LEGACY_SIDECAR_DEPRECATION_MESSAGES = {
    "validate.local.sh is deprecated; migrate validation hooks to validate_local.py",
    "validate.local.sh is deprecated and ignored because validate_local.py takes precedence",
}


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
    python_items = _without_python_only_sidecar_notices(
        _extract_python_diagnostic_items(_run_python_validate(python_project), python_project)
    )

    _assert_semantic_parity(bash_items, python_items, label=label)


def _without_python_only_sidecar_notices(items: list[DiagnosticItem]) -> list[DiagnosticItem]:
    # The Python runner reports legacy-sidecar migration notices as Results; bash validate.sh has no equivalent.
    return [
        item
        for item in items
        if not (item[0] == "warn" and item[1] is None and item[3] in _LEGACY_SIDECAR_DEPRECATION_MESSAGES)
    ]
