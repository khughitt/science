"""CLI update verb: flags wire into update_artifact correctly."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


@pytest.fixture
def project_with_stale_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a project with a stale validate.sh installed and a fresh canonical."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    new_body = b"echo new\n"
    new_h = hashlib.sha256(new_body).hexdigest()
    old_body = b"echo old\n"
    old_h = hashlib.sha256(old_body).hexdigest()

    canonical = tmp_path.parent / f"{tmp_path.name}-canonical" / "validate.sh"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_bytes(
        b"#!/usr/bin/env bash\n# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.05.10\n" + f"# science-managed-source-sha256: {new_h}\n".encode() + new_body
    )

    target = tmp_path / "validate.sh"
    target.write_bytes(
        b"#!/usr/bin/env bash\n# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.04.26\n" + f"# science-managed-source-sha256: {old_h}\n".encode() + old_body
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    from science_tool.project_artifacts.registry_schema import Artifact, Registry

    art = Artifact.model_validate(
        {
            "name": "validate.sh",
            "source": "data/validate.sh",
            "install_target": "validate.sh",
            "description": "d",
            "content_type": "text",
            "newline": "lf",
            "mode": "0755",
            "consumer": "direct_execute",
            "header_protocol": {"kind": "shebang_comment", "comment_prefix": "#"},
            "extension_protocol": {
                "kind": "sourced_sidecar",
                "sidecar_path": "validate.local.sh",
                "hook_namespace": "X",
            },
            "mutation_policy": {},
            "version": "2026.05.10",
            "current_hash": new_h,
            "previous_hashes": [{"version": "2026.04.26", "hash": old_h}],
            "migrations": [
                {
                    "from": "2026.04.26",
                    "to": "2026.05.10",
                    "kind": "byte_replace",
                    "summary": "x",
                    "steps": [],
                }
            ],
            "changelog": {"2026.05.10": "x"},
        }
    )
    monkeypatch.setattr("science_tool.project_artifacts.cli.default_registry", lambda: Registry(artifacts=[art]))
    monkeypatch.setattr("science_tool.project_artifacts.update.canonical_path", lambda name: canonical)
    return tmp_path


def test_update_clean_happy_path(project_with_stale_install: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "update",
            "validate.sh",
            "--project-root",
            str(project_with_stale_install),
        ],
    )
    assert result.exit_code == 0, result.output


def test_update_dirty_refused_without_allow_dirty(project_with_stale_install: Path) -> None:
    (project_with_stale_install / "unrelated.txt").write_text("dirty", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "update",
            "validate.sh",
            "--project-root",
            str(project_with_stale_install),
        ],
    )
    assert result.exit_code != 0
    assert "dirty worktree" in result.output


def test_update_allow_dirty_proceeds_when_no_conflict(project_with_stale_install: Path) -> None:
    (project_with_stale_install / "unrelated.txt").write_text("dirty", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "update",
            "validate.sh",
            "--project-root",
            str(project_with_stale_install),
            "--allow-dirty",
        ],
    )
    assert result.exit_code == 0, result.output


def test_update_allow_dirty_refuses_on_conflict(project_with_stale_install: Path) -> None:
    # Modify the artifact path itself (conflicts).
    (project_with_stale_install / "validate.sh").write_text("dirty content", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "update",
            "validate.sh",
            "--project-root",
            str(project_with_stale_install),
            "--allow-dirty",
        ],
    )
    assert result.exit_code != 0
    assert "path conflict" in result.output
