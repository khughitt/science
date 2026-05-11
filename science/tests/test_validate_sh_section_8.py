"""validate.sh Section 8 + managed-artifact registry bump."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
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


def test_section_8_passes_ignore_lifted() -> None:
    text = VALIDATE_SH.read_text(encoding="utf-8")
    section_idx = text.find("8. Unresolved annotation markers")
    assert section_idx >= 0
    section_end = text.find("# ─── 9.", section_idx)
    section = text[section_idx:section_end]
    assert "--ignore-lifted" in section


def test_registry_version_bumped() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    assert validate["version"] == "2026.05.11.2"


def test_registry_current_hash_matches_validate_body() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    assert validate["current_hash"] == _body_hash(VALIDATE_SH)


def test_registry_previous_hashes_grow() -> None:
    """The pre-P3.2 version's hash is preserved in previous_hashes."""
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    prev = validate["previous_hashes"]
    assert any(
        entry.get("version") == "2026.05.11.1"
        and entry.get("hash") == "171dada621d6741d0deb7d592ec6ac92f4ceb10d39941d6dc06e8d898824cf23"
        for entry in prev
    )


def test_registry_migration_entry_for_2026_05_11_2() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    migrations = validate["migrations"]
    assert any(
        m.get("from") == "2026.05.11.1" and m.get("to") == "2026.05.11.2"
        for m in migrations
    )


def test_registry_changelog_entry_for_2026_05_11_2() -> None:
    data = yaml.safe_load(REGISTRY_YAML.read_text(encoding="utf-8"))
    validate = next(a for a in data["artifacts"] if a["name"] == "validate.sh")
    assert "2026.05.11.2" in validate["changelog"]


def test_section_8_runs_against_empty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            ["bash", str(VALIDATE_SH)],
            cwd=tmp, capture_output=True, text=True, check=False,
        )
        assert result.returncode in (0, 1)
        # Section 8 always echoes this header banner; confirms the script ran past it.
        assert "unresolved markers" in result.stdout.lower()
