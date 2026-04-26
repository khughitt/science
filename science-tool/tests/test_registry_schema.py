"""Schema-strictness for the managed-artifact registry."""

import pytest
from pydantic import ValidationError

from science_tool.project_artifacts.registry_schema import (
    Artifact,
    Consumer,
    ExtensionKind,
    HeaderKind,
    TransactionKind,
)


def _valid_validate_sh_dict() -> dict:
    return {
        "name": "validate.sh",
        "source": "data/validate.sh",
        "install_target": "validate.sh",
        "description": "Structural validation for Science research projects",
        "content_type": "text",
        "newline": "lf",
        "mode": "0755",
        "consumer": "direct_execute",
        "header_protocol": {"kind": "shebang_comment", "comment_prefix": "#"},
        "extension_protocol": {
            "kind": "sourced_sidecar",
            "sidecar_path": "validate.local.sh",
            "hook_namespace": "SCIENCE_VALIDATE_HOOKS",
            "contract": "...",
        },
        "mutation_policy": {
            "requires_clean_worktree": True,
            "commit_default": True,
            "transaction_kind": "temp_commit",
        },
        "version": "2026.04.26",
        "current_hash": "a" * 64,
        "previous_hashes": [],
        "migrations": [],
        "changelog": {"2026.04.26": "Initial."},
    }


def test_valid_artifact_parses() -> None:
    art = Artifact.model_validate(_valid_validate_sh_dict())
    assert art.name == "validate.sh"
    assert art.consumer is Consumer.DIRECT_EXECUTE
    assert art.header_protocol.kind is HeaderKind.SHEBANG_COMMENT
    assert art.extension_protocol.kind is ExtensionKind.SOURCED_SIDECAR
    assert art.mutation_policy.transaction_kind is TransactionKind.TEMP_COMMIT


def test_direct_execute_rejects_merged_sidecar() -> None:
    bad = _valid_validate_sh_dict()
    bad["extension_protocol"] = {"kind": "merged_sidecar", "sidecar_path": "x"}
    with pytest.raises(ValidationError, match="merged_sidecar.*direct_execute"):
        Artifact.model_validate(bad)


def test_native_tool_requires_generated_effective_file() -> None:
    bad = _valid_validate_sh_dict()
    bad["consumer"] = "native_tool"
    bad["extension_protocol"] = {"kind": "sourced_sidecar", "sidecar_path": "x"}
    with pytest.raises(ValidationError, match="native_tool.*generated_effective_file"):
        Artifact.model_validate(bad)


def test_current_hash_must_be_sha256_hex() -> None:
    bad = _valid_validate_sh_dict()
    bad["current_hash"] = "not-hex"
    with pytest.raises(ValidationError, match="current_hash"):
        Artifact.model_validate(bad)


def test_current_hash_not_in_previous_hashes() -> None:
    bad = _valid_validate_sh_dict()
    bad["previous_hashes"] = [{"version": "2026.04.20", "hash": bad["current_hash"]}]
    with pytest.raises(ValidationError, match="duplicate.*hash"):
        Artifact.model_validate(bad)


def test_mode_must_be_octal_string() -> None:
    bad = _valid_validate_sh_dict()
    bad["mode"] = "not-octal"
    with pytest.raises(ValidationError, match="mode"):
        Artifact.model_validate(bad)


def test_extension_protocol_none_allowed_with_rationale() -> None:
    art_dict = _valid_validate_sh_dict()
    art_dict["extension_protocol"] = {"kind": "none", "rationale": "Frozen by design."}
    art = Artifact.model_validate(art_dict)
    assert art.extension_protocol.kind is ExtensionKind.NONE
