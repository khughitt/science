"""validate.sh shim + managed-artifact registry bump."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

SCIENCE_ROOT = Path(__file__).resolve().parents[1]
VALIDATE_SH = SCIENCE_ROOT / "src/science_tool/project_artifacts/data/validate.sh"
REGISTRY_YAML = SCIENCE_ROOT / "src/science_tool/project_artifacts/registry.yaml"


def _body_hash(path: Path) -> str:
    """Match the registry's body_hash semantics: skip 4-line header."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    body = "".join(lines[4:])
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_validate_sh_is_cli_shim() -> None:
    text = VALIDATE_SH.read_text(encoding="utf-8")
    assert text.splitlines(keepends=True)[4:] == ['exec uv run science validate "$@"\n']


def test_registry_version_bumped() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    assert validate["version"] == "2026.05.21.1"


def test_registry_current_hash_matches_validate_body() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    assert validate["current_hash"] == _body_hash(VALIDATE_SH)


def test_registry_previous_hashes_grow() -> None:
    """The previous validate.sh version's hash is preserved in previous_hashes."""
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    prev = validate["previous_hashes"]
    assert any(
        entry.get("version") == "2026.05.12.1"
        and entry.get("hash") == "ec986621008863cffd749c59e5478722ca7d6f3ea75b497a4d49b801639e0be1"
        for entry in prev
    )


def test_registry_migration_entry_for_shim_transition() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    migrations = validate["migrations"]
    migration = next(
        (m for m in migrations if m.get("from") == "2026.05.12.1" and m.get("to") == "2026.05.21.1"),
        None,
    )
    assert migration is not None
    assert migration["kind"] == "byte_replace"
    assert migration["steps"] == []
    assert (
        migration["summary"] == "Migrate from in-project canonical body to packaged shim; project-local checks move to "
        "validate_local.py per docs/migration/2026-05-19-validate-local-sh-porting-guide.md."
    )


def test_registry_changelog_entry_for_shim_transition() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    assert validate["changelog"]["2026.05.21.1"] == (
        "Replace in-project canonical validate.sh body with packaged shim; project-local checks move "
        "to validate_local.py per docs/migration/2026-05-19-validate-local-sh-porting-guide.md."
    )


def test_registry_extension_protocol_uses_python_sidecar() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    protocol = validate["extension_protocol"]

    assert protocol["kind"] == "python_sidecar"
    assert protocol["sidecar_path"] == "validate_local.py"
    assert "hook_namespace" not in protocol
    assert "import" in protocol["contract"].lower()
    assert "@hook" in protocol["contract"]


def test_validate_sh_no_longer_contains_section_8_body() -> None:
    assert "unresolved markers" not in VALIDATE_SH.read_text(encoding="utf-8").lower()
