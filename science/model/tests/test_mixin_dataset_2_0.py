from __future__ import annotations

from science_model.entity_schema import MergePolicy, default_profile_for_kind, parse_profile, read_merge_policy


_V1 = parse_profile("science-entity-base/1.0+dataset/1.0")
_V2 = parse_profile("science-entity-base/1.0+dataset/2.0")


def test_dataset_2_declares_status_project_only() -> None:
    assert read_merge_policy(_V2)["status"] is MergePolicy.PROJECT_ONLY


def test_dataset_1_keeps_its_pinned_status_semantics() -> None:
    assert read_merge_policy(_V1)["status"] is MergePolicy.REPLACE


def test_dataset_default_moves_atomically_to_2_0() -> None:
    assert default_profile_for_kind("dataset").render() == "science-entity-base/1.0+dataset/2.0"
