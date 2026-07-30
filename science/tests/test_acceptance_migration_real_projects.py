from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.findings.cli import run_acceptance_migration


PROJECTS = (
    (Path(__file__).resolve().parents[2] / "meta", 2),
    (Path("~/d/natural-systems").expanduser(), 6),
    (Path("~/d/cancer/cancer-types/multiple-myeloma").expanduser(), 24),
    (Path("~/d/health/processes/post-acute-infection").expanduser(), 20),
)


def git_status(project: Path) -> bytes:
    return subprocess.run(
        ["git", "-C", str(project), "status", "--porcelain=v1", "-z"],
        check=True,
        capture_output=True,
    ).stdout


@pytest.mark.real_projects
@pytest.mark.parametrize(("project", "expected_entries"), PROJECTS)
def test_acceptance_migration_dry_run_is_nonblocking_on_real_project(
    project: Path,
    expected_entries: int,
) -> None:
    if not project.is_dir():
        display_path = str(project).replace(str(Path.home()), "~")
        pytest.skip(f"configured project is absent: {display_path}")

    config_path = project / "science.yaml"
    before_config = config_path.read_bytes()
    before_status = git_status(project)
    try:
        assert not (project / "doc" / "audits" / "cases").exists()
        migration = run_acceptance_migration(project)

        assert len(migration.entries) == expected_entries
        unexpected = [
            (entry.entry_index, entry.verdict, entry.detail)
            for entry in migration.entries
            if entry.verdict not in {"migrated", "already-current"}
        ]
        assert not unexpected
        assert migration.can_apply
    finally:
        assert config_path.read_bytes() == before_config
        assert git_status(project) == before_status
