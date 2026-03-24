from __future__ import annotations

from datetime import date

from science_tool.registry.index import RegistryEntity, RegistryEntitySource
from science_tool.registry.matching import MatchResult, MatchTier, find_matches


def _make_entity(
    canonical_id: str,
    kind: str = "gene",
    title: str = "Test",
    aliases: list[str] | None = None,
    ontology_terms: list[str] | None = None,
) -> RegistryEntity:
    return RegistryEntity(
        canonical_id=canonical_id,
        kind=kind,
        title=title,
        profile="bio",
        aliases=aliases or [],
        ontology_terms=ontology_terms or [],
        source_projects=[RegistryEntitySource(project="proj-a", first_seen=date(2026, 3, 1))],
    )


def test_exact_canonical_id_match():
    registry = [_make_entity("gene:tp53")]
    matches = find_matches("gene:tp53", aliases=[], ontology_terms=[], registry_entities=registry)
    assert len(matches) == 1
    assert matches[0].tier == MatchTier.EXACT
    assert matches[0].entity.canonical_id == "gene:tp53"


def test_alias_match():
    registry = [_make_entity("gene:tp53", aliases=["p53", "TP53"])]
    matches = find_matches("gene:p53-variant", aliases=["p53"], ontology_terms=[], registry_entities=registry)
    assert len(matches) == 1
    assert matches[0].tier == MatchTier.ALIAS


def test_ontology_term_match():
    registry = [_make_entity("gene:tp53", ontology_terms=["NCBIGene:7157"])]
    matches = find_matches(
        "gene:tumor-protein-53", aliases=[], ontology_terms=["NCBIGene:7157"], registry_entities=registry
    )
    assert len(matches) == 1
    assert matches[0].tier == MatchTier.ONTOLOGY


def test_fuzzy_title_match():
    registry = [_make_entity("gene:tp53", title="TP53 (Tumor Protein P53)")]
    matches = find_matches(
        "gene:tumor-protein-p53",
        aliases=[],
        ontology_terms=[],
        registry_entities=registry,
        candidate_kind="gene",
        candidate_title="Tumor Protein P53",
    )
    fuzzy = [m for m in matches if m.tier == MatchTier.FUZZY]
    assert len(fuzzy) == 1


def test_no_match():
    registry = [_make_entity("gene:tp53")]
    matches = find_matches("gene:brca1", aliases=[], ontology_terms=[], registry_entities=registry)
    assert matches == []


def test_highest_tier_wins():
    entity = _make_entity("gene:tp53", aliases=["p53"], ontology_terms=["NCBIGene:7157"])
    registry = [entity]
    matches = find_matches(
        "gene:tp53", aliases=["p53"], ontology_terms=["NCBIGene:7157"], registry_entities=registry
    )
    assert len(matches) == 1
    assert matches[0].tier == MatchTier.EXACT  # highest tier
