from __future__ import annotations

from pathlib import Path

from science_model.entity_schema import PROJECT_MIXIN_NAMES
from science_model.source_contracts import StructuredEntitySource
from science_tool.graph.sources import ProjectSources, load_project_sources


def _write_project(root: Path, *, pinned: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    pin = "entity_schema_version: 2\n" if pinned else ""
    (root / "science.yaml").write_text(f"name: demo\n{pin}", encoding="utf-8")
    hyp = root / "entities" / "hypotheses" / "h1.md"
    hyp.parent.mkdir(parents=True)
    hyp.write_text(
        '---\nid: "hypothesis:h1"\nkind: "hypothesis"\ntitle: "H1"\nstatus: "active"\n'
        'related: []\nsource_refs: []\ncreated: "2026-03-12"\nupdated: "2026-03-12"\n'
        "---\nBody.\n",
        encoding="utf-8",
    )


def test_project_sources_has_strict_schema_kinds_field_default() -> None:
    field = ProjectSources.model_fields["strict_schema_kinds"]
    assert field.get_default(call_default_factory=True) == frozenset()


def test_unpinned_project_strict_schema_kinds_is_empty(tmp_path: Path) -> None:
    _write_project(tmp_path / "p", pinned=False)
    assert load_project_sources(tmp_path / "p").strict_schema_kinds == frozenset()


def test_pinned_project_strict_schema_kinds_is_mixin_names(tmp_path: Path) -> None:
    _write_project(tmp_path / "p", pinned=True)
    assert load_project_sources(tmp_path / "p").strict_schema_kinds == PROJECT_MIXIN_NAMES


def test_structured_source_drops_unknown_reference_key() -> None:
    # The extra-preserving-path invariant: structured sources cannot carry a stray
    # reference-named key into model_extra (extra="ignore"), so the diagnostic can
    # never misfire on them. StructuredEntitySource requires canonical_id and has no
    # `kind` field; both `kind` and `method` here are unknown keys and are dropped.
    record = StructuredEntitySource.model_validate(
        {"canonical_id": "workflow:w", "title": "W", "kind": "workflow", "method": "phantom"}
    )
    assert not (record.model_extra or {})
