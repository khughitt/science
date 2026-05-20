"""Registry schema coverage for Python sidecar artifacts."""

import pytest
from pydantic import ValidationError

from science_tool.project_artifacts.registry_schema import Artifact, ExtensionKind


def _artifact_dict() -> dict:
    return {
        "name": "validate.py",
        "source": "data/validate.py",
        "install_target": "validate.py",
        "description": "Python structural validation for Science research projects",
        "content_type": "text",
        "newline": "lf",
        "mode": "0755",
        "consumer": "direct_execute",
        "header_protocol": {"kind": "shebang_comment", "comment_prefix": "#"},
        "extension_protocol": {
            "kind": "python_sidecar",
            "sidecar_path": "validate_local.py",
            "hook_namespace": "science_validate_hooks",
            "contract": "Import and execute project-local Python validation hooks.",
        },
        "mutation_policy": {
            "requires_clean_worktree": True,
            "commit_default": True,
            "transaction_kind": "temp_commit",
        },
        "version": "2026.05.20",
        "current_hash": "b" * 64,
        "previous_hashes": [],
        "migrations": [],
        "changelog": {"2026.05.20": "Add Python sidecar support."},
    }


def test_direct_execute_accepts_python_sidecar_round_trip() -> None:
    art = Artifact.model_validate(_artifact_dict())
    round_tripped = Artifact.model_validate(art.model_dump(mode="json"))

    assert round_tripped.extension_protocol.kind is ExtensionKind.PYTHON_SIDECAR


def test_science_loader_rejects_python_sidecar() -> None:
    art_dict = _artifact_dict()
    art_dict["consumer"] = "science_loader"

    with pytest.raises(ValidationError, match="python_sidecar.*science_loader"):
        Artifact.model_validate(art_dict)


def test_direct_execute_sourced_sidecar_still_round_trips() -> None:
    art_dict = _artifact_dict()
    art_dict["extension_protocol"] = {
        "kind": "sourced_sidecar",
        "sidecar_path": "validate.local.sh",
        "hook_namespace": "SCIENCE_VALIDATE_HOOKS",
        "contract": "Source project-local shell validation hooks.",
    }

    art = Artifact.model_validate(art_dict)
    round_tripped = Artifact.model_validate(art.model_dump(mode="json"))

    assert round_tripped.extension_protocol.kind is ExtensionKind.SOURCED_SIDECAR
