from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
import importlib
import os
import re
import shutil
import subprocess
import sys
import tomllib
import warnings
from pathlib import Path

import pytest

from science_tool.validate import Result, Severity
from science_tool.validate.checks import clear_checks_for_tests
from science_tool.validate.runner import run
from science_tool.validate.runner import RunResult


DiagnosticItem = tuple[str, str | None, int | None, str]

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
COMBINED_PROJECT = FIXTURES / "_combined"
REAL_PROJECTS_CONFIG = FIXTURES / "real_projects.txt"
VALIDATE_SH = REPO_ROOT / "src" / "science_tool" / "project_artifacts" / "data" / "validate.sh"
CHECK_MODULES = (
    "tooling",
    "manifest",
    "directory_structure",
    "research_scope",
    "document_structure",
    "hypotheses",
    "references",
    "papers",
    "unresolved_markers",
    "gap_analysis",
    "research_plan",
    "discussions",
    "prereg",
    "hypothesis_comparisons",
    "bias_audits",
    "notes",
    "graph",
    "tasks",
    "id_prefixes",
    "cross_references",
    "prose_lints",
    "annotations",
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_BASH_RESULT_RE = re.compile(r"^(?P<severity>WARN|ERROR):\s*(?P<message>.+)$")
_PATH_TOKEN_RE = re.compile(r"^(?P<path>(?:\.?/)?(?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]+)(?::(?P<line>\d+))?\b")

# validate.sh has no stable explicit rule IDs, and Python Result.rule is section-level
# (for example, "manifest" or "graph"). Phase 1 semantic parity therefore uses the
# diagnostic message text as the diagnostic key so message-level regressions stay visible.


def _extract_bash_diagnostic_items(stdout: str) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = []
    for raw_line in stdout.splitlines():
        line = _ANSI_RE.sub("", raw_line).strip()
        match = _BASH_RESULT_RE.match(line)
        if not match:
            continue

        message = match.group("message")
        path: str | None = None
        line_number: int | None = None
        path_match = _PATH_TOKEN_RE.match(message)
        if path_match:
            path = path_match.group("path").removeprefix("./")
            raw_line_number = path_match.group("line")
            line_number = int(raw_line_number) if raw_line_number is not None else None

        items.append((match.group("severity").lower(), path, line_number, message))
    return _sort_diagnostic_items(items)


def _extract_python_diagnostic_items(result: RunResult, project_root: Path) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = []
    for item in result.results:
        if item.severity is Severity.INFO:
            continue
        path = _normalize_result_path(item.path, project_root)
        items.append((item.severity.value, path, item.line, item.message))
    return _sort_diagnostic_items(items)


def _sort_diagnostic_items(items: list[DiagnosticItem]) -> list[DiagnosticItem]:
    return sorted(items, key=_diagnostic_item_sort_key)


def _diagnostic_item_sort_key(item: DiagnosticItem) -> tuple[str, bool, str, bool, int, str]:
    severity, path, line_number, diagnostic_key = item
    return (
        severity,
        path is None,
        path or "",
        line_number is None,
        line_number or 0,
        diagnostic_key,
    )


def _normalize_result_path(path: Path | None, project_root: Path) -> str | None:
    if path is None:
        return None
    if path.is_absolute():
        try:
            return path.relative_to(project_root).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def _assert_semantic_parity(
    bash_items: Sequence[DiagnosticItem],
    python_items: Sequence[DiagnosticItem],
    *,
    label: str,
) -> None:
    if bash_items == python_items:
        return

    bash_counter = Counter(bash_items)
    python_counter = Counter(python_items)
    bash_only = list((bash_counter - python_counter).elements())
    python_only = list((python_counter - bash_counter).elements())

    raise AssertionError(
        "\n".join(
            [
                f"Semantic parity mismatch for {label}",
                "",
                "bash - python:",
                *_format_items(_sort_diagnostic_items(bash_only)),
                "",
                "python - bash:",
                *_format_items(_sort_diagnostic_items(python_only)),
            ]
        )
    )


def _format_items(items: list[DiagnosticItem]) -> list[str]:
    if not items:
        return ["  <none>"]
    return [f"  {item!r}" for item in items]


def _run_bash_validate(project_root: Path, tmp_path: Path) -> str:
    copied_venv = project_root / ".venv"
    if copied_venv.exists():
        shutil.rmtree(copied_venv)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    uv_executable = shutil.which("uv")
    if uv_executable is None:
        raise AssertionError("uv executable not found on PATH before validate.sh isolation")
    _write_python3_stub(bin_dir)
    _write_science_stub(bin_dir, Path(uv_executable).resolve(strict=True))

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(bin_dir), "/bin", "/usr/sbin", "/sbin"])
    env["SCIENCE_VALIDATE_SKIP_DOTENV"] = "1"
    env.pop("SCIENCE_TOOL", None)
    env.pop("SCIENCE_TOOL_PATH", None)

    completed = subprocess.run(
        ["/usr/bin/bash", str(VALIDATE_SH)],
        cwd=project_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        raise AssertionError(
            f"validate.sh exited {completed.returncode}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout


def _write_python3_stub(bin_dir: Path) -> None:
    stub = bin_dir / "python3"
    stub.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f'exec "{sys.executable}" "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)


def _write_science_stub(bin_dir: Path, uv_executable: Path) -> None:
    stub = bin_dir / "science"
    stub.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f'exec "{uv_executable}" run --frozen --project "{REPO_ROOT}" science "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)


def _run_python_validate(project_root: Path) -> RunResult:
    _ensure_canonical_checks()
    return run(project_root, strict=False, verbose=False)


def _ensure_canonical_checks() -> None:
    clear_checks_for_tests()
    for module_name in CHECK_MODULES:
        importlib.reload(importlib.import_module(f"science_tool.validate.checks.{module_name}"))


def _load_project_paths(config_path: Path) -> list[Path]:
    paths: list[Path] = []
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        paths.append(Path(line).expanduser())
    return paths


def _resolved_project_paths(paths: list[Path]) -> list[Path]:
    resolved_paths: list[Path] = []
    for path in paths:
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            continue
        if resolved.is_dir():
            resolved_paths.append(resolved)
    return resolved_paths


def _warn_if_sidecars_present(project_root: Path, *, label: str) -> None:
    sidecars = sorted(
        path.relative_to(project_root).as_posix()
        for path in project_root.rglob("*")
        if path.name in {"validate.local.sh", "validate_local.py"}
    )
    if sidecars:
        warnings.warn(
            f"{label}: sidecar files were copied despite the isolated_copy exclude pattern: {sidecars}",
            UserWarning,
            stacklevel=2,
        )


def test_bash_diagnostic_extractor_keeps_only_warn_and_error_lines() -> None:
    stdout = "\n".join(
        [
            "\033[33mWARN: doc/a.md missing section: ## Summary\033[0m",
            "  advisory chatter",
            "\033[31mERROR: task t001 missing required field: aspects\033[0m",
            "\033[31mFAILED: 1 error(s), 1 warning(s)\033[0m",
        ]
    )

    assert _extract_bash_diagnostic_items(stdout) == [
        ("error", None, None, "task t001 missing required field: aspects"),
        ("warn", "doc/a.md", None, "doc/a.md missing section: ## Summary"),
    ]


def test_python_diagnostic_extractor_filters_info_and_normalizes_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    run_result = RunResult(
        results=[
            Result(Severity.INFO, None, None, "advisory chatter", "demo.info", None),
            Result(Severity.WARN, project_root / "doc" / "a.md", 7, "doc/a.md missing section", "demo.warn", None),
            Result(Severity.ERROR, Path("tasks/active.md"), None, "task t001 missing field", "demo.error", None),
        ],
        errors=1,
        warnings=1,
        infos=1,
    )

    assert _extract_python_diagnostic_items(run_result, project_root) == [
        ("error", "tasks/active.md", None, "task t001 missing field"),
        ("warn", "doc/a.md", 7, "doc/a.md missing section"),
    ]


def test_python_diagnostic_extractor_uses_message_as_diagnostic_key_not_result_rule(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    run_result = RunResult(
        results=[
            Result(
                Severity.ERROR,
                Path("manifest.yaml"),
                None,
                "manifest.yaml: missing required field: project_id",
                "manifest",
                None,
            ),
        ],
        errors=1,
        warnings=0,
        infos=0,
    )

    assert _extract_python_diagnostic_items(run_result, project_root) == [
        ("error", "manifest.yaml", None, "manifest.yaml: missing required field: project_id"),
    ]


def test_semantic_parity_assertion_reports_structured_diff() -> None:
    bash_items = [("warn", "doc/a.md", None, "bash only")]
    python_items = [("error", None, None, "python only")]

    with pytest.raises(AssertionError) as excinfo:
        _assert_semantic_parity(bash_items, python_items, label="fixture")

    message = str(excinfo.value)
    assert "Semantic parity mismatch for fixture" in message
    assert "bash - python" in message
    assert "python - bash" in message
    assert "bash only" in message
    assert "python only" in message


def test_project_path_config_loader_expands_user_and_ignores_comments(tmp_path: Path) -> None:
    config_path = tmp_path / "projects.txt"
    config_path.write_text(
        "\n".join(
            [
                "# comment",
                "",
                "~/example/project",
            ]
        ),
        encoding="utf-8",
    )

    assert _load_project_paths(config_path) == [Path("~/example/project").expanduser()]


def test_resolved_project_paths_keep_only_existing_directories(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    missing = tmp_path / "missing"

    assert _resolved_project_paths([missing, existing]) == [existing]


def test_sidecar_check_warns_without_failing(tmp_path: Path) -> None:
    tmp_path.joinpath("nested").mkdir()
    tmp_path.joinpath("nested", "validate.local.sh").write_text("echo sidecar\n", encoding="utf-8")

    with pytest.warns(UserWarning, match="sidecar files were copied"):
        _warn_if_sidecars_present(tmp_path, label="fixture")


def test_science_stub_uses_resolved_uv_executable_path(tmp_path: Path) -> None:
    uv_path = tmp_path / "tools" / "uv"
    uv_path.parent.mkdir()

    _write_science_stub(tmp_path, uv_path)

    stub = tmp_path / "science"
    assert stub.read_text(encoding="utf-8") == "\n".join(
        [
            "#!/bin/sh",
            f'exec "{uv_path}" run --frozen --project "{REPO_ROOT}" science "$@"',
            "",
        ]
    )


def test_default_pytest_collection_includes_this_parity_gate() -> None:
    relative_path = Path(__file__).resolve().relative_to(REPO_ROOT)
    pyproject = tomllib.loads(REPO_ROOT.joinpath("pyproject.toml").read_text(encoding="utf-8"))

    assert relative_path.parts[0] == "tests"
    assert "tests" in pyproject["tool"]["pytest"]["ini_options"]["testpaths"]


def test_combined_fixture_matches_bash_validate_semantics(
    isolated_copy: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    bash_project = isolated_copy(COMBINED_PROJECT)
    python_project = isolated_copy(COMBINED_PROJECT)

    bash_items = _extract_bash_diagnostic_items(_run_bash_validate(bash_project, tmp_path))
    python_items = _extract_python_diagnostic_items(_run_python_validate(python_project), python_project)

    _assert_semantic_parity(bash_items, python_items, label="combined fixture")


def test_real_downstream_projects_match_bash_validate_semantics(
    isolated_copy: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    project_paths = _resolved_project_paths(_load_project_paths(REAL_PROJECTS_CONFIG))
    if not project_paths:
        pytest.skip(f"No real downstream project paths from {REAL_PROJECTS_CONFIG} resolve")

    failures: list[str] = []
    for project_path in project_paths:
        bash_project = isolated_copy(project_path)
        python_project = isolated_copy(project_path)
        _warn_if_sidecars_present(bash_project, label=f"{project_path} bash copy")
        _warn_if_sidecars_present(python_project, label=f"{project_path} python copy")

        bash_items = _extract_bash_diagnostic_items(_run_bash_validate(bash_project, tmp_path))
        python_items = _extract_python_diagnostic_items(_run_python_validate(python_project), python_project)

        try:
            _assert_semantic_parity(bash_items, python_items, label=str(project_path))
        except AssertionError as exc:
            failures.append(str(exc))

    if failures:
        raise AssertionError("\n\n".join(failures))
