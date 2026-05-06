"""End-to-end install CLI: every install-matrix row exercised through the verb."""

import hashlib
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


@pytest.fixture
def project_with_registry(tmp_path, monkeypatch):
    """Create a tmp project root + a fake registry containing one artifact."""
    canonical = tmp_path / "canonical" / "validate.sh"
    canonical.parent.mkdir()
    body = b"echo body\n"
    body_sha = hashlib.sha256(body).hexdigest()
    canonical_bytes = (
        b"#!/usr/bin/env bash\n"
        b"# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.04.26\n" + f"# science-managed-source-sha256: {body_sha}\n".encode() + body
    )
    canonical.write_bytes(canonical_bytes)

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
                "hook_namespace": "SCIENCE_VALIDATE_HOOKS",
            },
            "mutation_policy": {},
            "version": "2026.04.26",
            "current_hash": body_sha,
            "previous_hashes": [],
            "migrations": [],
            "changelog": {"2026.04.26": "x"},
        }
    )
    monkeypatch.setattr("science_tool.project_artifacts.cli.default_registry", lambda: Registry(artifacts=[art]))
    monkeypatch.setattr("science_tool.project_artifacts.artifacts.canonical_path", lambda name: canonical)
    project_root = tmp_path / "project"
    project_root.mkdir()
    return project_root


def test_install_into_empty_project(project_with_registry: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "install",
            "validate.sh",
            "--project-root",
            str(project_with_registry),
        ],
    )
    assert result.exit_code == 0, result.output
    target = project_with_registry / "validate.sh"
    assert target.exists()
    assert (target.stat().st_mode & 0o777) == 0o755


def test_install_no_op_when_current(project_with_registry: Path) -> None:
    runner = CliRunner()
    runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "install",
            "validate.sh",
            "--project-root",
            str(project_with_registry),
        ],
    )
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "install",
            "validate.sh",
            "--project-root",
            str(project_with_registry),
        ],
    )
    assert result.exit_code == 0
    assert "no_op" in result.output.lower() or "current" in result.output.lower()


def test_install_refuses_locally_modified(project_with_registry: Path) -> None:
    runner = CliRunner()
    runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "install",
            "validate.sh",
            "--project-root",
            str(project_with_registry),
        ],
    )
    target = project_with_registry / "validate.sh"
    raw = target.read_bytes()
    target.write_bytes(raw + b"# locally added\n")  # body change
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "install",
            "validate.sh",
            "--project-root",
            str(project_with_registry),
        ],
    )
    assert result.exit_code != 0
    assert "locally" in result.output.lower() or "diff" in result.output.lower()
