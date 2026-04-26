"""meta/validate.sh and scripts/validate.sh are byte-identical 5-line shims."""
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_SHIM = (
    "#!/usr/bin/env bash\n"
    "# science-managed: shim for validate.sh (path convenience; not a managed artifact)\n"
    'here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
    'exec uv run --project "$here/../science-tool" \\\n'
    '     science-tool project artifacts exec validate.sh -- "$@"\n'
)


@pytest.mark.parametrize("path", ["meta/validate.sh", "scripts/validate.sh"])
def test_shim_is_exact(path: str) -> None:
    p = REPO_ROOT / path
    assert p.exists(), f"{path} should be the shim, not absent"
    assert p.read_text(encoding="utf-8") == EXPECTED_SHIM


@pytest.mark.parametrize("path", ["meta/validate.sh", "scripts/validate.sh"])
def test_shim_is_executable(path: str) -> None:
    p = REPO_ROOT / path
    assert p.stat().st_mode & 0o111, f"{path} must be executable"


def _write_minimal_software_project(root: Path) -> None:
    """Write the minimum project layout the canonical validate.sh accepts.

    The canonical script (project_artifacts/data/validate.sh) requires:
      - science.yaml with fields: name, created, last_modified, status,
        summary, profile, layout_version, plus knowledge_profiles.local.
      - Required dirs: specs/, doc/, knowledge/, tasks/, plus the
        profile-specific code root (`src/` for software, `code/` for research).
      - Required files: CLAUDE.md, AGENTS.md.
    The `software` profile skips the research-only papers/data/models/results.
    """
    (root / "science.yaml").write_text(
        "name: smoke\n"
        "created: '2026-04-26'\n"
        "last_modified: '2026-04-26'\n"
        "status: active\n"
        "summary: smoke fixture\n"
        "profile: software\n"
        "layout_version: 1\n"
        "knowledge_profiles:\n"
        "  local: local\n",
        encoding="utf-8",
    )
    (root / "CLAUDE.md").write_text("# Smoke\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# Smoke\n", encoding="utf-8")
    for d in ("doc", "specs", "tasks", "knowledge", "src"):
        (root / d).mkdir()
    (root / "tasks" / "active.md").write_text("# x\n", encoding="utf-8")


def test_meta_shim_smoke_runs(tmp_path: Path) -> None:
    """Smoke: invoking meta/validate.sh exits with same status as direct canonical run."""
    _write_minimal_software_project(tmp_path)

    result = subprocess.run(
        ["bash", str(REPO_ROOT / "meta" / "validate.sh")],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        f"meta shim exec failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
