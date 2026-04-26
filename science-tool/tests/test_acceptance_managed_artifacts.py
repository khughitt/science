"""End-to-end acceptance: install -> check -> modify -> update -> pin -> unpin -> exec.

Covers the spec's "What it looks like in practice" lifecycle plus health surfacing
and shim equivalence with the canonical executable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Path to the science-tool project (parent of tests/) — needed to run the CLI
# via `python -m science_tool` and to locate the canonical bytes for the shim
# equivalence test.
_SCIENCE_TOOL_PROJECT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SCIENCE_TOOL_PROJECT.parent


def _run_cli(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "science_tool", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_full_science_yaml(project: Path, name: str = "acceptance") -> None:
    """Write a science.yaml with every required field validate.sh checks for.

    The plan's draft test used a two-line manifest; the canonical validate.sh
    grew to require ``created``, ``last_modified``, ``status``, ``summary``,
    ``layout_version``, and a ``knowledge_profiles.local`` mapping. The plan
    explicitly permits expanding the fixture to satisfy the canonical.
    """
    project.joinpath("science.yaml").write_text(
        "\n".join(
            [
                f"name: {name}",
                "created: 2026-04-26",
                "last_modified: 2026-04-26",
                "status: active",
                "summary: Acceptance test fixture.",
                "profile: software",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: local",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _scaffold_software_project(project: Path) -> None:
    """Create the directory layout that validate.sh expects for a software profile."""
    project.joinpath("AGENTS.md").write_text("# Acceptance\n", encoding="utf-8")
    project.joinpath("CLAUDE.md").write_text("# Acceptance\n", encoding="utf-8")
    for d in ("doc", "specs", "tasks", "knowledge", "src"):
        project.joinpath(d).mkdir(exist_ok=True)
    project.joinpath("tasks", "active.md").write_text("# active\n", encoding="utf-8")


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    _write_full_science_yaml(repo)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)


def _check_status(project: Path, name: str) -> str:
    result = _run_cli(["project", "artifacts", "check", name, "--project-root", str(project), "--json"])
    assert result.returncode == 0, f"check failed:\n{result.stdout}\n{result.stderr}"
    return json.loads(result.stdout)["status"]


def test_full_lifecycle(tmp_path: Path) -> None:
    project = tmp_path / "acceptance"
    project.mkdir()
    _init_git(project)

    # 1. Fresh install.
    r = _run_cli(["project", "artifacts", "install", "validate.sh", "--project-root", str(project)])
    assert r.returncode == 0, r.stdout + r.stderr
    assert (project / "validate.sh").exists()
    assert _check_status(project, "validate.sh") == "current"

    # 2. Modify body -> locally_modified.
    target = project / "validate.sh"
    target.write_bytes(target.read_bytes() + b"# user added\n")
    assert _check_status(project, "validate.sh") == "locally_modified"

    # 3. Force-update -> current.
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "user mod"], cwd=project, check=True)
    r = _run_cli(
        [
            "project",
            "artifacts",
            "update",
            "validate.sh",
            "--project-root",
            str(project),
            "--force",
            "--yes",
        ]
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _check_status(project, "validate.sh") == "current"

    # 4. Pin -> pinned.
    r = _run_cli(
        [
            "project",
            "artifacts",
            "pin",
            "validate.sh",
            "--project-root",
            str(project),
            "--rationale",
            "acceptance test",
            "--revisit-by",
            "2099-12-31",
        ]
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _check_status(project, "validate.sh") == "pinned"

    # 5. Modify under a pin -> pinned_but_locally_modified.
    target.write_bytes(target.read_bytes() + b"# more user changes\n")
    assert _check_status(project, "validate.sh") == "pinned_but_locally_modified"

    # 6. Unpin -> locally_modified (the body is still changed).
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "more user mod"], cwd=project, check=True)
    r = _run_cli(["project", "artifacts", "unpin", "validate.sh", "--project-root", str(project)])
    assert r.returncode == 0, r.stdout + r.stderr
    assert _check_status(project, "validate.sh") == "locally_modified"

    # 7. Refresh + exec runs cleanly. exec dispatches into bash data/validate.sh,
    # so the project must satisfy the canonical's structural checks.
    r = _run_cli(
        [
            "project",
            "artifacts",
            "update",
            "validate.sh",
            "--project-root",
            str(project),
            "--force",
            "--yes",
        ]
    )
    assert r.returncode == 0, r.stdout + r.stderr
    _scaffold_software_project(project)

    env = os.environ.copy()
    # Tell validate.sh where the science-tool project lives so its
    # `resolve_science_tool` check passes inside the temp project.
    env["SCIENCE_TOOL_PATH"] = str(_SCIENCE_TOOL_PROJECT)
    exec_result = subprocess.run(
        [sys.executable, "-m", "science_tool", "project", "artifacts", "exec", "validate.sh", "--"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    # exec replaces the process with bash data/validate.sh; exit code 0 means
    # validation passed against our minimal project.
    assert exec_result.returncode == 0, exec_result.stdout + exec_result.stderr


def test_health_surfaces_managed_artifact_status(tmp_path: Path) -> None:
    """End-to-end via science-tool health: managed_artifacts present, total_issues right."""
    from science_tool.graph.health import build_health_report

    project = tmp_path / "health"
    project.mkdir()
    project.joinpath("science.yaml").write_text("name: x\n", encoding="utf-8")
    report = build_health_report(project)
    assert "managed_artifacts" in report
    missing = [f for f in report["managed_artifacts"] if f["status"] == "missing"]
    assert len(missing) >= 1


def test_shim_invocation_matches_direct_canonical(tmp_path: Path) -> None:
    """meta/validate.sh and direct canonical produce the same exit code on the same project."""
    project = tmp_path / "shim"
    project.mkdir()
    _write_full_science_yaml(project, name="shim")
    _scaffold_software_project(project)

    env = os.environ.copy()
    env["SCIENCE_TOOL_PATH"] = str(_SCIENCE_TOOL_PROJECT)

    via_shim = subprocess.run(
        ["bash", str(_REPO_ROOT / "meta" / "validate.sh")],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    via_canonical = subprocess.run(
        [
            "bash",
            str(_SCIENCE_TOOL_PROJECT / "src" / "science_tool" / "project_artifacts" / "data" / "validate.sh"),
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    # Output may differ in line ordering of warnings; the exit code is the contract.
    assert via_shim.returncode == via_canonical.returncode
