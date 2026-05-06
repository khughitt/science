"""unpin CLI verb: removes the matching pin; refuses if absent."""

import hashlib
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


@pytest.fixture
def project_with_pin(tmp_path, monkeypatch):
    # Reuse Task 25's setup pattern.
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    body = b"x\n"
    h = hashlib.sha256(body).hexdigest()
    (tmp_path / "validate.sh").write_bytes(
        b"#!/usr/bin/env bash\n# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.04.25\n" + f"# science-managed-source-sha256: {h}\n".encode() + body
    )
    (tmp_path / "science.yaml").write_text(
        "name: x\nmanaged_artifacts:\n  pins:\n"
        "    - name: validate.sh\n      pinned_to: '2026.04.25'\n" + f"      pinned_hash: {h}\n"
        "      rationale: r\n      revisit_by: '2026-06-01'\n",
        encoding="utf-8",
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
                "sidecar_path": "v.local",
                "hook_namespace": "X",
            },
            "mutation_policy": {},
            "version": "2026.05.10",
            "current_hash": "b" * 64,
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


def test_unpin_removes_entry(project_with_pin: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "unpin",
            "validate.sh",
            "--project-root",
            str(project_with_pin),
        ],
    )
    assert result.exit_code == 0, result.output
    contents = (project_with_pin / "science.yaml").read_text(encoding="utf-8")
    assert "validate.sh" not in contents


def test_unpin_refuses_if_no_pin(project_with_pin: Path) -> None:
    runner = CliRunner()
    runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "unpin",
            "validate.sh",
            "--project-root",
            str(project_with_pin),
        ],
    )
    result = runner.invoke(
        main,
        [
            "project",
            "artifacts",
            "unpin",
            "validate.sh",
            "--project-root",
            str(project_with_pin),
        ],
    )
    assert result.exit_code != 0
    assert "no pin found" in result.output.lower()
