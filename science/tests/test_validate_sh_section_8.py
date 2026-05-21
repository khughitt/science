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
        entry.get("version") == "2026.05.11.2"
        and entry.get("hash") == "86dedcc6beebd74d4427b9202a1f083ef6de89b0eedbd06ae205db4b688087a4"
        for entry in prev
    )


def test_registry_migration_entry_for_2026_05_12_1() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    migrations = validate["migrations"]
    assert any(m.get("from") == "2026.05.11.2" and m.get("to") == "2026.05.12.1" for m in migrations)


def test_registry_changelog_entry_for_2026_05_12_1() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    assert "2026.05.12.1" in validate["changelog"]


def test_validate_sh_no_longer_contains_section_8_body() -> None:
    assert "unresolved markers" not in VALIDATE_SH.read_text(encoding="utf-8").lower()
