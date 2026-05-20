from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from science_model.entities import Entity
from science_model.source_contracts import BindingSource

from science_tool.graph.commons_sources import collect_referenced_commons_ids
from science_tool.graph.sources import SourceRelation


def _entity(
    canonical_id: str,
    *,
    related: list[str] | None = None,
    source_refs: list[str] | None = None,
) -> Entity:
    kind = canonical_id.split(":", 1)[0]
    return Entity.model_validate(
        {
            "id": canonical_id,
            "kind": kind,
            "type": kind,
            "title": canonical_id,
            "project": "demo",
            "ontology_terms": [],
            "related": related or [],
            "source_refs": source_refs or [],
            "content_preview": "",
            "file_path": "",
        }
    )


def _collect(
    *,
    entities: list[object] | None = None,
    relations: list[SourceRelation] | None = None,
    bindings: list[BindingSource] | None = None,
) -> set[str]:
    return collect_referenced_commons_ids(
        project_entities=cast(list[Entity], entities or []),
        project_relations=relations or [],
        project_bindings=bindings or [],
    )


def test_collect_referenced_commons_ids_returns_empty_set_for_no_references() -> None:
    assert _collect(entities=[_entity("concept:local")]) == set()


def test_collect_referenced_commons_ids_collects_entity_related() -> None:
    assert _collect(entities=[_entity("concept:local", related=["paper:smith2024"])]) == {"paper:smith2024"}


def test_collect_referenced_commons_ids_collects_entity_source_refs() -> None:
    assert _collect(entities=[_entity("concept:local", source_refs=["dataset:rnaseq"])]) == {"dataset:rnaseq"}


@pytest.mark.parametrize(
    ("field_name", "reference"),
    [
        ("evidence_refs", "paper:evidence"),
        ("commits_to", "theme:program"),
        ("blocked_by", "topic:blocker"),
        ("chain", "paper:chain"),
        ("proposition_refs", "dataset:derived"),
        ("same_as", "topic:equivalent"),
        ("participants", "theme:participant"),
        ("propositions", "paper:proposition"),
    ],
)
def test_collect_referenced_commons_ids_collects_list_fields(field_name: str, reference: str) -> None:
    entity = SimpleNamespace(**{field_name: [reference]})

    assert _collect(entities=[entity]) == {reference}


def test_collect_referenced_commons_ids_collects_singular_audits_field() -> None:
    assert _collect(entities=[SimpleNamespace(audits="paper:audit")]) == {"paper:audit"}


def test_collect_referenced_commons_ids_collects_relation_endpoints() -> None:
    relation = SourceRelation(
        subject="paper:subject",
        predicate="supports",
        object="topic:object",
        source_path="knowledge/sources/local/entities.yaml",
    )

    assert _collect(relations=[relation]) == {"paper:subject", "topic:object"}


def test_collect_referenced_commons_ids_collects_binding_model_parameter_and_source_refs() -> None:
    binding = BindingSource(
        model="paper:model",
        parameter="topic:parameter",
        source_path="knowledge/sources/local/bindings.yaml",
        source_refs=["dataset:inputs", "theme:context"],
    )

    assert _collect(bindings=[binding]) == {
        "paper:model",
        "topic:parameter",
        "dataset:inputs",
        "theme:context",
    }


def test_collect_referenced_commons_ids_filters_to_commons_types() -> None:
    entity = SimpleNamespace(
        related=[
            "dataset:rnaseq",
            "paper:smith2024",
            "topic:phf19",
            "theme:reproducibility",
            "concept:local",
            "hypothesis:h1",
            "model:m1",
        ]
    )

    assert _collect(entities=[entity]) == {
        "dataset:rnaseq",
        "paper:smith2024",
        "topic:phf19",
        "theme:reproducibility",
    }


def test_collect_referenced_commons_ids_ignores_empty_commons_local_parts() -> None:
    entity = SimpleNamespace(related=["paper:", "dataset:", "topic:", "topic:phf19"])

    assert _collect(entities=[entity]) == {"topic:phf19"}


def test_collect_referenced_commons_ids_ignores_external_ontology_and_metadata_refs() -> None:
    entity = SimpleNamespace(
        related=[
            "https://example.org/source",
            "/tmp/results.csv",
            "./local.csv",
            "../parent.csv",
            "results/table.csv",
            "doi:10.1000/example",
            "go:0008150",
            "meta:reviewed",
            "paper",
            "",
            None,
            "topic:phf19",
        ]
    )

    assert _collect(entities=[entity]) == {"topic:phf19"}
