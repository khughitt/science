import pytest

from science_model.ontologies import available_ontology_names, load_catalogs_for_names, load_registry
from science_model.ontologies.schema import OntologyCatalog, OntologyTermType


def test_load_registry_returns_biolink_entry() -> None:
    registry = load_registry()
    names = [entry.name for entry in registry]
    assert "biolink" in names


def test_load_biolink_catalog_parses_entity_types() -> None:
    catalogs = load_catalogs_for_names(["biolink"])
    assert len(catalogs) == 1
    catalog = catalogs[0]
    assert catalog.ontology == "biolink"
    type_names = {et.name for et in catalog.entity_types}
    assert "gene" in type_names
    assert "protein" in type_names
    assert "pathway" in type_names

    gene = next(et for et in catalog.entity_types if et.name == "gene")
    assert "NCBIGene" in gene.curie_prefixes
    assert "ENSEMBL" in gene.curie_prefixes
    assert "HGNC" in gene.curie_prefixes
    assert gene.recommended is True


def test_load_biolink_catalog_parses_predicates() -> None:
    catalogs = load_catalogs_for_names(["biolink"])
    catalog = catalogs[0]
    pred_names = {p.name for p in catalog.predicates}
    assert "interacts_with" in pred_names
    assert "encodes" in pred_names
    assert "participates_in" in pred_names

    interacts = next(p for p in catalog.predicates if p.name == "interacts_with")
    assert interacts.recommended is True


def test_load_catalogs_for_names_raises_on_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown ontology 'chebi'"):
        load_catalogs_for_names(["chebi"])


def test_load_catalogs_for_names_returns_declared() -> None:
    catalogs = load_catalogs_for_names(["biolink"])
    assert len(catalogs) == 1
    assert catalogs[0].ontology == "biolink"


def test_available_ontology_names() -> None:
    names = available_ontology_names()
    assert names == ["biolink"]


def test_ontology_term_type_round_trip() -> None:
    term = OntologyTermType(
        id="biolink:Gene",
        name="gene",
        description="A gene.",
        curie_prefixes=["NCBIGene"],
        recommended=True,
    )
    data = term.model_dump()
    restored = OntologyTermType.model_validate(data)
    assert restored == term


def test_ontology_catalog_round_trip() -> None:
    catalog = OntologyCatalog(
        ontology="test",
        version="1.0",
        prefix="test",
        prefix_uri="https://example.org/test/",
        entity_types=[
            OntologyTermType(id="test:Foo", name="foo", description="A foo."),
        ],
        predicates=[],
    )
    data = catalog.model_dump()
    restored = OntologyCatalog.model_validate(data)
    assert restored == catalog
