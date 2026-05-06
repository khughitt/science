"""pin CLI verb: writes pin entry with computed hash; refuses on duplicate."""

import hashlib
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


@pytest.fixture
def project_with_installed_artifact(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    body = b"echo body\n"
    h = hashlib.sha256(body).hexdigest()
    target = tmp_path / "validate.sh"
    target.write_bytes(
        b"#!/usr/bin/env bash\n# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.04.25\n" + f"# science-managed-source-sha256: {h}\n".encode() + body
    )
    (tmp_path / "science.yaml").write_text("name: x\n", encoding="utf-8")
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
                "sidecar_path": "v.local",
                "hook_namespace": "X",
            },
            "mutation_policy": {},
            "version": "2026.05.10",
            "current_hash": "a" * 64,
            "previous_hashes": [{"version": "2026.04.25", "hash": h}],
            "migrations": [],
            "changelog": {"2026.05.10": "x"},
        }
    )
    monkeypatch.setattr(
        "science_tool.project_artifacts.cli.default_registry",
        lambda: Registry(artifacts=[art]),
    )
    return tmp_path


def test_pin_writes_entry(project_with_installed_artifact: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "pin",
            "validate.sh",
            "--project-root",
            str(project_with_installed_artifact),
            "--rationale",
            "Awaiting CI rewrite.",
            "--revisit-by",
            "2026-06-01",
        ],
    )
    assert result.exit_code == 0, result.output
    contents = (project_with_installed_artifact / "science.yaml").read_text(encoding="utf-8")
    assert "validate.sh" in contents
    assert "Awaiting CI rewrite" in contents
    assert "2026-06-01" in contents


def test_pin_refuses_when_already_pinned(project_with_installed_artifact: Path) -> None:
    runner = CliRunner()
    runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "pin",
            "validate.sh",
            "--project-root",
            str(project_with_installed_artifact),
            "--rationale",
            "x",
            "--revisit-by",
            "2026-06-01",
        ],
    )
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "pin",
            "validate.sh",
            "--project-root",
            str(project_with_installed_artifact),
            "--rationale",
            "y",
            "--revisit-by",
            "2026-06-01",
        ],
    )
    assert result.exit_code != 0
    assert "already" in result.output.lower()
