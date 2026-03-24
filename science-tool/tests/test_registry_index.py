from __future__ import annotations

from datetime import date

from science_tool.registry.index import (
    RegistryEntity,
    RegistryEntitySource,
    RegistryIndex,
    RegistryRelation,
    load_registry_index,
    save_registry_index,
)


def test_registry_entity_round_trip():
    entity = RegistryEntity(
        canonical_id="gene:tp53",
        kind="gene",
        title="TP53",
        profile="bio",
        aliases=["p53", "TP53"],
        ontology_terms=["NCBIGene:7157"],
        source_projects=[
            RegistryEntitySource(project="proj-a", status="active", first_seen=date(2026, 3, 15)),
        ],
    )
    d = entity.model_dump()
    assert RegistryEntity.model_validate(d) == entity


def test_registry_index_round_trip(tmp_path):
    registry_dir = tmp_path / "registry"
    index = RegistryIndex(
        entities=[
            RegistryEntity(
                canonical_id="gene:tp53",
                kind="gene",
                title="TP53",
                profile="bio",
                source_projects=[
                    RegistryEntitySource(project="proj-a", first_seen=date(2026, 3, 15)),
                ],
            ),
        ],
        relations=[
            RegistryRelation(
                subject="gene:tp53",
                predicate="biolink:participates_in",
                object="pathway:apoptosis",
                source_projects=["proj-a"],
            ),
        ],
    )
    save_registry_index(index, registry_dir)
    loaded = load_registry_index(registry_dir)
    assert len(loaded.entities) == 1
    assert loaded.entities[0].canonical_id == "gene:tp53"
    assert len(loaded.relations) == 1
    assert loaded.relations[0].predicate == "biolink:participates_in"


def test_load_registry_index_missing(tmp_path):
    index = load_registry_index(tmp_path / "registry")
    assert index.entities == []
    assert index.relations == []


def test_registry_entity_multi_project():
    entity = RegistryEntity(
        canonical_id="gene:tp53",
        kind="gene",
        title="TP53",
        profile="bio",
        source_projects=[
            RegistryEntitySource(project="proj-a", first_seen=date(2026, 3, 1)),
            RegistryEntitySource(project="proj-b", first_seen=date(2026, 3, 10)),
        ],
    )
    assert len(entity.source_projects) == 2
    project_names = {sp.project for sp in entity.source_projects}
    assert project_names == {"proj-a", "proj-b"}
