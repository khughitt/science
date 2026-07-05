"""Profile-declared structured sources for project-local kinds.

A project-local kind may declare `structured_source: <file>.yaml` in its profile
manifest. Each row in that single-type YAML file (under knowledge/sources/<profile>/)
loads as an OWNER entity of that kind — generalizing the hardcoded model/parameter
loaders so generated structural kinds (limit-relation, morphism-edge, …) can use
a declared current structured source instead of an ad hoc manifest.
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


def test_root_key_defaults_to_kind_name_and_missing_file_is_noop(tmp_path: Path) -> None:
    # No structured_source file present → no entities, no error.
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 3\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _PROFILE)
    src = load_project_sources(tmp_path, strict_core_schema=False, strict_identity=False)
    assert not [e for e in src.entities if e.kind == "limit-relation"]


# A CORE kind (finding) augmented via core_structured_sources — no local-kind
# registration, so no EntityKindShadowError, yet rows load as owner entities.
_CORE_PROFILE = """\
name: t-core
imports:
  - core
strictness: typed-extension
entity_kinds: []
relation_kinds: []
core_structured_sources:
  - kind: finding
    structured_source: finding.yaml
"""

_FINDING_SOURCE = """\
finding:
  - canonical_id: finding:t291-path2-audit-asep__burgers-equation__heat-equation
    kind: finding
    title: "Path-2 audit: asep -> burgers-equation -> heat-equation = invalid"
    profile: t-core
    source_path: knowledge/sources/local/finding.yaml
    created: "2026-04-30"
    description: "At least one step is not a strict parameter_limit edge."
    evidence_refs:
      - limit-relation:asep__burgers-equation__a
      - limit-relation:burgers-equation__heat-equation__amplitude
  - canonical_id: finding:t291-path2-audit-bidomain__cable__hodgkin-huxley
    kind: finding
    title: "Path-2 audit: bidomain-model -> cable-equation -> hodgkin-huxley = valid"
    profile: t-core
    source_path: knowledge/sources/local/finding.yaml
"""


def _seed_core(root: Path) -> None:
    _write(root, "science.yaml", "name: t\nlayout_version: 3\nknowledge_profiles:\n  local: local\n")
    _write(root, "knowledge/sources/local/manifest.yaml", _CORE_PROFILE)
    _write(root, "knowledge/sources/local/finding.yaml", _FINDING_SOURCE)


def test_core_structured_source_rows_load_as_owner_entities(tmp_path: Path) -> None:
    _seed_core(tmp_path)
    src = load_project_sources(tmp_path, strict_core_schema=False, strict_identity=False)
    by_id = {e.canonical_id: e for e in src.entities}
    fid = "finding:t291-path2-audit-asep__burgers-equation__heat-equation"
    assert fid in by_id
    assert by_id[fid].kind == "finding"
    # Loaded by the structured-source adapter, not the multi-type aggregate.
    assert src.entity_source_adapters[fid] == "structured-source"
    # evidence_refs must survive — they drive the finding's bears_on edges.
    assert list(getattr(by_id[fid], "evidence_refs", [])) == [
        "limit-relation:asep__burgers-equation__a",
        "limit-relation:burgers-equation__heat-equation__amplitude",
    ]
