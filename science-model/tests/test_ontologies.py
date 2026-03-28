import pytest

from science_model.ontologies import available_ontology_names, load_catalogs_for_names, load_registry
from science_model.ontologies.schema import OntologyCatalog, OntologyTermType


def test_load_registry_returns_biology_entry() -> None:
    registry = load_registry()
    names = [entry.name for entry in registry]
    assert "biology" in names


def test_load_biology_catalog_parses_entity_types() -> None:
    catalogs = load_catalogs_for_names(["biology"])
    assert len(catalogs) == 1
    catalog = catalogs[0]
    assert catalog.ontology == "biology"
    type_names = {et.name for et in catalog.entity_types}
    assert "gene" in type_names
    assert "protein" in type_names
    assert "pathway" in type_names

    gene = next(et for et in catalog.entity_types if et.name == "gene")
    assert "NCBIGene" in gene.curie_prefixes
    assert "ENSEMBL" in gene.curie_prefixes
    assert "HGNC" in gene.curie_prefixes
    assert gene.recommended is True


def test_load_biology_catalog_parses_predicates() -> None:
    catalogs = load_catalogs_for_names(["biology"])
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
    catalogs = load_catalogs_for_names(["biology"])
    assert len(catalogs) == 1
    assert catalogs[0].ontology == "biology"


def test_available_ontology_names() -> None:
    names = available_ontology_names()
    assert "biology" in names
    assert "physics" in names
    assert "units" in names


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


# --- Physics catalog tests ---


def test_load_physics_catalog_parses_entity_types() -> None:
    catalogs = load_catalogs_for_names(["physics"])
    assert len(catalogs) == 1
    catalog = catalogs[0]
    assert catalog.ontology == "physics"
    type_names = {et.name for et in catalog.entity_types}
    assert "elementary_particle" in type_names
    assert "quantum_state" in type_names
    assert "physical_system" in type_names

    particle = next(et for et in catalog.entity_types if et.name == "elementary_particle")
    assert "PDGID" in particle.curie_prefixes
    assert "WD" in particle.curie_prefixes
    assert particle.recommended is True


def test_load_physics_catalog_parses_predicates() -> None:
    catalogs = load_catalogs_for_names(["physics"])
    catalog = catalogs[0]
    pred_names = {p.name for p in catalog.predicates}
    assert "decays_to" in pred_names
    assert "mediates" in pred_names
    assert "composed_of" in pred_names

    decays = next(p for p in catalog.predicates if p.name == "decays_to")
    assert decays.recommended is True


def test_physics_recommended_counts() -> None:
    catalogs = load_catalogs_for_names(["physics"])
    catalog = catalogs[0]
    rec_types = sum(1 for et in catalog.entity_types if et.recommended)
    rec_preds = sum(1 for p in catalog.predicates if p.recommended)
    assert 20 <= rec_types <= 50, f"Expected 20-50 recommended types, got {rec_types}"
    assert 15 <= rec_preds <= 35, f"Expected 15-35 recommended predicates, got {rec_preds}"


def test_physics_curie_prefixes() -> None:
    catalogs = load_catalogs_for_names(["physics"])
    catalog = catalogs[0]
    quark = next(et for et in catalog.entity_types if et.name == "quark")
    assert len(quark.curie_prefixes) > 0
    crystal = next(et for et in catalog.entity_types if et.name == "crystal")
    assert "COD" in crystal.curie_prefixes


# --- Units catalog tests ---


def test_load_units_catalog_parses_entity_types() -> None:
    catalogs = load_catalogs_for_names(["units"])
    assert len(catalogs) == 1
    catalog = catalogs[0]
    assert catalog.ontology == "units"
    type_names = {et.name for et in catalog.entity_types}
    assert "mass" in type_names
    assert "energy" in type_names
    assert "temperature" in type_names
    assert "velocity" in type_names


