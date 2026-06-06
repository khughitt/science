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


import pytest

from science_tool.entities import (
    EntityCommandError,
    EntityPathPolicy,
    is_markdown_entity_kind,
    load_local_entity_policies,
    markdown_entity_kinds,
    resolve_path_policy,
)

_LOCAL_MANIFEST = """\
name: t-local
imports:
  - core
strictness: typed-extension
entity_kinds:
  - name: design
    canonical_prefix: design
    layer: layer/local
    description: Design.
  - name: gadget
    canonical_prefix: gadget
    layer: layer/local
    description: Gadget.
    home: entities/gizmos
relation_kinds: []
"""


def _project_with_local_kinds(tmp_path: Path) -> Path:
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_MANIFEST)
    return tmp_path


def test_load_local_entity_policies_derives_verbatim_home(tmp_path: Path) -> None:
    root = _project_with_local_kinds(tmp_path)
    policies = load_local_entity_policies(root)
    assert policies["design"] == EntityPathPolicy(Path("entities/design"), "numeric")
    assert policies["gadget"] == EntityPathPolicy(Path("entities/gizmos"), "numeric")


def test_resolve_path_policy_is_project_aware(tmp_path: Path) -> None:
    root = _project_with_local_kinds(tmp_path)
    assert resolve_path_policy("hypothesis").root == Path("entities/hypotheses")
    assert resolve_path_policy("design", project_root=root).root == Path("entities/design")
    with pytest.raises(EntityCommandError):
        resolve_path_policy("design")


def test_markdown_kinds_and_membership_are_project_aware(tmp_path: Path) -> None:
    root = _project_with_local_kinds(tmp_path)
    assert "design" not in markdown_entity_kinds()
    assert "design" in markdown_entity_kinds(project_root=root)
    assert not is_markdown_entity_kind("design")
    assert is_markdown_entity_kind("design", project_root=root)


def test_local_kind_may_not_shadow_core(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace("name: design", "name: hypothesis").replace(
        "canonical_prefix: design", "canonical_prefix: hypothesis"
    )
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    policies = load_local_entity_policies(tmp_path)
    assert "hypothesis" not in policies


def test_name_must_equal_canonical_prefix(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace("canonical_prefix: design", "canonical_prefix: dsgn")
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    with pytest.raises(EntityCommandError):
        load_local_entity_policies(tmp_path)


@pytest.mark.parametrize(
    "bad_home",
    [
        "/abs/entities/design",
        "../outside/design",
        "doc/design",
        "entities/../escape",
        "entities",
    ],
)
def test_home_override_must_be_relative_under_entities(tmp_path: Path, bad_home: str) -> None:
    manifest = _LOCAL_MANIFEST.replace("    home: entities/gizmos\n", f"    home: {bad_home}\n")
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    with pytest.raises(EntityCommandError):
        load_local_entity_policies(tmp_path)


@pytest.mark.parametrize("bad_strategy", ["banana", "singleton"])
def test_strategy_override_must_be_known(tmp_path: Path, bad_strategy: str) -> None:
    manifest = _LOCAL_MANIFEST.replace(
        "    home: entities/gizmos\n", f"    home: entities/gizmos\n    strategy: {bad_strategy}\n"
    )
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    with pytest.raises(EntityCommandError):
        load_local_entity_policies(tmp_path)


def test_strategy_override_accepts_known_values(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace(
        "    home: entities/gizmos\n", "    home: entities/gizmos\n    strategy: citekey\n"
    )
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    policies = load_local_entity_policies(tmp_path)
    assert policies["gadget"] == EntityPathPolicy(Path("entities/gizmos"), "citekey")


def test_no_local_profile_is_empty(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\n")
    assert load_local_entity_policies(tmp_path) == {}


from science_tool.entities import default_status, valid_statuses


def test_status_accessors_core_unchanged() -> None:
    assert default_status("hypothesis") == "proposed"
    assert "supported" in valid_statuses("hypothesis")


def test_local_kind_status_defaults_open(tmp_path: Path) -> None:
    root = _project_with_local_kinds(tmp_path)
    assert default_status("design", project_root=root) == "active"
    assert valid_statuses("design", project_root=root) is None  # open set


def test_local_kind_status_manifest_override(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace(
        "    description: Design.\n",
        "    description: Design.\n    default_status: draft\n    statuses: [draft, active]\n",
    )
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    assert default_status("design", project_root=tmp_path) == "draft"
    assert valid_statuses("design", project_root=tmp_path) == frozenset({"draft", "active"})


def test_status_unknown_kind_raises() -> None:
    with pytest.raises(KeyError):
        default_status("nonexistent-kind")
    with pytest.raises(KeyError):
        valid_statuses("nonexistent-kind")
