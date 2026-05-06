"""Update verb (no-migration path): byte-replace + .pre-update.bak + commit."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from science_tool.project_artifacts.registry_schema import Artifact
from science_tool.project_artifacts.update import UpdateError, update_artifact


def _commit_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)


def _art(current_h: str, prev_h: str) -> Artifact:
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
            "current_hash": current_h,
            "previous_hashes": [{"version": "2026.04.26", "hash": prev_h}],
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


def _install_stale(repo: Path, body: bytes, prev_h: str) -> None:
    target = repo / "validate.sh"
    target.write_bytes(
        b"#!/usr/bin/env bash\n"
        b"# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.04.26\n" + f"# science-managed-source-sha256: {prev_h}\n".encode() + body
    )


def test_clean_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _commit_init(tmp_path)
    canonical_body = b"echo new\n"
    canonical_h = hashlib.sha256(canonical_body).hexdigest()
    fake_canonical = tmp_path / "canonical"
    fake_canonical.parent.mkdir(parents=True, exist_ok=True)
    fake_canonical.write_bytes(
        b"#!/usr/bin/env bash\n"
        b"# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.05.10\n"
        + f"# science-managed-source-sha256: {canonical_h}\n".encode()
        + canonical_body
    )
    prev_body = b"echo old\n"
    prev_h = hashlib.sha256(prev_body).hexdigest()
    _install_stale(tmp_path, prev_body, prev_h)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    monkeypatch.setattr("science_tool.project_artifacts.update.canonical_path", lambda name: fake_canonical)

    update_artifact(_art(canonical_h, prev_h), tmp_path)

    target = tmp_path / "validate.sh"
    assert (
        hashlib.sha256(target.read_bytes()[len(b"#!/usr/bin/env bash\n") + 3 * 80 :]).hexdigest() != prev_h
    )  # body changed
    assert (tmp_path / "validate.sh.pre-update.bak").exists()
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout
    assert "refresh validate.sh" in log


def test_dirty_worktree_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _commit_init(tmp_path)
    canonical_body = b"echo new\n"
    canonical_h = hashlib.sha256(canonical_body).hexdigest()
    fake_canonical = tmp_path / "canonical"
    fake_canonical.write_bytes(
        b"#!/usr/bin/env bash\n# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.05.10\n"
        + f"# science-managed-source-sha256: {canonical_h}\n".encode()
        + canonical_body
    )
    prev_body = b"echo old\n"
    prev_h = hashlib.sha256(prev_body).hexdigest()
    _install_stale(tmp_path, prev_body, prev_h)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    # Make worktree dirty.
    (tmp_path / "unrelated.txt").write_text("dirty", encoding="utf-8")
    monkeypatch.setattr("science_tool.project_artifacts.update.canonical_path", lambda name: fake_canonical)
    with pytest.raises(UpdateError, match="dirty worktree"):
        update_artifact(_art(canonical_h, prev_h), tmp_path)


def test_locally_modified_refuses_without_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _commit_init(tmp_path)
    canonical_body = b"echo new\n"
    canonical_h = hashlib.sha256(canonical_body).hexdigest()
    fake_canonical = tmp_path / "canonical"
    fake_canonical.write_bytes(
        b"#!/usr/bin/env bash\n# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.05.10\n"
        + f"# science-managed-source-sha256: {canonical_h}\n".encode()
        + canonical_body
    )
    # Install a file with header but body matches no known version.
    target = tmp_path / "validate.sh"
    target.write_bytes(
        b"#!/usr/bin/env bash\n# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.04.26\n"
        + f"# science-managed-source-sha256: {'a' * 64}\n".encode()
        + b"echo locally_modified\n"
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    monkeypatch.setattr("science_tool.project_artifacts.update.canonical_path", lambda name: fake_canonical)
    with pytest.raises(UpdateError, match="locally modified"):
        update_artifact(_art(canonical_h, "0" * 64), tmp_path)