def test_load_units_catalog_parses_predicates() -> None:
    catalogs = load_catalogs_for_names(["units"])
    catalog = catalogs[0]
    pred_names = {p.name for p in catalog.predicates}
    assert "has_quantity_kind" in pred_names
    assert "has_unit" in pred_names
    assert "measured_in" in pred_names
    assert len(catalog.predicates) == 6


def test_units_recommended_counts() -> None:
    catalogs = load_catalogs_for_names(["units"])
    catalog = catalogs[0]
    rec_types = sum(1 for et in catalog.entity_types if et.recommended)
    assert 20 <= rec_types <= 50, f"Expected 20-50 recommended quantity kinds, got {rec_types}"
    rec_preds = sum(1 for p in catalog.predicates if p.recommended)
    assert rec_preds == 4


def test_units_curie_prefixes() -> None:
    catalogs = load_catalogs_for_names(["units"])
    catalog = catalogs[0]
    mass = next(et for et in catalog.entity_types if et.name == "mass")
    assert "QUDT" in mass.curie_prefixes


def test_load_registry_returns_math_entry() -> None:
    registry = load_registry()
    names = [entry.name for entry in registry]
    assert "math" in names


def test_load_math_catalog_parses_entity_types() -> None:
    catalogs = load_catalogs_for_names(["math"])
    assert len(catalogs) == 1
    catalog = catalogs[0]
    assert catalog.ontology == "math"
    assert catalog.prefix == "math"
    type_names = {et.name for et in catalog.entity_types}
    assert "gradient" in type_names
    assert "eigenvalue" in type_names
    assert "bifurcation" in type_names
    assert "manifold" in type_names
    assert "functor" in type_names


def test_math_catalog_has_recommended_entity_types() -> None:
    catalogs = load_catalogs_for_names(["math"])
    catalog = catalogs[0]
    recommended = [et for et in catalog.entity_types if et.recommended]
    assert 20 <= len(recommended) <= 50


def test_math_catalog_has_predicates() -> None:
    catalogs = load_catalogs_for_names(["math"])
    catalog = catalogs[0]
    pred_names = {p.name for p in catalog.predicates}
    assert "operates_on" in pred_names
    assert "generalizes" in pred_names
    assert len(catalog.predicates) >= 10


def test_math_catalog_has_recommended_predicates() -> None:
    catalogs = load_catalogs_for_names(["math"])
    catalog = catalogs[0]
    recommended = [p for p in catalog.predicates if p.recommended]
    assert 10 <= len(recommended) <= 35


def test_load_registry_returns_earth_entry() -> None:
    registry = load_registry()
    names = [entry.name for entry in registry]
    assert "earth" in names


def test_load_earth_catalog_parses_entity_types() -> None:
    catalogs = load_catalogs_for_names(["earth"])
    assert len(catalogs) == 1
    catalog = catalogs[0]
    assert catalog.ontology == "earth"
    assert catalog.prefix == "earth"
    type_names = {et.name for et in catalog.entity_types}
    assert "cloud" in type_names
    assert "river" in type_names
    assert "volcano" in type_names
    assert "erosion" in type_names
    assert "branching_pattern" in type_names


def test_earth_catalog_has_recommended_entity_types() -> None:
    catalogs = load_catalogs_for_names(["earth"])
    catalog = catalogs[0]
    recommended = [et for et in catalog.entity_types if et.recommended]
    assert 20 <= len(recommended) <= 55


def test_earth_catalog_has_predicates() -> None:
    catalogs = load_catalogs_for_names(["earth"])
    catalog = catalogs[0]
    pred_names = {p.name for p in catalog.predicates}
    assert "occurs_in" in pred_names
    assert "shaped_by" in pred_names
    assert len(catalog.predicates) >= 10


def test_earth_catalog_has_recommended_predicates() -> None:
    catalogs = load_catalogs_for_names(["earth"])
    catalog = catalogs[0]
    recommended = [p for p in catalog.predicates if p.recommended]
    assert 8 <= len(recommended) <= 35


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
