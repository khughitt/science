from datetime import date

from science_model.entities import Entity, EntityType
from science_model.sync import SyncSource


def test_sync_source_round_trip():
    ss = SyncSource(project="aging-clocks", entity_id="question:q4-tp53", sync_date=date(2026, 3, 23))
    d = ss.model_dump()
    assert d == {"project": "aging-clocks", "entity_id": "question:q4-tp53", "sync_date": date(2026, 3, 23)}
    assert SyncSource.model_validate(d) == ss


def test_entity_with_sync_source():
    e = Entity(
        id="question:q-tp53-methylation",
        kind="question",
        type=EntityType.QUESTION,
        title="TP53 methylation question",
        project="protein-folding",
        ontology_terms=[],
        related=["gene:tp53"],
        source_refs=[],
        content_preview="Propagated question",
        file_path="doc/sync/q-tp53-methylation.md",
        sync_source=SyncSource(
            project="aging-clocks",
            entity_id="question:q4-tp53-methylation-age",
            sync_date=date(2026, 3, 23),
        ),
    )
    assert e.sync_source is not None
    assert e.sync_source.project == "aging-clocks"
    d = e.model_dump()
    e2 = Entity.model_validate(d)
    assert e2.sync_source == e.sync_source


def test_entity_without_sync_source_defaults_none():
    e = Entity(
        id="question:q1",
        kind="question",
        type=EntityType.QUESTION,
        title="Local question",
        project="p",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/q1.md",
    )
    assert e.sync_source is None
