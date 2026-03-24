from science_tool.graph.sources import SourceEntity
from science_tool.graph.suggest import suggest_ontologies


def _entity(*, kind: str = "hypothesis", ontology_terms: list[str] | None = None) -> SourceEntity:
    return SourceEntity(
        canonical_id=f"{kind}:test",
        kind=kind,
        title="Test entity",
        profile="core",
        source_path="test.md",
        ontology_terms=ontology_terms or [],
    )


def test_no_suggestions_when_ontology_declared() -> None:
    entities = [_entity(ontology_terms=["NCBIGene:7157"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=["biolink"])
    assert suggestions == []


def test_suggests_biolink_for_curie_prefixes() -> None:
    entities = [_entity(ontology_terms=["NCBIGene:7157"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    assert len(suggestions) == 1
    assert suggestions[0].ontology_name == "biolink"
    assert suggestions[0].entity_count >= 1
    assert "CURIE" in suggestions[0].reason


def test_suggests_biolink_for_kind_match() -> None:
    entities = [_entity(kind="gene")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    assert len(suggestions) == 1
    assert suggestions[0].ontology_name == "biolink"
    assert "kind" in suggestions[0].reason


def test_no_suggestions_for_unrelated_entities() -> None:
    entities = [_entity(kind="hypothesis", ontology_terms=["functor"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    assert suggestions == []


def test_suggests_counts_both_prefix_and_kind() -> None:
    entities = [
        _entity(kind="gene", ontology_terms=["NCBIGene:7157"]),
        _entity(kind="protein"),
    ]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.ontology_name == "biolink"
    # gene matches both prefix and kind, protein matches kind only
    assert s.entity_count >= 2
