from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, SKOS

from science_tool.cli import main
from science_tool.distill.openalex import distill_openalex

SCI = Namespace("http://example.org/science/vocab/")
SCHEMA = Namespace("https://schema.org/")


def _mock_openalex_response(level: str) -> list[dict]:
    """Fixture: minimal OpenAlex API response for testing."""
    if level == "domains":
        return [
            {
                "id": "https://openalex.org/domains/1",
                "display_name": "Life Sciences",
                "works_count": 100000,
            },
        ]
    if level == "fields":
        return [
            {
                "id": "https://openalex.org/fields/11",
                "display_name": "Agricultural and Biological Sciences",
                "domain": {"id": "https://openalex.org/domains/1", "display_name": "Life Sciences"},
                "works_count": 50000,
            },
            {
                "id": "https://openalex.org/fields/12",
                "display_name": "Biochemistry, Genetics and Molecular Biology",
                "domain": {"id": "https://openalex.org/domains/1", "display_name": "Life Sciences"},
                "works_count": 60000,
            },
        ]
    if level == "subfields":
        return [
            {
                "id": "https://openalex.org/subfields/1101",
                "display_name": "Agricultural and Biological Sciences (miscellaneous)",
                "field": {"id": "https://openalex.org/fields/11", "display_name": "Agricultural and Biological Sciences"},
                "works_count": 5000,
            },
            {
                "id": "https://openalex.org/subfields/1201",
                "display_name": "Biochemistry",
                "field": {
                    "id": "https://openalex.org/fields/12",
                    "display_name": "Biochemistry, Genetics and Molecular Biology",
                },
                "works_count": 30000,
            },
        ]
    return []


def _mock_fetch_all(endpoint: str) -> list[dict]:
    """Mock for openalex._fetch_all_pages that returns fixture data."""
    level = endpoint.rstrip("/").rsplit("/", 1)[-1]
    return _mock_openalex_response(level)


def test_distill_openalex_subfields_produces_valid_turtle(tmp_path: Path) -> None:
    output = tmp_path / "openalex-science-map.ttl"

    with patch("science_tool.distill.openalex._fetch_all_pages", side_effect=_mock_fetch_all):
        result = distill_openalex(level="subfields", output_path=output)

    assert result.exists()
    g = Graph()
    g.parse(str(result), format="turtle")

    # Should have domain, field, and subfield nodes typed as sci:Concept
    concepts = set(g.subjects(RDF.type, SCI.Concept))
    assert len(concepts) == 5  # 1 domain + 2 fields + 2 subfields

    # All should have prefLabel
    for concept in concepts:
        assert any(g.triples((concept, SKOS.prefLabel, None)))

    # Should have broader/narrower links
    broader_count = len(list(g.triples((None, SKOS.broader, None))))
    assert broader_count >= 4  # 2 fields→domain + 2 subfields→field


def test_distill_openalex_writes_manifest(tmp_path: Path) -> None:
    output = tmp_path / "openalex-science-map.ttl"

    with patch("science_tool.distill.openalex._fetch_all_pages", side_effect=_mock_fetch_all):
        distill_openalex(level="subfields", output_path=output)

    manifest = tmp_path / "manifest.ttl"
    assert manifest.exists()

    g = Graph()
    g.parse(str(manifest), format="turtle")
    assert len(list(g.triples((None, SCHEMA.name, None)))) == 1
    assert len(list(g.triples((None, SCHEMA.sha256, None)))) == 1


import numpy as np

from science_tool.distill.pykeen_source import distill_pykeen


def _make_mock_triples_factory():
    """Create a mock TriplesFactory with small synthetic data."""
    from unittest.mock import MagicMock

    triples = np.array([
        ["GeneA", "interacts_with", "GeneB"],
        ["GeneA", "associated_with", "DiseaseX"],
        ["GeneB", "interacts_with", "GeneC"],
        ["DrugAlpha", "treats", "DiseaseX"],
        ["DiseaseX", "phenotype_present", "PhenotypeP"],
        ["GeneC", "associated_with", "DiseaseY"],
        ["DrugBeta", "treats", "DiseaseY"],
        ["GeneA", "interacts_with", "GeneC"],
    ], dtype=object)

    factory = MagicMock()
    factory.triples = triples
    factory.num_entities = 8
    factory.num_relations = 4
    factory.entity_to_id = {name: i for i, name in enumerate(
        ["GeneA", "GeneB", "GeneC", "DiseaseX", "DiseaseY", "DrugAlpha", "DrugBeta", "PhenotypeP"]
    )}
    factory.relation_to_id = {name: i for i, name in enumerate(
        ["interacts_with", "associated_with", "treats", "phenotype_present"]
    )}
    return factory


