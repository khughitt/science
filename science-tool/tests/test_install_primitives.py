"""Install primitives: byte-copy + chmod + parent-dir mkdir."""

from pathlib import Path

from science_tool.project_artifacts.artifacts import (
    InstallResult,
    install_artifact,
)
from science_tool.project_artifacts.install_matrix import Action
from science_tool.project_artifacts.registry_schema import Artifact


def _art(tmp_canonical: Path) -> Artifact:
    return Artifact.model_validate(
        {
            "name": "validate.sh",
            "source": str(tmp_canonical.relative_to(tmp_canonical.parent)),
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
            "version": "2026.04.26",
            "current_hash": "a" * 64,
            "previous_hashes": [],
            "migrations": [],
            "changelog": {"2026.04.26": "x"},
        }
    )


def test_install_copies_bytes_and_sets_mode(tmp_path, monkeypatch) -> None:
    canonical_bytes = b"#!/usr/bin/env bash\necho hi\n"
    fake_canonical = tmp_path / "canonical" / "validate.sh"
    fake_canonical.parent.mkdir()
    fake_canonical.write_bytes(canonical_bytes)

    art = _art(fake_canonical)
    monkeypatch.setattr(
        "science_tool.project_artifacts.artifacts.canonical_path",
        lambda name: fake_canonical,
    )

    project_root = tmp_path / "project"
    project_root.mkdir()
    result = install_artifact(art, project_root)

    assert isinstance(result, InstallResult)
    assert result.action is Action.INSTALL
    target = project_root / "validate.sh"
    assert target.read_bytes() == canonical_bytes
    assert (target.stat().st_mode & 0o777) == 0o755


def test_install_creates_parent_directory(tmp_path, monkeypatch) -> None:
    canonical_bytes = b"hi\n"
    fake_canonical = tmp_path / "canonical" / "x"
    fake_canonical.parent.mkdir()
    fake_canonical.write_bytes(canonical_bytes)

    art = _art(fake_canonical)
    art = art.model_copy(update={"install_target": "deep/nested/x"})
    monkeypatch.setattr(
        "science_tool.project_artifacts.artifacts.canonical_path",
        lambda name: fake_canonical,
    )
    project_root = tmp_path / "project"
    project_root.mkdir()
    install_artifact(art, project_root)
    assert (project_root / "deep" / "nested" / "x").read_bytes() == canonical_bytes
