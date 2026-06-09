from __future__ import annotations

from science_tool.graph.storage_adapters.aggregate import (
    MULTI_TYPE_AGGREGATE_ROOT_KEYS,
    multi_type_root_key,
)


def test_root_keys_map_both_multi_type_files() -> None:
    assert MULTI_TYPE_AGGREGATE_ROOT_KEYS == {"entities.yaml": "entities", "terms.yaml": "terms"}


def test_helper_returns_root_key_for_known_files() -> None:
    assert multi_type_root_key("entities.yaml") == "entities"
    assert multi_type_root_key("terms.yaml") == "terms"


def test_helper_returns_none_for_single_type_or_unknown() -> None:
    assert multi_type_root_key("topics.json") is None
    assert multi_type_root_key("datasets.yaml") is None
    assert multi_type_root_key("") is None
