"""validate.sh entry points.

scripts/validate.sh is a 5-line path-convenience shim. meta/validate.sh is the
materialized `validate.sh` managed artifact (byte-identical to the canonical
artifact the tool ships), since the science-meta project consumes the migrated
`science validate` CLI directly.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# The canonical, fully-rendered validate.sh artifact the tool materializes into
# consuming projects. meta/validate.sh must match it byte-for-byte; comparing
# against the shipped source (rather than a hard-coded copy) stays correct when
# the managed version/sha header is regenerated, and catches materialization drift.
CANONICAL_ARTIFACT = REPO_ROOT / "science" / "src" / "science_tool" / "project_artifacts" / "data" / "validate.sh"

EXPECTED_SHIM = (
    "#!/usr/bin/env bash\n"
    "# science-managed: shim for validate.sh (path convenience; not a managed artifact)\n"
    'here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
    'exec uv run --project "$here/../science" \\\n'
    '     science project artifacts exec validate.sh -- "$@"\n'
)


def test_scripts_validate_is_shim() -> None:
    p = REPO_ROOT / "scripts" / "validate.sh"
    assert p.exists(), "scripts/validate.sh should be the shim, not absent"
    assert p.read_text(encoding="utf-8") == EXPECTED_SHIM


def test_meta_validate_matches_materialized_artifact() -> None:
    p = REPO_ROOT / "meta" / "validate.sh"
    assert p.exists(), "meta/validate.sh should be the materialized artifact, not absent"
    assert p.read_text(encoding="utf-8") == CANONICAL_ARTIFACT.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ["meta/validate.sh", "scripts/validate.sh"])
def test_validate_sh_is_executable(path: str) -> None:
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
        "layout_version: 3\n"
        "knowledge_profiles:\n"
        "  local: local\n",
        encoding="utf-8",
    )
    (root / "CLAUDE.md").write_text("# Smoke\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# Smoke\n", encoding="utf-8")
    for d in ("doc", "specs", "tasks", "knowledge", "src", "entities"):
        (root / d).mkdir()
    (root / "tasks" / "active.md").write_text("# x\n", encoding="utf-8")


def test_meta_validate_smoke_runs(tmp_path: Path) -> None:
    """Smoke: invoking meta/validate.sh exits 0 on a minimal valid project."""
    _write_minimal_software_project(tmp_path)

    result = subprocess.run(
        ["bash", str(REPO_ROOT / "meta" / "validate.sh")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"meta validate exec failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