def test_distill_pykeen_no_budget_takes_all_triples(tmp_path: Path) -> None:
    output = tmp_path / "test-dataset.ttl"
    factory = _make_mock_triples_factory()

    with patch("science_tool.distill.pykeen_source._load_pykeen_dataset", return_value=factory):
        result = distill_pykeen(dataset_name="TestDataset", output_path=output)

    assert result.exists()
    g = Graph()
    g.parse(str(result), format="turtle")

    concepts = set(g.subjects(RDF.type, SCI.Concept))
    assert len(concepts) == 8  # all entities

    # All entities should have prefLabel
    for concept in concepts:
        assert any(g.triples((concept, SKOS.prefLabel, None)))


def test_distill_pykeen_with_budget_reduces_entities(tmp_path: Path) -> None:
    output = tmp_path / "test-budget.ttl"
    factory = _make_mock_triples_factory()

    with patch("science_tool.distill.pykeen_source._load_pykeen_dataset", return_value=factory):
        result = distill_pykeen(dataset_name="TestDataset", budget=4, output_path=output)

    assert result.exists()
    g = Graph()
    g.parse(str(result), format="turtle")

    concepts = set(g.subjects(RDF.type, SCI.Concept))
    # Budget=4 means at most 4 entities selected
    assert len(concepts) <= 4
    assert len(concepts) >= 1  # at least some survived


def test_distill_pykeen_writes_manifest(tmp_path: Path) -> None:
    output = tmp_path / "test-dataset.ttl"
    factory = _make_mock_triples_factory()

    with patch("science_tool.distill.pykeen_source._load_pykeen_dataset", return_value=factory):
        distill_pykeen(dataset_name="TestDataset", output_path=output)

    manifest = tmp_path / "manifest.ttl"
    assert manifest.exists()


from rdflib import Literal, URIRef
from rdflib.namespace import PROV


def _write_test_snapshot(path: Path) -> None:
    """Write a minimal Turtle snapshot for import testing."""
    g = Graph()
    g.bind("sci", SCI)
    g.bind("skos", SKOS)
    concept = URIRef("http://example.org/test/concept1")
    g.add((concept, RDF.type, SCI.Concept))
    g.add((concept, SKOS.prefLabel, Literal("TestConcept")))
    g.serialize(destination=str(path), format="turtle")


def test_graph_import_merges_into_knowledge_layer() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        snapshot = Path("snapshot.ttl")
        _write_test_snapshot(snapshot)

        result = runner.invoke(main, ["graph", "import", str(snapshot)])
        assert result.exit_code == 0

        from rdflib import Dataset as RdfDataset

        dataset = RdfDataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(URIRef("http://example.org/project/graph/knowledge"))

        concept = URIRef("http://example.org/test/concept1")
        assert (concept, RDF.type, SCI.Concept) in knowledge
        assert (concept, SKOS.prefLabel, Literal("TestConcept")) in knowledge


def test_graph_import_records_provenance() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        snapshot = Path("snapshot.ttl")
        _write_test_snapshot(snapshot)

        result = runner.invoke(main, ["graph", "import", str(snapshot)])
        assert result.exit_code == 0

        from rdflib import Dataset as RdfDataset

        dataset = RdfDataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        provenance = dataset.graph(URIRef("http://example.org/project/graph/provenance"))

        # Should have an import provenance record
        import_records = list(provenance.triples((None, PROV.generatedAtTime, None)))
        assert len(import_records) >= 1


def test_graph_import_reports_triple_count() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        snapshot = Path("snapshot.ttl")
        _write_test_snapshot(snapshot)

        result = runner.invoke(main, ["graph", "import", str(snapshot)])
        assert result.exit_code == 0
        assert "2" in result.output  # 2 triples imported
