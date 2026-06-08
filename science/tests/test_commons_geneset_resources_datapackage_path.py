from __future__ import annotations

from pathlib import Path

from science_tool.commons.geneset_resources import dataset_datapackage_path


def test_orphan_datapackage_returns_entity_path() -> None:
    # adapter == "datapackage": the entity IS the datapackage; its own path is read.
    p = dataset_datapackage_path(
        entity_adapter="datapackage", entity_path="data/ds1/datapackage.yaml", datapackage_rel=None
    )
    assert p == Path("data/ds1/datapackage.yaml")


def test_deferred_owner_returns_recorded_datapackage_rel() -> None:
    # a real markdown owner with a deferred local datapackage attachment.
    p = dataset_datapackage_path(
        entity_adapter="markdown", entity_path="entities/datasets/ds1.md", datapackage_rel="data/ds1/datapackage.yaml"
    )
    assert p == Path("data/ds1/datapackage.yaml")


def test_entity_md_source_maps_to_sibling_datapackage() -> None:
    # an orphan whose entity source is an entity.md sits beside its datapackage.yaml.
    p = dataset_datapackage_path(entity_adapter="datapackage", entity_path="data/ds1/entity.md", datapackage_rel=None)
    assert p == Path("data/ds1/datapackage.yaml")


def test_commons_merged_is_not_a_local_datapackage() -> None:
    # commons-scope resources are owned/materialized by commons (§B4 owner_scope) -> None here.
    assert (
        dataset_datapackage_path(entity_adapter="commons-merged", entity_path="x/entity.md", datapackage_rel=None)
        is None
    )


def test_no_datapackage_returns_none() -> None:
    assert (
        dataset_datapackage_path(
            entity_adapter="markdown", entity_path="entities/datasets/ds1.md", datapackage_rel=None
        )
        is None
    )
