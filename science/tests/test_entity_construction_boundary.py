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
from science_tool.graph.sources import load_project_sources


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


@pytest.mark.xfail(
    strict=True,
    reason="composed validation on the structured path arrives in Task 5",
)
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
