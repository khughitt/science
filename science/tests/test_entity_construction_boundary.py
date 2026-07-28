"""Gate 3: every load path that can emit a schema-closed kind validates BEFORE projection.

The Markdown adapter is not the only path. The structured-source loader builds entities from a
mapping it assembles itself, so a check placed there inspects the toolkit's own output. These
tests pin the ORDER -- lossless parse, declared normalization, composed validation, projection --
because a check downstream of a lossy step validates the loss, not the input.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from science_model.source_contracts import StructuredEntitySource
from science_tool.entity_profiles import ProjectSchema, load_project_schema_if_pinned
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import load_project_sources, registry_for_project


def _armed_registry(tmp_path: Path) -> tuple[EntityRegistry, ProjectSchema]:
    """A registry plus a project schema that is actually ARMED.

    The assert is the point. `load_project_schema_if_pinned` returns None for an unpinned
    project, `validate_against_schema` returns on its first line when handed None, and every
    refusal test in this file would then pass by never validating anything. A fixture that fails
    silently open is worse than no fixture.
    """
    root = tmp_path / "armed"
    root.mkdir()
    (root / "science.yaml").write_text(
        "name: demo\nentity_schema_version: 2\n", encoding="utf-8"
    )
    project_schema = load_project_schema_if_pinned(root)
    assert project_schema is not None, "fixture is not pinned; the refusal tests would be vacuous"
    return registry_for_project(root), project_schema


def _valid_hypothesis_mapping() -> dict[str, Any]:
    """A hypothesis mapping that passes `unevaluatedProperties: false` under base 2.0 + mixin 1.0.

    Not invented: this is the record `tests/test_undeclared_key_diagnostic.py:33-40` writes and
    loads through `load_project_sources` on a project pinned to `entity_schema_version: 2`, in a
    test asserting `hypothesis` is in `strict_schema_kinds` -- i.e. a record already proven to
    survive the closed path. `mixin-hypothesis-1.0.json` requires exactly `id`, `kind`, `status`;
    the rest are base-2.0-admitted and present because the proven fixture carries them.
    """
    return {
        "id": "hypothesis:h1",
        "kind": "hypothesis",
        "title": "H1",
        "status": "active",
        "related": [],
        "source_refs": [],
        "created": "2026-03-12",
        "updated": "2026-03-12",
    }


def _valid_concept_mapping() -> dict[str, Any]:
    """The same, for the OPEN kind. `concept` has no mixin, so only base 2.0 applies."""
    return {
        "id": "concept:c1",
        "kind": "concept",
        "title": "C1",
        "status": "active",
        "related": [],
        "source_refs": [],
        "created": "2026-03-12",
        "updated": "2026-03-12",
    }


def _enrich_projection_fields(raw: dict[str, Any]) -> frozenset[str]:
    """Supply model bookkeeping only after composed validation has accepted the authored view."""
    raw.update(
        {
            "project": "demo",
            "ontology_terms": [],
            "content_preview": "",
            "file_path": "entities/test.md",
        }
    )
    return frozenset()


def test_an_unknown_key_SURVIVES_the_source_contract() -> None:
    # extra="allow", not "ignore". This is what lets a shadow key reach schema validation at all.
    # extra="forbid" is rejected as the alternative: every existing row carries `kind`, which the
    # loader legitimately ignores, so forbidding would reject the whole corpus for a key the
    # design agrees is fine.
    record = StructuredEntitySource.model_validate(
        {"canonical_id": "finding:0001-x", "shadow_key": "value"}
    )
    assert record.model_extra == {"shadow_key": "value"}


def test_only_AUTHORED_keys_are_normalized() -> None:
    # The declared fields still DEFAULT (title="", profile="", source_path="", five empty lists).
    # Normalizing from the parsed record would promote those defaults into the mapping that gets
    # schema-validated -- an absent title would arrive as "" and fail minLength: 1, and an absent
    # evidence_refs would arrive as [] and read as an authored empty list.
    from science_tool.graph.source_normalization import normalize_structured_row

    normalized = normalize_structured_row({"canonical_id": "finding:0001-x"})
    assert normalized == {"id": "finding:0001-x"}
    assert "title" not in normalized
    assert "evidence_refs" not in normalized


def test_the_declared_key_mapping_is_applied() -> None:
    from science_tool.graph.source_normalization import normalize_structured_row

    normalized = normalize_structured_row(
        {"canonical_id": "finding:0001-x", "source_path": "knowledge/sources/x.yaml"}
    )
    assert normalized["id"] == "finding:0001-x"
    assert normalized["file_path"] == "knowledge/sources/x.yaml"
    assert "canonical_id" not in normalized
    assert "source_path" not in normalized


@pytest.mark.parametrize(
    "row",
    [
        {"canonical_id": "finding:0001-x", "id": "shadow"},
        {"id": "shadow", "canonical_id": "finding:0001-x"},
        {"canonical_id": "finding:0001-x", "id": "finding:0001-x"},
        {"id": "finding:0001-x", "canonical_id": "finding:0001-x"},
    ],
)
def test_canonical_id_and_id_collision_is_refused_for_any_order_or_value(
    row: dict[str, Any],
) -> None:
    from science_tool.graph.source_normalization import normalize_structured_row

    with pytest.raises(
        ValueError,
        match="authored keys 'canonical_id' and 'id' both normalize to 'id'",
    ):
        normalize_structured_row(row)


@pytest.mark.parametrize(
    "row",
    [
        {"source_path": "authored.yaml", "file_path": "shadow.yaml"},
        {"file_path": "shadow.yaml", "source_path": "authored.yaml"},
        {"source_path": "same.yaml", "file_path": "same.yaml"},
        {"file_path": "same.yaml", "source_path": "same.yaml"},
    ],
)
def test_source_path_and_file_path_collision_is_refused_for_any_order_or_value(
    row: dict[str, Any],
) -> None:
    from science_tool.graph.source_normalization import normalize_structured_row

    with pytest.raises(
        ValueError,
        match="authored keys 'file_path' and 'source_path' both normalize to 'file_path'",
    ):
        normalize_structured_row(row)


def test_kind_is_the_only_declared_DROP() -> None:
    # `kind` is authoritative from the manifest and deliberately ignored on the row, so it is a
    # legitimately dropped key rather than a shadow field. A drop that is not DECLARED is
    # indistinguishable from a bug, which is the whole reason this set is written down.
    from science_tool.graph.source_normalization import STRUCTURED_DROP_KEYS

    assert STRUCTURED_DROP_KEYS == frozenset({"kind"})


def test_a_shadow_key_reaches_the_normalized_mapping() -> None:
    from science_tool.graph.source_normalization import normalize_structured_row

    normalized = normalize_structured_row({"canonical_id": "finding:0001-x", "shadow_key": "v"})
    assert normalized["shadow_key"] == "v", "a shadow key must survive to be REFUSED downstream"


def _write_structured_project(root: Path, rows: list[dict]) -> None:
    """A project whose local profile declares one structured-source kind."""
    (root / "science.yaml").write_text(
        yaml.safe_dump({"name": "demo", "knowledge_profiles": {"local": "project_specific"}}),
        encoding="utf-8",
    )
    sources = root / "knowledge" / "sources" / "project_specific"
    sources.mkdir(parents=True)
    (sources / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "project_specific",
                "imports": [],
                "relation_kinds": [],
                "strictness": "typed-extension",
                "entity_kinds": [
                    {
                        "name": "widget",
                        "canonical_prefix": "widget",
                        "layer": "layer/local",
                        "description": "d",
                        "entity_class": "reference",
                        "structured_source": "widget.yaml",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (sources / "widget.yaml").write_text(yaml.safe_dump({"widget": rows}), encoding="utf-8")


def test_an_authored_shadow_key_SURVIVES_the_whole_load_path(tmp_path: Path) -> None:
    _write_structured_project(
        tmp_path, [{"canonical_id": "widget:0001-x", "title": "W", "shadow_key": "v"}]
    )
    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "widget:0001-x")
    assert (entity.model_extra or {}).get("shadow_key") == "v"


def test_an_alias_collision_is_refused_through_the_whole_load_path(tmp_path: Path) -> None:
    _write_structured_project(
        tmp_path,
        [{"canonical_id": "widget:0001-x", "id": "widget:shadow", "title": "W"}],
    )
    with pytest.raises(
        ValueError,
        match="authored keys 'canonical_id' and 'id' both normalize to 'id'",
    ):
        load_project_sources(tmp_path)


def _write_closed_kind_project(root: Path, rows: list[dict]) -> None:
    """A pinned project whose local profile attaches a structured source to core hypothesis."""
    _write_structured_project(root, [])
    (root / "science.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "demo",
                "knowledge_profiles": {"local": "project_specific"},
                "entity_schema_version": 2,
            }
        ),
        encoding="utf-8",
    )
    sources_dir = root / "knowledge" / "sources" / "project_specific"
    manifest = yaml.safe_load((sources_dir / "manifest.yaml").read_text())
    manifest["core_structured_sources"] = [
        {"kind": "hypothesis", "structured_source": "hypothesis.yaml"}
    ]
    (sources_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (sources_dir / "hypothesis.yaml").write_text(
        yaml.safe_dump({"hypothesis": rows}), encoding="utf-8"
    )


def _valid_hypothesis_row() -> dict[str, Any]:
    """The same valid hypothesis, in structured-row spelling."""
    return {
        "canonical_id": "hypothesis:h1",
        "title": "H1",
        "status": "active",
        "created": "2026-03-12",
        "updated": "2026-03-12",
    }


def test_a_CLOSED_kind_refuses_a_shadow_key_through_the_whole_structured_path(
    tmp_path: Path,
) -> None:
    _write_closed_kind_project(tmp_path, [{**_valid_hypothesis_row(), "shadow_key": "v"}])
    with pytest.raises(ValueError, match="does not satisfy its schema"):
        load_project_sources(tmp_path)


def test_the_same_closed_row_WITHOUT_the_shadow_key_loads(tmp_path: Path) -> None:
    _write_closed_kind_project(tmp_path, [_valid_hypothesis_row()])
    sources = load_project_sources(tmp_path)
    assert any(e.canonical_id == _valid_hypothesis_row()["canonical_id"] for e in sources.entities)


def test_an_unauthored_optional_field_is_absent_from_what_VALIDATION_SEES(
    tmp_path: Path, monkeypatch
) -> None:
    # The defaults-promotion failure. Asserting `entity.evidence_refs == []` on the loaded entity
    # would be INERT: `_enrich_raw` does `raw.setdefault("evidence_refs", [])` on every record, so
    # that assertion holds whether the value was authored, promoted from the source-model default,
    # or injected by enrichment. The claim is about the mapping VALIDATION is shown, upstream of
    # enrichment -- so spy on that.
    import science_tool.graph.entity_registry as reg_mod

    # Record the AUTHORED VIEW -- `raw` minus `injected` -- because that is the mapping the
    # validator ranges over. Spying on `raw` alone would assert the wrong thing now that
    # bookkeeping is subtracted inside the validator rather than absent from `raw`.
    seen: list[dict] = []
    real = reg_mod.validate_against_schema

    def _spy(raw, **kw):
        seen.append({k: v for k, v in raw.items() if k not in kw["injected"]})
        return real(raw, **kw)

    monkeypatch.setattr(reg_mod, "validate_against_schema", _spy)
    _write_structured_project(tmp_path, [{"canonical_id": "widget:0002-y", "title": "W2"}])
    load_project_sources(tmp_path)

    row = next(m for m in seen if m.get("id") == "widget:0002-y")
    assert "evidence_refs" not in row, "an unauthored field reached validation as an authored one"
    assert row["title"] == "W2"  # the authored ones DO arrive -- not a vacuously empty mapping


def test_structured_validation_sees_normalized_authored_destinations(
    tmp_path: Path, monkeypatch
) -> None:
    import science_tool.graph.entity_registry as reg_mod

    seen: list[dict] = []
    real = reg_mod.validate_against_schema

    def _spy(raw, **kw):
        seen.append({k: v for k, v in raw.items() if k not in kw["injected"]})
        return real(raw, **kw)

    monkeypatch.setattr(reg_mod, "validate_against_schema", _spy)
    _write_structured_project(
        tmp_path,
        [
            {
                "canonical_id": "widget:0003-z",
                "title": "W3",
                "source_path": "authored/widget.yaml",
                "evidence_refs": ["paper:p1"],
                "content": "authored prose",
            }
        ],
    )
    load_project_sources(tmp_path)

    row = next(m for m in seen if m.get("id") == "widget:0003-z")
    assert row["id"] == "widget:0003-z"
    assert "canonical_id" not in row
    assert row["file_path"] == "authored/widget.yaml"
    assert row["evidence_refs"] == ["paper:p1"]
    assert row["content"] == "authored prose"


def test_the_loaders_OWN_bookkeeping_keys_do_not_refuse_the_row(tmp_path: Path) -> None:
    # The control above passes only if `type`, `canonical_id`, `file_path` and the backfilled
    # `evidence_refs` are hidden from the composed schema -- each is refused by the hypothesis
    # profile, and the structured loader adds all four to every row.
    from science_tool.graph.sources import _STRUCTURED_INJECTED_KEYS

    assert {"type", "canonical_id", "file_path", "evidence_refs"} <= _STRUCTURED_INJECTED_KEYS
    assert not {"id", "kind", "title"} & _STRUCTURED_INJECTED_KEYS, (
        "id/kind/title are REQUIRED by the composed schema; hiding them refuses every record"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("content", "prose"), ("evidence_refs", ["paper:p1"])],
)
def test_an_AUTHORED_bookkeeping_key_is_still_refused(
    tmp_path: Path, field: str, value: object
) -> None:
    # These names are bookkeeping in some paths, but a structured-row author who writes either
    # authored it. The composed hypothesis schema must see and refuse it.
    _write_closed_kind_project(tmp_path, [{**_valid_hypothesis_row(), field: value}])
    with pytest.raises(ValueError, match="does not satisfy its schema"):
        load_project_sources(tmp_path)


def test_build_validates_a_closed_kind_before_projecting(tmp_path) -> None:
    # The load-bearing order. `hypothesis` is the one closed kind on this branch, so it is what
    # can demonstrate refusal at all.
    #
    # `ValueError`, not EntityValidationError: `validate_against_schema` CATCHES the model-layer
    # EntityValidationError and re-raises a ValueError carrying the path and the pinned
    # generation (sources.py:1431, moved in Step 3). Asserting the inner type would fail.
    registry, project_schema = _armed_registry(tmp_path)
    with pytest.raises(ValueError, match="does not satisfy its schema"):
        registry.build(
            "hypothesis",
            {**_valid_hypothesis_mapping(), "shadow_key": "v"},
            project_schema=project_schema,
            path="entities/hypotheses/0001-x.md",
            injected=frozenset(),
        )


def test_build_admits_a_valid_closed_kind(tmp_path) -> None:
    registry, project_schema = _armed_registry(tmp_path)
    entity = registry.build(
        "hypothesis",
        _valid_hypothesis_mapping(),
        project_schema=project_schema,
        path="entities/hypotheses/0001-x.md",
        injected=frozenset(),  # the mapping is entirely authored -- nothing to hide
        enrich=_enrich_projection_fields,
    )
    assert entity.kind == "hypothesis"


def test_build_does_not_validate_an_OPEN_kind(tmp_path) -> None:
    # Open kinds keep loading exactly as before -- this branch closes nothing. A shadow key on an
    # open kind is preserved, not refused; that is the `extra="allow"` projection doing its job.
    registry, project_schema = _armed_registry(tmp_path)
    entity = registry.build(
        "concept",
        {**_valid_concept_mapping(), "shadow_key": "v"},
        project_schema=project_schema,
        path="entities/concepts/0001-x.md",
        injected=frozenset(),
        enrich=_enrich_projection_fields,
    )
    assert entity.kind == "concept"
