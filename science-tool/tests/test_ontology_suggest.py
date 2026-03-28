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
    suggestions = suggest_ontologies(entities, declared_ontologies=["biology"])
    assert suggestions == []


def test_suggests_biology_for_curie_prefixes() -> None:
    entities = [_entity(ontology_terms=["NCBIGene:7157"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    assert len(suggestions) == 1
    assert suggestions[0].ontology_name == "biology"
    assert suggestions[0].entity_count >= 1
    assert "CURIE" in suggestions[0].reason


def test_suggests_biology_for_kind_match() -> None:
    entities = [_entity(kind="gene")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    assert len(suggestions) == 1
    assert suggestions[0].ontology_name == "biology"
    assert "kind" in suggestions[0].reason


def test_no_suggestions_for_unrelated_entities() -> None:
    entities = [_entity(kind="hypothesis", ontology_terms=["functor"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    assert suggestions == []


# --- Physics suggestion tests ---


def test_suggests_physics_for_curie_prefixes() -> None:
    entities = [_entity(ontology_terms=["PDGID:11"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    physics_suggestions = [s for s in suggestions if s.ontology_name == "physics"]
    assert len(physics_suggestions) == 1
    assert physics_suggestions[0].entity_count >= 1
    assert "CURIE" in physics_suggestions[0].reason


def test_suggests_physics_for_kind_match() -> None:
    entities = [_entity(kind="elementary_particle")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    physics_suggestions = [s for s in suggestions if s.ontology_name == "physics"]
    assert len(physics_suggestions) == 1
    assert "kind" in physics_suggestions[0].reason


def test_no_physics_suggestions_when_declared() -> None:
    entities = [_entity(kind="elementary_particle", ontology_terms=["PDGID:11"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=["physics"])
    physics_suggestions = [s for s in suggestions if s.ontology_name == "physics"]
    assert physics_suggestions == []


# --- Units suggestion tests ---


def test_suggests_units_for_curie_prefixes() -> None:
    entities = [_entity(ontology_terms=["QUDT:Mass"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    units_suggestions = [s for s in suggestions if s.ontology_name == "units"]
    assert len(units_suggestions) == 1
    assert "CURIE" in units_suggestions[0].reason


def test_suggests_units_for_kind_match() -> None:
    entities = [_entity(kind="mass")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    units_suggestions = [s for s in suggestions if s.ontology_name == "units"]
    assert len(units_suggestions) == 1
    assert "kind" in units_suggestions[0].reason


def test_no_units_suggestions_when_declared() -> None:
    entities = [_entity(kind="mass", ontology_terms=["QUDT:Mass"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=["units"])
    units_suggestions = [s for s in suggestions if s.ontology_name == "units"]
    assert units_suggestions == []


def test_suggests_counts_both_prefix_and_kind() -> None:
    entities = [
        _entity(kind="gene", ontology_terms=["NCBIGene:7157"]),
        _entity(kind="protein"),
    ]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.ontology_name == "biology"
    # gene matches both prefix and kind, protein matches kind only
    assert s.entity_count >= 2


# --- Math suggestion tests ---


def test_suggests_math_for_mathworld_curie() -> None:
    entities = [_entity(ontology_terms=["MATHWORLD:Laplacian"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    math_suggestions = [s for s in suggestions if s.ontology_name == "math"]
    assert len(math_suggestions) == 1
    assert "CURIE" in math_suggestions[0].reason


def test_suggests_math_for_gradient_kind() -> None:
    entities = [_entity(kind="gradient")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    math_suggestions = [s for s in suggestions if s.ontology_name == "math"]
    assert len(math_suggestions) == 1
    assert "kind" in math_suggestions[0].reason


def test_no_suggestion_math_when_declared() -> None:
    entities = [_entity(kind="gradient")]
    suggestions = suggest_ontologies(entities, declared_ontologies=["math"])
    math_suggestions = [s for s in suggestions if s.ontology_name == "math"]
    assert len(math_suggestions) == 0


# --- Earth suggestion tests ---


def test_suggests_earth_for_envo_curie() -> None:
    entities = [_entity(ontology_terms=["ENVO:00000015"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    earth_suggestions = [s for s in suggestions if s.ontology_name == "earth"]
    assert len(earth_suggestions) == 1
    assert "CURIE" in earth_suggestions[0].reason


def test_suggests_earth_for_cloud_kind() -> None:
    entities = [_entity(kind="cloud")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    earth_suggestions = [s for s in suggestions if s.ontology_name == "earth"]
    assert len(earth_suggestions) == 1
    assert "kind" in earth_suggestions[0].reason


def test_no_suggestion_earth_when_declared() -> None:
    entities = [_entity(kind="cloud")]
    suggestions = suggest_ontologies(entities, declared_ontologies=["earth"])
    earth_suggestions = [s for s in suggestions if s.ontology_name == "earth"]
    assert len(earth_suggestions) == 0


# --- Chemistry suggestion tests ---


def test_suggests_chemistry_for_chebi_curie() -> None:
    entities = [_entity(ontology_terms=["CHEBI:15377"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    chem_suggestions = [s for s in suggestions if s.ontology_name == "chemistry"]
    assert len(chem_suggestions) == 1
    assert "CURIE" in chem_suggestions[0].reason


def test_suggests_chemistry_for_element_kind() -> None:
    entities = [_entity(kind="element")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    chem_suggestions = [s for s in suggestions if s.ontology_name == "chemistry"]
    assert len(chem_suggestions) == 1
    assert "kind" in chem_suggestions[0].reason


def test_no_suggestion_chemistry_when_declared() -> None:
    entities = [_entity(kind="element")]
    suggestions = suggest_ontologies(entities, declared_ontologies=["chemistry"])
    chem_suggestions = [s for s in suggestions if s.ontology_name == "chemistry"]
    assert len(chem_suggestions) == 0


# --- Astronomy suggestion tests ---


def test_suggests_astronomy_for_simbad_curie() -> None:
    entities = [_entity(ontology_terms=["SIMBAD:HD209458"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    astro_suggestions = [s for s in suggestions if s.ontology_name == "astronomy"]
    assert len(astro_suggestions) == 1
    assert "CURIE" in astro_suggestions[0].reason


def test_suggests_astronomy_for_star_kind() -> None:
    entities = [_entity(kind="star")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    astro_suggestions = [s for s in suggestions if s.ontology_name == "astronomy"]
    assert len(astro_suggestions) == 1
    assert "kind" in astro_suggestions[0].reason


def test_no_suggestion_astronomy_when_declared() -> None:
    entities = [_entity(kind="star")]
    suggestions = suggest_ontologies(entities, declared_ontologies=["astronomy"])
    astro_suggestions = [s for s in suggestions if s.ontology_name == "astronomy"]
    assert len(astro_suggestions) == 0


# --- Information suggestion tests ---


def test_suggests_information_for_network_kind() -> None:
    entities = [_entity(kind="network")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    info_suggestions = [s for s in suggestions if s.ontology_name == "information"]
    assert len(info_suggestions) == 1
    assert "kind" in info_suggestions[0].reason


def test_no_suggestion_information_when_declared() -> None:
    entities = [_entity(kind="network")]
    suggestions = suggest_ontologies(entities, declared_ontologies=["information"])
    info_suggestions = [s for s in suggestions if s.ontology_name == "information"]
    assert len(info_suggestions) == 0
