import importlib
import os
import subprocess
from pathlib import Path

from science_tool.validate.checks.code_files import check_produced_by_unresolved
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)


def _ctx(root: Path) -> ValidateContext:
    root.joinpath("science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "knowledge" / "local").mkdir(parents=True)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def test_dangling_produced_by_is_flagged(tmp_path: Path) -> None:
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\nid: dataset:x\nkind: dataset\ntitle: X\n"
        "status: active\norigin: derived\ntier: use-now\nproduced_by: [code-file:missing.py]\n",
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    results = list(check_produced_by_unresolved(ctx))
    assert len(results) == 1
    assert results[0].rule == "code.produced-by-unresolved"
    assert results[0].severity is Severity.WARN


def test_resolved_produced_by_is_not_flagged(tmp_path: Path) -> None:
    code_dir = tmp_path / "code"
    code_dir.mkdir()
    (code_dir / "run.py").write_text(
        "# science:code\n# status: workflow-owned\n# science:end\n",
        encoding="utf-8",
    )
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\nid: dataset:x\nkind: dataset\ntitle: X\n"
        "status: active\norigin: derived\ntier: use-now\nproduced_by: [code-file:run.py]\n",
        encoding="utf-8",
    )
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(tmp_path, "commit", "-m", "init", env=env)
    ctx = _ctx(tmp_path)
    results = list(check_produced_by_unresolved(ctx))
    assert results == []


def test_check_registered_in_canonical_checks() -> None:
    # Reload the module to re-run @Check decorators and confirm the check is
    # wired into the registry the CLI validate runner iterates.
    import science_tool.validate.checks.code_files as code_files_mod
    from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests

    original = list(CANONICAL_CHECKS)
    try:
        clear_checks_for_tests()
        importlib.reload(code_files_mod)

        names = {entry.fn.__name__ for entry in CANONICAL_CHECKS}
        assert "check_produced_by_unresolved" in names
    finally:
        CANONICAL_CHECKS[:] = original
