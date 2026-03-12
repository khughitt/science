from datetime import date
from science_model.entities import Entity, EntityType


def test_entity_round_trip():
    e = Entity(
        id="hypothesis:h01-foo",
        type=EntityType.HYPOTHESIS,
        title="Test hypothesis",
        status="proposed",
        project="my-project",
        tags=["genomics"],
        ontology_terms=["GO:0006915"],
        created=date(2026, 3, 1),
        updated=date(2026, 3, 10),
        related=["question:q01"],
        source_refs=[],
        content_preview="A test hypothesis about...",
        file_path="specs/hypotheses/h01-foo.md",
    )
    assert e.type == EntityType.HYPOTHESIS
    assert e.id == "hypothesis:h01-foo"
    d = e.model_dump()
    assert d["type"] == "hypothesis"
    e2 = Entity.model_validate(d)
    assert e2 == e


def test_entity_optional_fields_default_none():
    e = Entity(
        id="concept:foo",
        type=EntityType.CONCEPT,
        title="Foo",
        project="p",
        tags=[],
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/topics/foo.md",
    )
    assert e.status is None
    assert e.domain is None
    assert e.maturity is None
    assert e.confidence is None
    assert e.datasets is None
    assert e.created is None
    assert e.updated is None
