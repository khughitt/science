"""Update with project_action migration: success applies + commits + lists steps;
failure restores snapshot + leaves artifact at old version."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from science_tool.project_artifacts.registry_schema import Artifact
from science_tool.project_artifacts.update import UpdateError, update_artifact


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, will_succeed: bool) -> Artifact:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    new_body, old_body = b"echo new\n", b"echo old\n"
    new_h, old_h = hashlib.sha256(new_body).hexdigest(), hashlib.sha256(old_body).hexdigest()

    fake_canonical = tmp_path.parent / f"{tmp_path.name}-canonical" / "validate.sh"
    fake_canonical.parent.mkdir(parents=True, exist_ok=True)
    fake_canonical.write_bytes(
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

    monkeypatch.setattr("science_tool.project_artifacts.update.canonical_path", lambda name: fake_canonical)

    apply_body = "touch will_apply.flag\n" if will_succeed else "exit 1\n"
    return Artifact.model_validate(
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
                    "kind": "project_action",
                    "summary": "x",
                    "steps": [
                        {
                            "id": "s1",
                            "description": "d",
                            "touched_paths": ["will_apply.flag"],
                            "reversible": False,
                            "idempotent": True,
                            "impl": {
                                "kind": "bash",
                                "shell": "bash",
                                "working_dir": ".",
                                "timeout_seconds": 5,
                                "check": "test -f will_apply.flag && exit 0 || exit 1\n",
                                "apply": apply_body,
                            },
                        }
                    ],
                }
            ],
            "changelog": {"2026.05.10": "x"},
        }
    )


def test_with_migration_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    art = _setup(tmp_path, monkeypatch, will_succeed=True)
    result = update_artifact(art, tmp_path, auto_apply=True)
    assert "s1" in result.migrated_steps
    assert (tmp_path / "will_apply.flag").exists()
    assert (tmp_path / "validate.sh.pre-update.bak").exists()


def test_failed_migration_restores_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    art = _setup(tmp_path, monkeypatch, will_succeed=False)
    target_before = (tmp_path / "validate.sh").read_bytes()
    with pytest.raises(UpdateError, match="migration"):
        update_artifact(art, tmp_path, auto_apply=True)
    # Artifact at old version; flag file not present.
    assert (tmp_path / "validate.sh").read_bytes() == target_before
    assert not (tmp_path / "will_apply.flag").exists()
    assert not (tmp_path / "validate.sh.pre-update.bak").exists()
