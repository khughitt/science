from __future__ import annotations

from pathlib import Path

from science_model.profiles.schema import EntityKind
from science_tool.graph.sources import resolve_local_profile_name


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_entity_kind_accepts_optional_layout_and_status_fields() -> None:
    ek = EntityKind(
        name="design",
        canonical_prefix="design",
        layer="layer/local",
        description="Project-local design spec.",
        home="entities/designs",
        strategy="numeric",
        default_status="active",
        statuses=["active", "superseded"],
    )
    assert ek.home == "entities/designs"
    assert ek.strategy == "numeric"
    assert ek.default_status == "active"
    assert ek.statuses == ["active", "superseded"]


def test_entity_kind_overrides_default_to_none() -> None:
    ek = EntityKind(name="note", canonical_prefix="note", layer="layer/local", description="Note.")
    assert ek.home is None
    assert ek.strategy is None
    assert ek.default_status is None
    assert ek.statuses is None


def test_resolve_local_profile_name_knowledge_profiles(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: mm30-local\n")
    assert resolve_local_profile_name(tmp_path) == "mm30-local"


def test_resolve_local_profile_name_legacy_profiles(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nprofiles:\n  local: legacy-local\n")
    assert resolve_local_profile_name(tmp_path) == "legacy-local"


def test_resolve_local_profile_name_defaults_to_local(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\n")
    assert resolve_local_profile_name(tmp_path) == "local"
