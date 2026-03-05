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
