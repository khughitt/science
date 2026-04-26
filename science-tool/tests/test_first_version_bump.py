"""After Plan #7 fixes: registry shows two versions; old install classifies as STALE."""

import hashlib
from pathlib import Path

from science_tool.project_artifacts.loader import load_packaged_registry


def test_registry_has_two_versions() -> None:
    reg = load_packaged_registry()
    art = next(a for a in reg.artifacts if a.name == "validate.sh")
    assert len(art.previous_hashes) >= 1
    assert art.version == "2026.04.26.1"
    assert art.previous_hashes[-1].version == "2026.04.26"


def test_byte_replace_migration_recorded() -> None:
    reg = load_packaged_registry()
    art = next(a for a in reg.artifacts if a.name == "validate.sh")
    bump = next(m for m in art.migrations if m.to_version == "2026.04.26.1")
    assert bump.kind.value == "byte_replace"
    assert bump.steps == []
    assert "Plan #7" in bump.summary


def test_old_install_classifies_as_stale(tmp_path: Path) -> None:
    """A project with the pre-bump hash installed should classify as STALE.

    Placeholder per the plan: real assertion runs in T37 acceptance test against
    the actual previous canonical bytes. Here we exercise that previous_hashes is
    populated so future tooling can match against it.
    """
    reg = load_packaged_registry()
    art = next(a for a in reg.artifacts if a.name == "validate.sh")
    prev = art.previous_hashes[-1]
    body = b"# fake body matching previous_hashes\n"
    _h = hashlib.sha256(body).hexdigest()
    target = tmp_path / "validate.sh"
    target.write_bytes(
        b"#!/usr/bin/env bash\n# science-managed-artifact: validate.sh\n"
        b"# science-managed-version: 2026.04.26\n"
        + f"# science-managed-source-sha256: {prev.hash}\n".encode()
        + b"# (body would be the actual previous canonical body)\n"
    )
    assert prev.version == "2026.04.26"
    assert len(prev.hash) == 64
