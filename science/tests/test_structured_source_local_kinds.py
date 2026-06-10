"""Profile-declared structured sources for project-local kinds.

A project-local kind may declare `structured_source: <file>.yaml` in its profile
manifest. Each row in that single-type YAML file (under knowledge/sources/<profile>/)
loads as an OWNER entity of that kind — generalizing the hardcoded model/parameter
loaders so generated structural kinds (limit-relation, morphism-edge, …) need not
ride the multi-type entities.yaml/terms.yaml aggregate that v3 retirement forbids.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.graph.sources import load_project_sources

_PROFILE = """\
name: t-local
imports:
  - core
strictness: typed-extension
entity_kinds:
  - name: limit-relation
    canonical_prefix: limit-relation
    layer: layer/local
    description: Project-local model-to-model limit-relation row.
    structured_source: limit-relation.yaml
relation_kinds: []
"""

_SOURCE = """\
limit-relation:
  - canonical_id: limit-relation:allee-effect__logistic-growth__a
    kind: limit-relation
    title: "model:allee-effect -> model:logistic-growth (A)"
    profile: t-local
    source_path: knowledge/sources/local/limits.yaml
    created: "2026-04-30"
    updated: "2026-06-01"
  - canonical_id: limit-relation:asep__burgers-equation__a
    kind: limit-relation
    title: "model:asep -> model:burgers-equation (A)"
    profile: t-local
    source_path: knowledge/sources/local/limits.yaml
"""


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _seed(root: Path) -> None:
    _write(root, "science.yaml", "name: t\nlayout_version: 3\nknowledge_profiles:\n  local: local\n")
    _write(root, "knowledge/sources/local/manifest.yaml", _PROFILE)
    _write(root, "knowledge/sources/local/limit-relation.yaml", _SOURCE)


def test_structured_source_rows_load_as_owner_entities(tmp_path: Path) -> None:
    _seed(tmp_path)
    src = load_project_sources(tmp_path, strict_core_schema=False, strict_identity=False)
    by_id = {e.canonical_id: e for e in src.entities}
    assert "limit-relation:allee-effect__logistic-growth__a" in by_id
    assert "limit-relation:asep__burgers-equation__a" in by_id
    e = by_id["limit-relation:allee-effect__logistic-growth__a"]
    assert e.kind == "limit-relation"
    # Loaded by the structured-source adapter, not the multi-type aggregate.
    assert src.entity_source_adapters[e.canonical_id] == "structured-source"


def test_structured_source_rows_are_owner_declarations_not_aggregate(tmp_path: Path) -> None:
    """The rows must NOT appear as aggregate rows (which v3 would flag for retirement)."""
    _seed(tmp_path)
    src = load_project_sources(tmp_path, strict_core_schema=False, strict_identity=False)
    agg_ids = {r.canonical_id for r in src.aggregate_rows}
    assert "limit-relation:allee-effect__logistic-growth__a" not in agg_ids


def test_root_key_defaults_to_kind_name_and_missing_file_is_noop(tmp_path: Path) -> None:
    # No structured_source file present → no entities, no error.
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 3\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _PROFILE)
    src = load_project_sources(tmp_path, strict_core_schema=False, strict_identity=False)
    assert not [e for e in src.entities if e.kind == "limit-relation"]
