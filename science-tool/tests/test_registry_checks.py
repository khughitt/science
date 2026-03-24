from __future__ import annotations

from datetime import date

from science_tool.registry.checks import check_registry
from science_tool.registry.index import RegistryEntity, RegistryEntitySource, RegistryIndex
from science_tool.registry.matching import MatchTier


def _index_with_entity(canonical_id: str, aliases: list[str] | None = None,
                        ontology_terms: list[str] | None = None) -> RegistryIndex:
    return RegistryIndex(
        entities=[
            RegistryEntity(
                canonical_id=canonical_id,
                kind="gene",
                title="Test entity",
                profile="bio",
                aliases=aliases or [],
                ontology_terms=ontology_terms or [],
                source_projects=[
                    RegistryEntitySource(project="proj-a", first_seen=date(2026, 3, 1)),
                ],
            ),
        ],
    )


def test_check_registry_exact_match():
    index = _index_with_entity("gene:tp53")
    matches = check_registry("gene:tp53", aliases=[], ontology_terms=[], registry_index=index)
    assert len(matches) == 1
    assert matches[0].tier == MatchTier.EXACT


def test_check_registry_no_match():
    index = _index_with_entity("gene:tp53")
    matches = check_registry("gene:brca1", aliases=[], ontology_terms=[], registry_index=index)
    assert matches == []


def test_check_registry_empty_index():
    matches = check_registry("gene:tp53", aliases=[], ontology_terms=[], registry_index=RegistryIndex())
    assert matches == []
