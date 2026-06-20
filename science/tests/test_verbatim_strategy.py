"""Phase 3c: the `verbatim` filename strategy + `decision` core kind."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.entities import (
    _VALID_STRATEGIES,
    EntityCommandError,
    entity_policies,
    generate_entity_id,
    local_part_conforms,
    resolve_path_policy,
    validate_entity_id,
)


def test_decision_resolves_to_verbatim_policy():
    policy = resolve_path_policy("decision")
    assert policy.root == Path("entities/decision")
    assert policy.strategy == "verbatim"


def test_verbatim_accepts_uppercase_and_kebab_ids():
    assert local_part_conforms("decision", "D1")
    assert local_part_conforms("decision", "D10")
    assert local_part_conforms("decision", "D2-treatment-response-category")


def test_verbatim_rejects_unsafe_local_parts():
    assert not local_part_conforms("decision", "../escape")
    assert not local_part_conforms("decision", "a/b")
    assert not local_part_conforms("decision", ".hidden")
    assert not local_part_conforms("decision", "D..x")
    assert not local_part_conforms("decision", "")


def test_validate_entity_id_accepts_verbatim_decision():
    assert validate_entity_id("decision", "decision:D1") == "decision:D1"


def test_validate_entity_id_rejects_bad_verbatim_local_part():
    with pytest.raises(EntityCommandError):
        validate_entity_id("decision", "decision:../escape")
    with pytest.raises(EntityCommandError):
        validate_entity_id("decision", "decision:D..x")


def test_generate_entity_id_verbatim_requires_explicit_id():
    # Sequence identities are never derived from a title.
    with pytest.raises(EntityCommandError):
        generate_entity_id(Path("."), "decision", "Some decision title", None, None)
    # An explicit id passes straight through.
    assert generate_entity_id(Path("."), "decision", "ignored", "decision:D7", None) == "decision:D7"


def test_verbatim_is_builtin_only_not_in_valid_strategies():
    # Mirrors `singleton`: a local manifest may not opt into `verbatim`.
    assert "verbatim" not in _VALID_STRATEGIES


def test_builtin_decision_overrides_local_manifest(tmp_path: Path):
    # A project whose local manifest still declares `decision` must still resolve
    # to the builtin verbatim policy (builtins win; local shadowing is silent).
    sources = tmp_path / "knowledge" / "sources" / "local"
    sources.mkdir(parents=True)
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    (sources / "manifest.yaml").write_text(
        "name: local\n"
        "imports: []\n"
        "strictness: typed-extension\n"
        "relation_kinds: []\n"
        "entity_kinds:\n"
        "  - name: decision\n"
        "    canonical_prefix: decision\n"
        "    layer: project\n"
        "    description: local decision\n"
        "    home: entities/local-decisions\n"
        "    strategy: numeric\n",
        encoding="utf-8",
    )
    policy = resolve_path_policy("decision", project_root=tmp_path)
    assert policy.root == Path("entities/decision")
    assert policy.strategy == "verbatim"
    # And the local declaration of `decision` is absent from the resolved table's
    # local override (builtin key wins on merge).
    assert entity_policies(tmp_path)["decision"].strategy == "verbatim"
